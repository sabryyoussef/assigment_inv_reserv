import uuid
from datetime import datetime, timedelta

from odoo.exceptions import AccessError, UserError

from odoo import sql_db
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
