import secrets
from datetime import datetime, timedelta

from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


# ---------------------------------------------------------------------------
# StockReservationBatch — model tests
# ---------------------------------------------------------------------------

@tagged('post_install', '-at_install')
class TestStockReservationBatch(TransactionCase):
    """Comprehensive tests for the StockReservationBatch model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.stock_location = cls.env.ref('stock.stock_location_stock')
        cls.output_location = cls.env.ref('stock.stock_location_output')
        cls.uom_unit = cls.env.ref('uom.product_uom_unit')
        cls.product = cls.env['product.product'].create({
            'name': 'Reservation Product',
            'type': 'consu',
            'uom_id': cls.uom_unit.id,
            'uom_po_id': cls.uom_unit.id,
        })
        cls.lot_product = cls.env['product.product'].create({
            'name': 'Lot Reservation Product',
            'type': 'consu',
            'tracking': 'lot',
            'uom_id': cls.uom_unit.id,
            'uom_po_id': cls.uom_unit.id,
        })

    def _make_batch(self, product=None, qty=5.0, confirm=True, location=None):
        """Helper: create (and optionally confirm) a single-line batch."""
        batch = self.env['stock.reservation.batch'].create({
            'request_user_id': self.env.user.id,
            'line_ids': [(0, 0, {
                'product_id': (product or self.product).id,
                'requested_qty': qty,
                'location_id': (location or self.stock_location).id,
            })],
        })
        if confirm:
            batch.action_confirm()
        return batch

    def _add_stock(self, product=None, qty=10.0, lot=None):
        self.env['stock.quant']._update_available_quantity(
            product or self.product, self.stock_location, qty, lot_id=lot
        )

    # ------------------------------------------------------------------ #
    # Creation & sequence                                                   #
    # ------------------------------------------------------------------ #

    def test_create_auto_sequence(self):
        """Batch name must be auto-generated from sequence, not stay 'New'."""
        batch = self._make_batch(confirm=False)
        self.assertNotEqual(batch.name, 'New')
        self.assertTrue(batch.name)

    def test_create_default_state_is_draft(self):
        batch = self._make_batch(confirm=False)
        self.assertEqual(batch.state, 'draft')

    def test_create_default_priority(self):
        batch = self._make_batch(confirm=False)
        self.assertEqual(batch.priority, '1')

    # ------------------------------------------------------------------ #
    # action_confirm                                                        #
    # ------------------------------------------------------------------ #

    def test_confirm_no_lines_raises(self):
        batch = self.env['stock.reservation.batch'].create({
            'request_user_id': self.env.user.id,
        })
        with self.assertRaises(UserError):
            batch.action_confirm()

    def test_confirm_sets_state_confirmed(self):
        batch = self._make_batch(confirm=False)
        self.assertEqual(batch.state, 'draft')
        batch.action_confirm()
        self.assertEqual(batch.state, 'confirmed')

    # ------------------------------------------------------------------ #
    # action_cancel                                                         #
    # ------------------------------------------------------------------ #

    def test_cancel_sets_batch_state(self):
        batch = self._make_batch()
        batch.action_cancel()
        self.assertEqual(batch.state, 'cancelled')

    def test_cancel_marks_non_allocated_lines_cancelled(self):
        batch = self._make_batch()
        batch.action_cancel()
        for line in batch.line_ids:
            self.assertEqual(line.state, 'cancelled')

    def test_cancel_preserves_allocated_lines(self):
        """Lines already 'allocated' must remain allocated after cancel."""
        self._add_stock(qty=10.0)
        batch = self._make_batch(qty=5.0)
        batch.action_allocate()
        line = batch.line_ids[0]
        self.assertEqual(line.state, 'allocated')
        batch.action_cancel()
        self.assertEqual(line.state, 'allocated')
        self.assertEqual(batch.state, 'cancelled')

    # ------------------------------------------------------------------ #
    # action_mark_done                                                      #
    # ------------------------------------------------------------------ #

    def test_mark_done_sets_state(self):
        batch = self._make_batch()
        batch.action_mark_done()
        self.assertEqual(batch.state, 'done')

    # ------------------------------------------------------------------ #
    # _action_allocate_single guards                                        #
    # ------------------------------------------------------------------ #

    def test_allocate_raises_if_in_progress(self):
        batch = self._make_batch()
        batch.allocation_in_progress = True
        with self.assertRaises(UserError):
            batch._action_allocate_single()

    def test_allocate_raises_if_state_done(self):
        """action_mark_done transitions to 'done'; allocation must then be refused."""
        batch = self._make_batch(confirm=False)
        batch.action_mark_done()
        self.assertEqual(batch.state, 'done')
        with self.assertRaises(UserError):
            batch._action_allocate_single()

    def test_allocate_raises_if_state_cancelled(self):
        """action_cancel transitions to 'cancelled'; allocation must then be refused."""
        batch = self._make_batch()
        batch.action_cancel()
        self.assertEqual(batch.state, 'cancelled')
        with self.assertRaises(UserError):
            batch._action_allocate_single()

    def test_allocate_raises_if_no_lines(self):
        """Batch starts in 'draft' (a valid-for-allocation state) but has no lines."""
        batch = self.env['stock.reservation.batch'].create({
            'request_user_id': self.env.user.id,
        })
        self.assertFalse(batch.line_ids)
        with self.assertRaises(UserError):
            batch._action_allocate_single()

    def test_allocate_resets_in_progress_flag(self):
        """allocation_in_progress flag must always be reset after allocation."""
        self._add_stock(qty=10.0)
        batch = self._make_batch(qty=5.0)
        batch.action_allocate()
        self.assertFalse(batch.allocation_in_progress)

    # ------------------------------------------------------------------ #
    # Allocation scenarios                                                  #
    # ------------------------------------------------------------------ #

    def test_full_allocation(self):
        self._add_stock(qty=10.0)
        batch = self._make_batch(qty=6.0)
        batch.action_allocate()
        line = batch.line_ids[0]
        self.assertEqual(line.allocated_qty, 6.0)
        self.assertEqual(line.state, 'allocated')
        self.assertTrue(line.move_id)
        self.assertEqual(batch.state, 'allocated')

    def test_partial_allocation(self):
        self._add_stock(qty=2.0)
        batch = self._make_batch(qty=5.0)
        batch.action_allocate()
        line = batch.line_ids[0]
        self.assertEqual(line.allocated_qty, 2.0)
        self.assertEqual(line.state, 'partial')
        self.assertEqual(batch.state, 'partial')

    def test_no_stock_allocation(self):
        batch = self._make_batch(qty=4.0)
        batch.action_allocate()
        line = batch.line_ids[0]
        self.assertEqual(line.allocated_qty, 0.0)
        self.assertEqual(line.state, 'not_available')
        self.assertFalse(line.move_id)
        self.assertEqual(batch.state, 'partial')

    def test_multi_line_all_allocated(self):
        """Two lines, both fully satisfied → batch state = 'allocated'."""
        self._add_stock(qty=20.0)
        batch = self.env['stock.reservation.batch'].create({
            'request_user_id': self.env.user.id,
            'line_ids': [
                (0, 0, {'product_id': self.product.id, 'requested_qty': 4.0,
                        'location_id': self.stock_location.id}),
                (0, 0, {'product_id': self.product.id, 'requested_qty': 3.0,
                        'location_id': self.stock_location.id}),
            ],
        })
        batch.action_confirm()
        batch.action_allocate()
        self.assertEqual(batch.state, 'allocated')
        for line in batch.line_ids:
            self.assertEqual(line.state, 'allocated')

    def test_multi_line_mixed_produces_partial_batch(self):
        """First line fully satisfied, second not → batch state = 'partial'."""
        self._add_stock(qty=5.0)
        batch = self.env['stock.reservation.batch'].create({
            'request_user_id': self.env.user.id,
            'line_ids': [
                (0, 0, {'product_id': self.product.id, 'requested_qty': 4.0,
                        'location_id': self.stock_location.id}),
                (0, 0, {'product_id': self.product.id, 'requested_qty': 10.0,
                        'location_id': self.stock_location.id}),
            ],
        })
        batch.action_confirm()
        batch.action_allocate()
        self.assertEqual(batch.state, 'partial')

    # ------------------------------------------------------------------ #
    # FEFO / preferred lot                                                  #
    # ------------------------------------------------------------------ #

    def test_fefo_lot_selection(self):
        """FEFO: lot expiring soonest must be consumed first."""
        lot_soon = self.env['stock.lot'].create({
            'name': 'LOT-SOON',
            'product_id': self.lot_product.id,
            'company_id': self.env.company.id,
            'expiration_date': datetime.now() + timedelta(days=5),
        })
        lot_later = self.env['stock.lot'].create({
            'name': 'LOT-LATER',
            'product_id': self.lot_product.id,
            'company_id': self.env.company.id,
            'expiration_date': datetime.now() + timedelta(days=20),
        })
        self._add_stock(self.lot_product, 2.0, lot=lot_later)
        self._add_stock(self.lot_product, 2.0, lot=lot_soon)
        batch = self._make_batch(product=self.lot_product, qty=1.0)
        batch.action_allocate()
        line = batch.line_ids[0]
        self.assertEqual(line.lot_id, lot_soon)
        self.assertEqual(line.state, 'allocated')

    def test_allocate_with_preferred_lot(self):
        """When lot_id is set on the line only that lot should be consumed."""
        lot_a = self.env['stock.lot'].create({
            'name': 'LOT-A', 'product_id': self.lot_product.id,
            'company_id': self.env.company.id,
        })
        lot_b = self.env['stock.lot'].create({
            'name': 'LOT-B', 'product_id': self.lot_product.id,
            'company_id': self.env.company.id,
        })
        self._add_stock(self.lot_product, 5.0, lot=lot_a)
        self._add_stock(self.lot_product, 5.0, lot=lot_b)
        batch = self.env['stock.reservation.batch'].create({
            'request_user_id': self.env.user.id,
            'line_ids': [(0, 0, {
                'product_id': self.lot_product.id,
                'requested_qty': 3.0,
                'location_id': self.stock_location.id,
                'lot_id': lot_b.id,
            })],
        })
        batch.action_confirm()
        batch.action_allocate()
        line = batch.line_ids[0]
        self.assertEqual(line.lot_id, lot_b)
        self.assertEqual(line.allocated_qty, 3.0)

    # ------------------------------------------------------------------ #
    # _compute_line_state                                                   #
    # ------------------------------------------------------------------ #

    def test_compute_line_state_not_available(self):
        batch = self._make_batch()
        self.assertEqual(batch._compute_line_state(10.0, 0.0), 'not_available')

    def test_compute_line_state_partial(self):
        batch = self._make_batch()
        self.assertEqual(batch._compute_line_state(10.0, 5.0), 'partial')

    def test_compute_line_state_fully_allocated(self):
        batch = self._make_batch()
        self.assertEqual(batch._compute_line_state(10.0, 10.0), 'allocated')

    # ------------------------------------------------------------------ #
    # _compute_batch_state                                                  #
    # ------------------------------------------------------------------ #

    def test_compute_batch_state_empty_lines_gives_draft(self):
        batch = self.env['stock.reservation.batch'].create({
            'request_user_id': self.env.user.id,
        })
        batch._compute_batch_state()
        self.assertEqual(batch.state, 'draft')

    # ------------------------------------------------------------------ #
    # _compute_move_count                                                   #
    # ------------------------------------------------------------------ #

    def test_move_count_zero_before_allocation(self):
        self._add_stock(qty=10.0)
        batch = self._make_batch(qty=5.0)
        self.assertEqual(batch.move_count, 0)

    def test_move_count_increments_after_allocation(self):
        self._add_stock(qty=10.0)
        batch = self._make_batch(qty=5.0)
        batch.action_allocate()
        self.assertEqual(batch.move_count, 1)

    # ------------------------------------------------------------------ #
    # _create_stock_move_for_line                                           #
    # ------------------------------------------------------------------ #

    def test_create_stock_move_zero_qty_raises(self):
        batch = self._make_batch()
        line = batch.line_ids[0]
        line.allocated_qty = 0.0
        with self.assertRaises(UserError):
            batch._create_stock_move_for_line(line)

    def test_stock_move_created_with_correct_product(self):
        self._add_stock(qty=10.0)
        batch = self._make_batch(qty=5.0)
        batch.action_allocate()
        line = batch.line_ids[0]
        self.assertTrue(line.move_id)
        self.assertEqual(line.move_id.product_id, self.product)
        self.assertEqual(line.move_id.product_uom_qty, 5.0)

    # ------------------------------------------------------------------ #
    # action_view_moves                                                     #
    # ------------------------------------------------------------------ #

    def test_action_view_moves_returns_action(self):
        self._add_stock(qty=10.0)
        batch = self._make_batch(qty=5.0)
        batch.action_allocate()
        action = batch.action_view_moves()
        self.assertIn('domain', action)
        move_ids = batch.line_ids.mapped('move_id').ids
        self.assertEqual(action['domain'], [('id', 'in', move_ids)])

    def test_action_view_moves_empty_when_no_moves(self):
        batch = self._make_batch()
        action = batch.action_view_moves()
        self.assertEqual(action['domain'], [('id', 'in', [])])


# ---------------------------------------------------------------------------
# StockReservationLine — model tests
# ---------------------------------------------------------------------------

@tagged('post_install', '-at_install')
class TestStockReservationLine(TransactionCase):
    """Tests for StockReservationLine model constraints and computed fields."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.stock_location = cls.env.ref('stock.stock_location_stock')
        cls.uom_unit = cls.env.ref('uom.product_uom_unit')
        cls.product = cls.env['product.product'].create({
            'name': 'Line Test Product',
            'type': 'consu',
            'uom_id': cls.uom_unit.id,
        })

    def _make_line(self, requested_qty=10.0, allocated_qty=0.0):
        batch = self.env['stock.reservation.batch'].create({
            'request_user_id': self.env.user.id,
            'line_ids': [(0, 0, {
                'product_id': self.product.id,
                'requested_qty': requested_qty,
                'location_id': self.stock_location.id,
                'allocated_qty': allocated_qty,
            })],
        })
        return batch, batch.line_ids[0]

    def test_line_default_state_is_draft(self):
        _, line = self._make_line()
        self.assertEqual(line.state, 'draft')

    def test_allocated_exceeds_requested_raises_validation(self):
        _, line = self._make_line(requested_qty=5.0, allocated_qty=0.0)
        line.allocated_qty = 6.0
        with self.assertRaises(ValidationError):
            line._check_allocated_qty()

    def test_allocated_equals_requested_is_valid(self):
        _, line = self._make_line(requested_qty=5.0)
        line.allocated_qty = 5.0
        line._check_allocated_qty()  # must not raise

    def test_allocated_less_than_requested_is_valid(self):
        _, line = self._make_line(requested_qty=5.0)
        line.allocated_qty = 3.0
        line._check_allocated_qty()  # must not raise

    def test_related_company_id(self):
        batch, line = self._make_line()
        self.assertEqual(line.company_id, batch.company_id)

    def test_related_request_user_id(self):
        _, line = self._make_line()
        self.assertEqual(line.request_user_id, self.env.user)

    def test_line_note_field(self):
        _, line = self._make_line()
        line.note = 'urgent'
        self.assertEqual(line.note, 'urgent')


# ---------------------------------------------------------------------------
# ReservationApiToken — model tests
# ---------------------------------------------------------------------------

@tagged('post_install', '-at_install')
class TestReservationApiToken(TransactionCase):
    """Tests for ReservationApiToken model."""

    def test_token_creation_defaults_active(self):
        token = self.env['reservation.api.token'].create({
            'name': 'Test Token',
            'user_id': self.env.user.id,
            'token': secrets.token_hex(32),
        })
        self.assertTrue(token.active)
        self.assertEqual(token.user_id, self.env.user)

    def test_token_can_be_deactivated(self):
        token = self.env['reservation.api.token'].create({
            'name': 'Inactive Token',
            'user_id': self.env.user.id,
            'token': secrets.token_hex(32),
        })
        token.active = False
        self.assertFalse(token.active)

    def test_active_token_found_by_value(self):
        val = secrets.token_hex(16)
        created = self.env['reservation.api.token'].create({
            'name': 'Active Token',
            'user_id': self.env.user.id,
            'token': val,
            'active': True,
        })
        found = self.env['reservation.api.token'].search([
            ('token', '=', val), ('active', '=', True),
        ])
        self.assertEqual(found, created)

    def test_inactive_token_not_found_in_active_search(self):
        val = secrets.token_hex(16)
        self.env['reservation.api.token'].create({
            'name': 'Inactive Token',
            'user_id': self.env.user.id,
            'token': val,
            'active': False,
        })
        found = self.env['reservation.api.token'].search([
            ('token', '=', val), ('active', '=', True),
        ])
        self.assertFalse(found)

    def test_token_name_is_rec_name(self):
        val = secrets.token_hex(16)
        token = self.env['reservation.api.token'].create({
            'name': 'My Token',
            'user_id': self.env.user.id,
            'token': val,
        })
        self.assertEqual(token.display_name, 'My Token')
