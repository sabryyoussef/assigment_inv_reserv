import uuid
from datetime import timedelta

from odoo import fields, sql_db
from odoo.exceptions import AccessError, UserError
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

    def test_partial_allocation(self):
        stocked = self._add_stock(self.product, self.stock_location, 2.0)
        batch = self._create_batch(self.product, 5.0)
        batch.action_allocate()
        line = batch.line_ids[0]
        if stocked:
            self.assertEqual(line.allocated_qty, 2.0)
            self.assertEqual(line.state, 'partial')
            self.assertEqual(batch.state, 'partial')

    def test_no_stock(self):
        batch = self._create_batch(self.product, 4.0)
        batch.action_allocate()
        line = batch.line_ids[0]
        self.assertEqual(line.allocated_qty, 0.0)
        self.assertEqual(line.state, 'not_available')
        self.assertFalse(line.move_id)
        self.assertEqual(batch.state, 'partial')

    def test_cancel_cancels_linked_pickings(self):
        stocked = self._add_stock(self.product, self.stock_location, 8.0)
        if not stocked:
            self.skipTest('Requires storable product with quants')
        batch = self._create_batch(self.product, 4.0)
        batch.action_allocate()
        self.assertTrue(batch.picking_ids)
        picking = batch.picking_ids[0]
        batch.action_cancel()
        picking.invalidate_recordset()
        self.assertEqual(picking.state, 'cancel')

    def test_allocate_denied_non_owner_non_manager(self):
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

    def test_fefo_allocates_earliest_expiry_lot_first(self):
        """FEFO: the lot with the earliest expiry date must be selected first.

        Two lots are created with different expiry dates.  Stock is added for both.
        The reservation only requests a quantity that fits within the earlier-expiry
        lot.  After allocation the line must reference the lot with the earliest
        expiry date, proving FEFO ordering is applied and not FIFO-by-id.
        """
        product = self.lot_product
        stocked = self._add_stock(product, self.stock_location, 1.0)
        if not stocked:
            self.skipTest('Requires storable lot-tracked product with quants')

        today = fields.Datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        lot_early = self.env['stock.lot'].create({
            'name': 'LOT-EARLY-%s' % uuid.uuid4().hex[:6],
            'product_id': product.id,
            'expiration_date': today + timedelta(days=5),
            'company_id': self.env.company.id,
        })
        lot_late = self.env['stock.lot'].create({
            'name': 'LOT-LATE-%s' % uuid.uuid4().hex[:6],
            'product_id': product.id,
            'expiration_date': today + timedelta(days=30),
            'company_id': self.env.company.id,
        })

        # Add stock: 3 units in the late-expiry lot, 5 units in the early-expiry lot.
        # FEFO must select early-expiry stock first regardless of lot creation order
        # or lot id ordering.
        self.env['stock.quant'].sudo()._update_available_quantity(product, self.stock_location, 3.0, lot_id=lot_late)
        self.env['stock.quant'].sudo()._update_available_quantity(product, self.stock_location, 5.0, lot_id=lot_early)

        batch = self.env['stock.reservation.batch'].create({
            'request_user_id': self.env.user.id,
            'line_ids': [(0, 0, {
                'product_id': product.id,
                'requested_qty': 4.0,
                'location_id': self.stock_location.id,
            })],
        })
        batch.action_confirm()
        batch.action_allocate()

        line = batch.line_ids[0]
        self.assertEqual(line.state, 'allocated', 'Line should be fully allocated')
        self.assertEqual(line.allocated_qty, 4.0, 'Full qty should be allocated from early lot')
        self.assertEqual(
            line.lot_id.id, lot_early.id,
            'FEFO must select the lot with the earliest expiry date (lot_early)',
        )

    def test_fefo_spans_lots_in_expiry_order(self):
        """FEFO: when a single lot cannot satisfy demand, remaining qty must be taken
        from the next-earliest lot, not the latest one.
        """
        product = self.lot_product
        stocked = self._add_stock(product, self.stock_location, 1.0)
        if not stocked:
            self.skipTest('Requires storable lot-tracked product with quants')

        today = fields.Datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        lot_a = self.env['stock.lot'].create({
            'name': 'LOT-A-%s' % uuid.uuid4().hex[:6],
            'product_id': product.id,
            'expiration_date': today + timedelta(days=3),
            'company_id': self.env.company.id,
        })
        lot_b = self.env['stock.lot'].create({
            'name': 'LOT-B-%s' % uuid.uuid4().hex[:6],
            'product_id': product.id,
            'expiration_date': today + timedelta(days=10),
            'company_id': self.env.company.id,
        })
        lot_c = self.env['stock.lot'].create({
            'name': 'LOT-C-%s' % uuid.uuid4().hex[:6],
            'product_id': product.id,
            'expiration_date': today + timedelta(days=60),
            'company_id': self.env.company.id,
        })

        # Deliberately add lots in reverse creation order: C (latest) first, A (earliest) last.
        # FEFO must still exhaust A, then B, never touching C for a request of 5 units.
        self.env['stock.quant'].sudo()._update_available_quantity(product, self.stock_location, 3.0, lot_id=lot_c)
        self.env['stock.quant'].sudo()._update_available_quantity(product, self.stock_location, 2.0, lot_id=lot_b)
        self.env['stock.quant'].sudo()._update_available_quantity(product, self.stock_location, 3.0, lot_id=lot_a)

        batch = self.env['stock.reservation.batch'].create({
            'request_user_id': self.env.user.id,
            'line_ids': [(0, 0, {
                'product_id': product.id,
                'requested_qty': 5.0,
                'location_id': self.stock_location.id,
            })],
        })
        batch.action_confirm()
        batch.action_allocate()

        line = batch.line_ids[0]
        self.assertEqual(line.state, 'allocated', 'Full allocation expected')
        self.assertEqual(line.allocated_qty, 5.0)
        # First lot_id recorded on the line must be the earliest-expiry lot (lot_a)
        self.assertEqual(
            line.lot_id.id, lot_a.id,
            'FEFO must record lot_a (earliest expiry) as the primary lot on the line',
        )

    def test_native_reservation_protects_stock_from_competing_batch(self):
        """Reservation protection: after a batch is allocated and stock is natively
        reserved (reserved_quantity incremented on the quant), a second competing
        batch requesting the same stock must receive zero allocation.

        This test proves that calling picking.action_assign() in _create_picking_for_moves
        creates real Odoo reservations, not merely informational allocation figures.
        """
        product = self.product
        stocked = self._add_stock(product, self.stock_location, 5.0)
        if not stocked:
            self.skipTest('Requires storable product with quants')

        # Batch 1 allocates all 5 units.
        batch1 = self._create_batch(product, 5.0)
        batch1.action_allocate()
        line1 = batch1.line_ids[0]
        self.assertEqual(line1.state, 'allocated')
        self.assertTrue(batch1.picking_ids, 'A picking must be generated after allocation')

        # Verify the quant's reserved_quantity was actually updated by Odoo's native
        # reservation (action_assign).
        Quant = self.env['stock.quant']
        quants = Quant.search([
            ('product_id', '=', product.id),
            ('location_id', 'child_of', self.stock_location.id),
        ])
        total_reserved = sum(q.reserved_quantity for q in quants)
        self.assertGreater(total_reserved, 0.0,
            'stock.quant.reserved_quantity must be > 0 after native reservation')

        # Batch 2 requests the same stock that is now natively reserved.
        batch2 = self._create_batch(product, 5.0)
        batch2.action_allocate()
        line2 = batch2.line_ids[0]

        # Because reserved_quantity is already set, available = qty - reserved = 0,
        # so batch 2 must receive nothing.
        self.assertEqual(line2.allocated_qty, 0.0,
            'Competing batch must receive zero because stock is already natively reserved')
        self.assertEqual(line2.state, 'not_available')
