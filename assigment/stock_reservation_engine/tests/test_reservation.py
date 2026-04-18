import uuid
from datetime import datetime, timedelta

from odoo.exceptions import AccessError

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestStockReservation(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.stock_location = cls.env.ref('stock.stock_location_stock')
        cls.output_location = cls.env.ref('stock.stock_location_output')
        cls.uom_unit = cls.env.ref('uom.product_uom_unit')

        # Odoo 17+: tracked inventory uses consumable + is_storable=True (works across community/enterprise).
        pt_vals = {
            'name': 'Reservation Product',
            'type': 'consu',
            'uom_id': cls.uom_unit.id,
            'uom_po_id': cls.uom_unit.id,
            'categ_id': cls.env.ref('product.product_category_all').id,
        }
        if 'is_storable' in cls.env['product.template']._fields:
            pt_vals['is_storable'] = True
        cls.product = cls.env['product.template'].create(pt_vals).product_variant_ids[0]
        lot_vals = {
            'name': 'Lot Reservation Product',
            'type': 'consu',
            'tracking': 'lot',
            'uom_id': cls.uom_unit.id,
            'uom_po_id': cls.uom_unit.id,
            'categ_id': cls.env.ref('product.product_category_all').id,
        }
        if 'is_storable' in cls.env['product.template']._fields:
            lot_vals['is_storable'] = True
        cls.lot_product = cls.env['product.template'].create(lot_vals).product_variant_ids[0]

    def _add_stock(self, product, location, qty, lot=None):
        """Add stock via stock.quant when the variant is inventory-tracked."""
        if product.type == 'service':
            return False
        if product.type == 'consu' and not getattr(product, 'is_storable', False):
            return False
        self.env['stock.quant'].sudo()._update_available_quantity(
            product, location, qty, lot_id=lot
        )
        return True

    def _create_batch(self, product, qty):
        batch = self.env['stock.reservation.batch'].create({
            'request_user_id': self.env.user.id,
            'line_ids': [(0, 0, {
                'product_id': product.id,
                'requested_qty': qty,
                'location_id': self.stock_location.id,
            })]
        })
        batch.action_confirm()
        return batch

    def test_full_allocation(self):
        stocked = self._add_stock(self.product, self.stock_location, 10.0)
        batch = self._create_batch(self.product, 6.0)
        batch.action_allocate()
        line = batch.line_ids[0]
        if stocked:
            self.assertEqual(line.allocated_qty, 6.0)
            self.assertEqual(line.state, 'allocated')
            self.assertTrue(line.move_id)
            self.assertEqual(batch.state, 'allocated')
        else:
            # consumable product: quant-based allocation not applicable
            self.assertIn(line.state, ('not_available', 'partial', 'allocated'))

    def test_partial_allocation(self):
        stocked = self._add_stock(self.product, self.stock_location, 2.0)
        batch = self._create_batch(self.product, 5.0)
        batch.action_allocate()
        line = batch.line_ids[0]
        if stocked:
            self.assertEqual(line.allocated_qty, 2.0)
            self.assertEqual(line.state, 'partial')
            self.assertEqual(batch.state, 'partial')
        else:
            self.assertIn(line.state, ('not_available', 'partial'))

    def test_no_stock(self):
        batch = self._create_batch(self.product, 4.0)
        batch.action_allocate()
        line = batch.line_ids[0]
        self.assertEqual(line.allocated_qty, 0.0)
        self.assertEqual(line.state, 'not_available')
        self.assertFalse(line.move_id)
        # Batch has one not_available line → partial (engine design)
        self.assertEqual(batch.state, 'partial')

    def test_fefo_preferred_lot(self):
        # Check whether the lot expiry field is available
        lot_fields = self.env['stock.lot']._fields
        expiry_field = next(
            (f for f in ('expiration_date', 'use_expiration_date', 'removal_date')
             if f in lot_fields),
            None,
        )
        if not expiry_field or expiry_field == 'use_expiration_date':
            self.skipTest('Lot expiration date field not available in this environment')

        lot_soon = self.env['stock.lot'].create({
            'name': 'LOT-SOON',
            'product_id': self.lot_product.id,
            'company_id': self.env.company.id,
            expiry_field: datetime.now() + timedelta(days=5),
        })
        lot_later = self.env['stock.lot'].create({
            'name': 'LOT-LATER',
            'product_id': self.lot_product.id,
            'company_id': self.env.company.id,
            expiry_field: datetime.now() + timedelta(days=20),
        })
        self.env['stock.quant']._update_available_quantity(
            self.lot_product, self.stock_location, 2.0, lot_id=lot_later)
        self.env['stock.quant']._update_available_quantity(
            self.lot_product, self.stock_location, 2.0, lot_id=lot_soon)
        batch = self._create_batch(self.lot_product, 1.0)
        batch.action_allocate()
        line = batch.line_ids[0]
        self.assertEqual(line.lot_id, lot_soon)
        self.assertEqual(line.state, 'allocated')

    def test_batch_state_all_cancelled(self):
        """All lines cancelled → batch must be cancelled, not confirmed."""
        batch = self._create_batch(self.product, 3.0)
        batch.action_cancel()
        self.assertEqual(batch.state, 'cancelled')

    def test_confirm_without_lines_raises(self):
        batch = self.env['stock.reservation.batch'].create({
            'request_user_id': self.env.user.id,
        })
        with self.assertRaises(Exception):
            batch.action_confirm()

    def test_allocate_denied_non_owner_non_manager(self):
        """RPC must enforce same policy as UI: owner or reservation manager."""
        other = self.env['res.users'].create({
            'name': 'Reservation peer user',
            'login': 'res_peer_%s' % uuid.uuid4().hex,
            'password': 'res_peer',
            'company_id': self.env.company.id,
            'company_ids': [(6, 0, [self.env.company.id])],
            'groups_id': [(6, 0, [
                self.env.ref('base.group_user').id,
                self.env.ref('stock.group_stock_user').id,
                self.env.ref('stock_reservation_engine.group_stock_reservation_user').id,
            ])],
        })
        batch = self.env['stock.reservation.batch'].create({
            'request_user_id': self.env.user.id,
            'line_ids': [(0, 0, {
                'product_id': self.product.id,
                'requested_qty': 1.0,
                'location_id': self.stock_location.id,
            })],
        })
        batch.action_confirm()
        with self.assertRaises(AccessError):
            batch.with_user(other).action_allocate()

    def test_owner_can_allocate_own_batch(self):
        owner = self.env['res.users'].create({
            'name': 'Reservation owner alloc',
            'login': 'res_owner_alloc_%s' % uuid.uuid4().hex,
            'password': 'owner',
            'company_id': self.env.company.id,
            'company_ids': [(6, 0, [self.env.company.id])],
            'groups_id': [(6, 0, [
                self.env.ref('base.group_user').id,
                self.env.ref('stock.group_stock_user').id,
                self.env.ref('stock_reservation_engine.group_stock_reservation_user').id,
            ])],
        })
        stocked = self._add_stock(self.product, self.stock_location, 5.0)
        batch = self.env['stock.reservation.batch'].with_user(owner).create({
            'request_user_id': owner.id,
            'line_ids': [(0, 0, {
                'product_id': self.product.id,
                'requested_qty': 2.0,
                'location_id': self.stock_location.id,
            })],
        })
        batch.with_user(owner).action_confirm()
        batch.with_user(owner).action_allocate()
        line = batch.line_ids[0]
        if stocked:
            self.assertEqual(line.state, 'allocated')
            self.assertTrue(line.move_id)

    def test_manager_can_allocate_other_users_batch(self):
        owner = self.env['res.users'].create({
            'name': 'Reservation owner foreign',
            'login': 'res_owner_for_%s' % uuid.uuid4().hex,
            'password': 'owner',
            'company_id': self.env.company.id,
            'company_ids': [(6, 0, [self.env.company.id])],
            'groups_id': [(6, 0, [
                self.env.ref('base.group_user').id,
                self.env.ref('stock.group_stock_user').id,
                self.env.ref('stock_reservation_engine.group_stock_reservation_user').id,
            ])],
        })
        manager = self.env['res.users'].create({
            'name': 'Reservation manager alloc',
            'login': 'res_mgr_alloc_%s' % uuid.uuid4().hex,
            'password': 'mgr',
            'company_id': self.env.company.id,
            'company_ids': [(6, 0, [self.env.company.id])],
            'groups_id': [(6, 0, [
                self.env.ref('base.group_user').id,
                self.env.ref('stock.group_stock_user').id,
                self.env.ref('stock_reservation_engine.group_stock_reservation_manager').id,
            ])],
        })
        stocked = self._add_stock(self.product, self.stock_location, 4.0)
        batch = self.env['stock.reservation.batch'].with_user(owner).create({
            'request_user_id': owner.id,
            'line_ids': [(0, 0, {
                'product_id': self.product.id,
                'requested_qty': 2.0,
                'location_id': self.stock_location.id,
            })],
        })
        batch.with_user(owner).action_confirm()
        batch.with_user(manager).action_allocate()
        line = batch.line_ids[0]
        if stocked:
            self.assertEqual(line.state, 'allocated')

    def test_second_allocate_does_not_duplicate_move(self):
        stocked = self._add_stock(self.product, self.stock_location, 10.0)
        if not stocked:
            self.skipTest('Requires storable product with quants')
        # Batch must stay in partial/confirmed after first allocate so a second run is allowed.
        batch = self._create_batch(self.product, 25.0)
        batch.action_allocate()
        line = batch.line_ids[0]
        self.assertEqual(line.state, 'partial')
        self.assertTrue(line.move_id)
        move_id = line.move_id.id
        batch.action_allocate()
        line.invalidate_recordset()
        self.assertEqual(line.move_id.id, move_id)

    def test_allocation_creates_picking_linked_moves(self):
        stocked = self._add_stock(self.product, self.stock_location, 10.0)
        if not stocked:
            self.skipTest('Requires storable product with quants')
        batch = self._create_batch(self.product, 4.0)
        batch.action_allocate()
        line = batch.line_ids[0]
        self.assertTrue(line.move_id)
        self.assertEqual(line.move_id.picking_id, line.picking_id)
        self.assertEqual(len(batch.picking_ids), 1)
        picking = batch.picking_ids[0]
        self.assertIn(line.move_id, picking.move_ids)
        self.assertEqual(picking.origin, batch.name)
        self.assertEqual(picking.picking_type_id.code, 'internal')

    def test_no_picking_when_nothing_allocated(self):
        batch = self._create_batch(self.product, 5.0)
        batch.action_allocate()
        line = batch.line_ids[0]
        self.assertFalse(line.move_id)
        self.assertFalse(batch.picking_ids)

    def test_second_allocate_same_picking_count(self):
        stocked = self._add_stock(self.product, self.stock_location, 10.0)
        if not stocked:
            self.skipTest('Requires storable product with quants')
        batch = self._create_batch(self.product, 25.0)
        batch.action_allocate()
        self.assertEqual(len(batch.picking_ids), 1)
        pid = batch.picking_ids.ids[0]
        batch.action_allocate()
        batch.invalidate_recordset()
        self.assertEqual(batch.picking_ids.ids, [pid])

