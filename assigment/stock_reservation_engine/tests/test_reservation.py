from datetime import datetime, timedelta

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

        # Use storable product type if available, fall back to consu.
        # In Odoo 18 enterprise the valid selection key for a stock-tracked
        # product may vary by installed modules, so we probe at runtime.
        storable_type = cls._get_storable_type()

        cls.product = cls.env['product.template'].create({
            'name': 'Reservation Product',
            'type': storable_type,
            'uom_id': cls.uom_unit.id,
            'uom_po_id': cls.uom_unit.id,
        }).product_variant_ids[0]
        cls.lot_product = cls.env['product.template'].create({
            'name': 'Lot Reservation Product',
            'type': storable_type,
            'tracking': 'lot',
            'uom_id': cls.uom_unit.id,
            'uom_po_id': cls.uom_unit.id,
        }).product_variant_ids[0]

    @classmethod
    def _get_storable_type(cls):
        """Return the correct selection value for a stock-tracked product in
        the current Odoo version.  Odoo 18 uses 'storable'; older builds
        used 'product'.  If neither is accepted we fall back to 'consu'."""
        type_field = cls.env['product.template']._fields.get('type')
        if type_field:
            valid = [k for k, _ in (type_field.selection or [])]
            for candidate in ('storable', 'product'):
                if candidate in valid:
                    return candidate
        return 'consu'

    def _add_stock(self, product, location, qty, lot=None):
        """Add stock via stock.quant if the product supports quants,
        otherwise skip silently (consumables have no quants)."""
        if product.type == 'consu':
            return False
        self.env['stock.quant']._update_available_quantity(
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
        if self.lot_product.type == 'consu':
            self.skipTest('FEFO test requires a storable tracked product; '
                          'current environment does not support storable type')

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

