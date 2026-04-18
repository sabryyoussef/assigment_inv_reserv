import logging
from datetime import datetime

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)


class StockReservationBatch(models.Model):
    _name = 'stock.reservation.batch'
    _description = 'Stock Reservation Batch'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(default='New', readonly=True, copy=False, tracking=True)
    request_user_id = fields.Many2one('res.users', required=True, default=lambda self: self.env.user, index=True, tracking=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company, index=True)
    line_ids = fields.One2many('stock.reservation.line', 'batch_id', string='Reservation Lines', copy=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('partial', 'Partial'),
        ('allocated', 'Allocated'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled'),
    ], default='draft', required=True, tracking=True, index=True)
    priority = fields.Selection([
        ('0', 'Low'),
        ('1', 'Normal'),
        ('2', 'High'),
        ('3', 'Urgent'),
    ], default='1', tracking=True)
    scheduled_date = fields.Datetime(tracking=True)
    allocation_in_progress = fields.Boolean(default=False, copy=False)
    move_count = fields.Integer(compute='_compute_move_count')

    def _compute_move_count(self):
        for batch in self:
            batch.move_count = len(batch.line_ids.filtered(lambda l: l.move_id))

    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env['ir.sequence']
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = seq.next_by_code('stock.reservation.batch') or 'New'
        return super().create(vals_list)

    def action_confirm(self):
        for batch in self:
            if not batch.line_ids:
                raise UserError(_('Add at least one reservation line before confirming.'))
            batch.state = 'confirmed'

    def action_cancel(self):
        for batch in self:
            batch.line_ids.filtered(lambda l: l.state != 'allocated').write({'state': 'cancelled'})
            batch.state = 'cancelled'

    def action_mark_done(self):
        for batch in self:
            batch.state = 'done'

    def _check_allocate_authorization(self):
        """Server-side gate: reservation manager OR batch owner may allocate."""
        self.ensure_one()
        if self.env.user.has_group('stock_reservation_engine.group_stock_reservation_manager'):
            return
        if self.request_user_id == self.env.user:
            return
        raise AccessError(_(
            'Only the reservation owner or a Stock Reservation Manager can allocate this batch.'
        ))

    def action_allocate(self):
        for batch in self:
            batch._check_allocate_authorization()
            batch._action_allocate_single()
        return True

    def _action_allocate_single(self):
        self.ensure_one()
        if self.allocation_in_progress:
            raise UserError(_('Allocation is already in progress for this batch.'))
        if self.state not in ['draft', 'confirmed', 'partial']:
            raise UserError(_('This reservation batch cannot be allocated in its current state.'))
        if not self.line_ids:
            raise UserError(_('There are no reservation lines to allocate.'))

        _logger.info(
            'Allocation start batch=%s user=%s id=%s',
            self.name, self.env.user.login, self.env.user.id,
        )
        self.write({'allocation_in_progress': True})
        try:
            for line in self.line_ids:
                # Fully allocated lines with a move: skip (no duplicate moves)
                if line.state == 'allocated' and line.move_id:
                    continue

                allocation_result = self._allocate_line(line)
                allocated = allocation_result.get('allocated_qty', 0.0)
                chosen_lot = allocation_result.get('lot_id')
                line.write({
                    'allocated_qty': allocated,
                    'state': self._compute_line_state(line.requested_qty, allocated),
                    'lot_id': chosen_lot,
                })
                # One move per line; refresh qty if re-running allocation on partial lines
                if allocated > 0:
                    if line.move_id:
                        line.move_id.write({'product_uom_qty': allocated})
                    else:
                        move = self._create_stock_move_for_line(line)
                        line.move_id = move.id
            self._compute_batch_state()
            _logger.info(
                'Allocation end batch=%s state=%s lines=%s moves=%s',
                self.name,
                self.state,
                len(self.line_ids),
                len(self.line_ids.filtered('move_id')),
            )
        finally:
            self.write({'allocation_in_progress': False})

    def _allocate_line(self, line):
        self.ensure_one()
        remaining = line.requested_qty
        allocated = 0.0
        lot_id = False

        domain = [
            ('product_id', '=', line.product_id.id),
            ('location_id', 'child_of', line.location_id.id),
            ('quantity', '>', 0),
            ('company_id', '=', self.company_id.id),
        ]
        if line.lot_id:
            domain.append(('lot_id', '=', line.lot_id.id))

        use_fefo = self._get_quant_order(line)
        quants = self.env['stock.quant'].search(domain, order='in_date asc, id asc')
        if use_fefo:
            quants = quants.sorted(
                key=lambda q: (
                    q.lot_id.expiration_date if (q.lot_id and q.lot_id.expiration_date) else datetime.max,
                    q.in_date or datetime.min,
                    q.id,
                )
            )

        for quant in quants:
            if remaining <= 0:
                break
            available = quant.quantity - quant.reserved_quantity
            if available <= 0:
                continue
            take = min(available, remaining)
            if take > 0:
                allocated += take
                remaining -= take
                if quant.lot_id and not lot_id:
                    lot_id = quant.lot_id.id

        return {
            'allocated_qty': allocated,
            'lot_id': lot_id,
        }

    def _get_quant_order(self, line):
        self.ensure_one()
        Quant = self.env['stock.quant']
        domain = [
            ('product_id', '=', line.product_id.id),
            ('location_id', 'child_of', line.location_id.id),
            ('quantity', '>', 0),
            ('company_id', '=', self.company_id.id),
            ('lot_id', '!=', False),
        ]
        if line.lot_id:
            domain.append(('lot_id', '=', line.lot_id.id))
        quant_with_expiry = Quant.search(domain, limit=1).filtered(lambda q: q.lot_id and q.lot_id.expiration_date)
        return bool(quant_with_expiry)

    def _compute_line_state(self, requested_qty, allocated_qty):
        if allocated_qty <= 0:
            return 'not_available'
        if allocated_qty < requested_qty:
            return 'partial'
        return 'allocated'

    def _compute_batch_state(self):
        for batch in self:
            states = batch.line_ids.mapped('state')
            if not states:
                batch.state = 'draft'
            elif all(state == 'cancelled' for state in states):
                batch.state = 'cancelled'
            elif all(state == 'allocated' for state in states):
                batch.state = 'allocated'
            elif any(state in ['partial', 'not_available'] for state in states):
                batch.state = 'partial'
            else:
                batch.state = 'confirmed'

    def _create_stock_move_for_line(self, line):
        self.ensure_one()
        if line.allocated_qty <= 0:
            raise UserError(_('Cannot generate a stock move for zero allocated quantity.'))
        output_location = self.env.ref('stock.stock_location_output', raise_if_not_found=False)
        if not output_location:
            raise UserError(_(
                'The output location (stock.stock_location_output) was not found. '
                'Please ensure the stock module is properly configured.'
            ))
        dest_location = output_location.id
        return self.env['stock.move'].create({
            'name': _('Reservation %s') % self.name,
            'company_id': self.company_id.id,
            'product_id': line.product_id.id,
            'product_uom': line.product_id.uom_id.id,
            'product_uom_qty': line.allocated_qty,
            'location_id': line.location_id.id,
            'location_dest_id': dest_location,
            'origin': self.name,
            'reference': self.name,
        })

    def action_view_moves(self):
        self.ensure_one()
        moves = self.line_ids.mapped('move_id')
        action = self.env.ref('stock.action_moves_all').read()[0]
        action['domain'] = [('id', 'in', moves.ids)]
        action['context'] = dict(self.env.context, create=False)
        return action
