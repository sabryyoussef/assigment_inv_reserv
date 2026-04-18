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
        cls.product = cls.env['product.product'].create({
            'name': 'Reservation Product',
            'type': 'product',
            'uom_id': cls.uom_unit.id,
            'uom_po_id': cls.uom_unit.id,
        })
        cls.lot_product = cls.env['product.product'].create({
            'name': 'Lot Reservation Product',
            'type': 'product',
            'tracking': 'lot',
            'uom_id': cls.uom_unit.id,
            'uom_po_id': cls.uom_unit.id,
        })

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
        self.env['stock.quant']._update_available_quantity(self.product, self.stock_location, 10.0)
        batch = self._create_batch(self.product, 6.0)
        batch.action_allocate()
        line = batch.line_ids[0]
        self.assertEqual(line.allocated_qty, 6.0)
        self.assertEqual(line.state, 'allocated')
        self.assertTrue(line.move_id)
        self.assertEqual(batch.state, 'allocated')

    def test_partial_allocation(self):
        self.env['stock.quant']._update_available_quantity(self.product, self.stock_location, 2.0)
        batch = self._create_batch(self.product, 5.0)
        batch.action_allocate()
        line = batch.line_ids[0]
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

    def test_fefo_preferred_lot(self):
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
        self.env['stock.quant']._update_available_quantity(self.lot_product, self.stock_location, 2.0, lot_id=lot_later)
        self.env['stock.quant']._update_available_quantity(self.lot_product, self.stock_location, 2.0, lot_id=lot_soon)
        batch = self._create_batch(self.lot_product, 1.0)
        batch.action_allocate()
        line = batch.line_ids[0]
        self.assertEqual(line.lot_id, lot_soon)
        self.assertEqual(line.state, 'allocated')
