from odoo import api, fields, models
from odoo.exceptions import ValidationError


class StockReservationLine(models.Model):
    _name = 'stock.reservation.line'
    _description = 'Stock Reservation Line'
    _order = 'id'

    batch_id = fields.Many2one('stock.reservation.batch', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='batch_id.company_id', store=True, index=True)
    request_user_id = fields.Many2one(related='batch_id.request_user_id', store=True, index=True)
    product_id = fields.Many2one('product.product', required=True, index=True)
    requested_qty = fields.Float(required=True, digits='Product Unit of Measure')
    allocated_qty = fields.Float(default=0.0, digits='Product Unit of Measure')
    location_id = fields.Many2one('stock.location', required=True, index=True)
    lot_id = fields.Many2one('stock.lot', string='Preferred Lot', index=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('not_available', 'Not Available'),
        ('partial', 'Partial'),
        ('allocated', 'Allocated'),
        ('cancelled', 'Cancelled'),
    ], default='draft', required=True, index=True)
    move_id = fields.Many2one('stock.move', string='Generated Move', readonly=True, copy=False, index=True)
    picking_id = fields.Many2one(
        related='move_id.picking_id',
        string='Transfer',
        readonly=True,
    )
    note = fields.Char()

    _sql_constraints = [
        ('requested_qty_positive', 'CHECK(requested_qty > 0)', 'Requested quantity must be greater than zero.'),
        ('allocated_qty_non_negative', 'CHECK(allocated_qty >= 0)', 'Allocated quantity cannot be negative.'),
    ]

    @api.constrains('allocated_qty', 'requested_qty')
    def _check_allocated_qty(self):
        for line in self:
            if line.allocated_qty > line.requested_qty:
                raise ValidationError('Allocated quantity cannot exceed requested quantity.')
