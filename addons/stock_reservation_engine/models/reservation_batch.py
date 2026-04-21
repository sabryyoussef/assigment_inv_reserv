import logging
import time
from datetime import datetime

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools.float_utils import float_is_zero

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
    picking_ids = fields.Many2many(
        'stock.picking',
        'stock_reservation_batch_picking_rel',
        'batch_id',
        'picking_id',
        string='Transfers',
        copy=False,
        help='Internal transfers linked to this reservation batch.',
    )
    picking_count = fields.Integer(compute='_compute_picking_count', string='Transfer Count')
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

    @api.depends('picking_ids')
    def _compute_picking_count(self):
        for batch in self:
            batch.picking_count = len(batch.picking_ids)

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
            pickings = batch.picking_ids.filtered(lambda p: p.state not in ('cancel', 'done'))
            if pickings:
                pickings.action_cancel()

            moves = batch.line_ids.mapped('move_id').filtered(lambda m: m.state not in ('cancel', 'done'))
            orphan_moves = moves.filtered(lambda m: not m.picking_id or m.picking_id.state == 'cancel')
            if orphan_moves:
                cancel_method = getattr(orphan_moves, '_action_cancel', None) or getattr(orphan_moves, 'action_cancel', None)
                if cancel_method:
                    cancel_method()

            batch.line_ids.write({'state': 'cancelled'})
            batch.write({
                'state': 'cancelled',
                'allocation_in_progress': False,
            })

    def action_mark_done(self):
        for batch in self:
            batch.state = 'done'

    def _check_allocate_authorization(self):
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

    def _is_lock_conflict_error(self, exc):
        seen = set()
        current = exc
        while current and id(current) not in seen:
            seen.add(id(current))
            if getattr(current, 'pgcode', None) == '55P03':
                return True
            if current.__class__.__name__ == 'LockNotAvailable':
                return True
            message = str(current).lower()
            if 'could not obtain lock on row' in message or 'lock not available' in message:
                return True
            current = getattr(current, '__cause__', None) or getattr(current, '__context__', None)
        return False

    def _lock_rows_nowait(self, table_name, ids, user_message):
        ids = sorted({int(rec_id) for rec_id in ids if rec_id})
        if not ids:
            return
        try:
            with self.env.cr.savepoint():
                self.env.cr.execute(
                    'SELECT id FROM %s WHERE id IN %%s ORDER BY id FOR UPDATE NOWAIT' % table_name,
                    [tuple(ids)],
                )
        except Exception as exc:
            if self._is_lock_conflict_error(exc):
                raise UserError(user_message) from exc
            raise

    def _get_line_quant_domain(self, line):
        self.ensure_one()
        domain = [
            ('product_id', '=', line.product_id.id),
            ('location_id', 'child_of', line.location_id.id),
            ('quantity', '>', 0),
            ('company_id', '=', self.company_id.id),
        ]
        if line.lot_id:
            domain.append(('lot_id', '=', line.lot_id.id))
        return domain

    def _lock_candidate_quants_nowait(self):
        self.ensure_one()
        Quant = self.env['stock.quant']
        quant_ids = set()
        for line in self.line_ids:
            if line.state == 'allocated' and line.move_id:
                continue
            quant_ids.update(Quant.search(self._get_line_quant_domain(line), order='id asc').ids)
        self._lock_rows_nowait(
            'stock_quant',
            quant_ids,
            _('Some stock quantities are currently being allocated by another user. Please try again in a moment.'),
        )

    def _action_allocate_single(self):
        self.ensure_one()
        self._lock_rows_nowait(
            self._table,
            self.ids,
            _('This reservation batch is already being allocated by another user. Please try again in a moment.'),
        )
        self.invalidate_recordset()
        if self.allocation_in_progress:
            raise UserError(_('Allocation is already in progress for this batch.'))
        if self.state not in ['draft', 'confirmed', 'partial']:
            raise UserError(_('This reservation batch cannot be allocated in its current state.'))
        if not self.line_ids:
            raise UserError(_('There are no reservation lines to allocate.'))

        _logger.info(
            'Starting allocation for reservation batch %s user=%s id=%s',
            self.name, self.env.user.login, self.env.user.id,
        )
        self.write({'allocation_in_progress': True})
        try:
            self._lock_candidate_quants_nowait()
            batch_t0 = time.perf_counter()
            for line in self.line_ids:
                if line.state == 'allocated' and line.move_id:
                    continue

                line_t0 = time.perf_counter()
                allocation_result = self._allocate_line(line)
                allocated = allocation_result.get('allocated_qty', 0.0)
                chosen_lot = allocation_result.get('lot_id')
                line.write({
                    'allocated_qty': allocated,
                    'state': self._compute_line_state(line.requested_qty, allocated),
                    'lot_id': chosen_lot,
                })
                if allocated > 0:
                    if line.move_id:
                        line.move_id.write({'product_uom_qty': allocated})
                    else:
                        move = self._create_stock_move_for_line(line)
                        line.move_id = move.id
                line_elapsed_ms = (time.perf_counter() - line_t0) * 1000.0
                _logger.info(
                    'Allocation line timing batch=%s line_id=%s product_id=%s elapsed_ms=%.2f allocated_qty=%s',
                    self.name,
                    line.id,
                    line.product_id.id,
                    line_elapsed_ms,
                    allocated,
                )
            self._compute_batch_state()
            total_elapsed_ms = (time.perf_counter() - batch_t0) * 1000.0
            _logger.info(
                'Finished allocation for reservation batch %s state=%s lines=%s moves=%s total_elapsed_ms=%.2f',
                self.name,
                self.state,
                len(self.line_ids),
                len(self.line_ids.filtered('move_id')),
                total_elapsed_ms,
            )
            self._generate_pickings_from_allocated_moves()
        finally:
            self.write({'allocation_in_progress': False})

    def _allocate_line(self, line):
        """Compute the intended allocation for a single line from available quant stock.

        FEFO detection is derived from the quants already fetched (no extra DB query).
        Lot expiry dates are prefetched in one query before sorting to avoid N+1 reads
        inside the sort key lambda.
        """
        self.ensure_one()
        remaining = line.requested_qty
        allocated = 0.0
        lot_id = False

        domain = self._get_line_quant_domain(line)
        quants = self.env['stock.quant'].search(domain, order='in_date asc, id asc')

        if quants:
            # Prefetch all related lot records (including expiration_date) in a single
            # query.  Without this, the sort key lambda would trigger one DB read per
            # unique lot, causing an N+1 pattern as the recordset is iterated.
            # NOTE: result is intentionally discarded — the purpose is ORM cache warming.
            quants.lot_id.mapped('expiration_date')

            # Detect FEFO from already-loaded quant data — no separate DB round-trip.
            use_fefo = any(q.lot_id and q.lot_id.expiration_date for q in quants)
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
            elif all(state in ['allocated', 'cancelled'] for state in states):
                batch.state = 'allocated'
            elif all(state == 'allocated' for state in states):
                batch.state = 'allocated'
            elif any(state in ['partial', 'not_available'] for state in states):
                batch.state = 'partial'
            else:
                batch.state = 'confirmed'

    def _resolve_warehouse_for_line(self, line):
        self.ensure_one()
        loc = line.location_id
        wh = loc.warehouse_id
        if wh:
            return wh
        return self.env['stock.warehouse'].search([
            ('company_id', '=', self.company_id.id),
        ], limit=1)

    def _get_reservation_destination_location(self, line):
        self.ensure_one()
        warehouse = self._resolve_warehouse_for_line(line)
        if warehouse and warehouse.wh_pack_stock_loc_id:
            return warehouse.wh_pack_stock_loc_id
        PickingType = self.env['stock.picking.type']
        ptype = PickingType.search([
            ('company_id', '=', self.company_id.id),
            ('code', '=', 'internal'),
        ], limit=1)
        if ptype.default_location_dest_id:
            return ptype.default_location_dest_id
        raise UserError(_(
            'Cannot resolve a staging destination location for reservation moves. '
            'Configure a warehouse Packing Location or an Internal operation type with a default destination.'
        ))

    def _get_internal_picking_type(self, warehouse):
        self.ensure_one()
        PickingType = self.env['stock.picking.type']
        if warehouse:
            ptype = PickingType.search([
                ('warehouse_id', '=', warehouse.id),
                ('company_id', '=', self.company_id.id),
                ('code', '=', 'internal'),
            ], limit=1)
            if ptype:
                return ptype
        return PickingType.search([
            ('company_id', '=', self.company_id.id),
            ('code', '=', 'internal'),
        ], limit=1)

    def _group_moves_for_pickings(self, moves):
        buckets = {}
        for move in moves:
            key = (move.location_id.id, move.location_dest_id.id)
            buckets.setdefault(key, self.env['stock.move'])
            buckets[key] |= move
        return list(buckets.values())

    def _create_picking_for_moves(self, moves):
        self.ensure_one()
        moves = moves.filtered(lambda m: m.state != 'cancel')
        if not moves:
            return self.env['stock.picking']

        warehouse = moves[0].location_id.warehouse_id or self.env['stock.warehouse'].search([
            ('company_id', '=', self.company_id.id),
        ], limit=1)
        pick_type = self._get_internal_picking_type(warehouse)
        if not pick_type:
            raise UserError(_(
                'No Internal transfer operation type found for company %(company)s.',
                company=self.company_id.display_name,
            ))

        src_loc = moves[0].location_id
        dest_loc = moves[0].location_dest_id
        if any(m.location_id != src_loc or m.location_dest_id != dest_loc for m in moves):
            raise UserError(_('Grouped moves must share the same source and destination locations.'))

        picking_vals = {
            'picking_type_id': pick_type.id,
            'location_id': src_loc.id,
            'location_dest_id': dest_loc.id,
            'origin': self.name,
            'company_id': self.company_id.id,
        }
        picking = self.env['stock.picking'].create(picking_vals)
        if self.scheduled_date:
            picking.scheduled_date = self.scheduled_date
        moves.write({'picking_id': picking.id})
        picking.action_confirm()
        # Trigger Odoo-native stock reservation: increments stock.quant.reserved_quantity
        # and creates stock.move.line records so competing operations cannot claim the
        # same stock.  This is the key step that turns our pre-allocation into a hard
        # reservation enforced by Odoo's inventory engine.
        picking.action_assign()
        return picking

    def _sync_allocated_qty_from_moves(self):
        """Reconcile allocated_qty on lines with Odoo's actual reserved quantities.

        After calling picking.action_assign(), Odoo updates stock.quant.reserved_quantity
        and creates stock.move.line records.  The quantity that was actually reserved may
        differ from what _allocate_line computed (e.g. if another transaction reserved some
        stock between our quant scan and the native assignment).  Reading back from
        move_line_ids ensures allocated_qty truthfully reflects what is protected.
        """
        for line in self.line_ids:
            if not line.move_id:
                continue
            actual = sum(ml.quantity for ml in line.move_id.move_line_ids)
            if actual != line.allocated_qty:
                line.write({
                    'allocated_qty': actual,
                    'state': self._compute_line_state(line.requested_qty, actual),
                })

    def _generate_pickings_from_allocated_moves(self):
        self.ensure_one()
        moves = self.line_ids.mapped('move_id').filtered(
            lambda m: m and not float_is_zero(
                m.product_uom_qty,
                precision_rounding=m.product_uom.rounding or m.product_id.uom_id.rounding,
            )
        )
        todo = moves.filtered(lambda m: not m.picking_id)
        if not todo:
            return

        pickings = self.env['stock.picking']
        for group in self._group_moves_for_pickings(todo):
            picking = self._create_picking_for_moves(group)
            pickings |= picking

        if pickings:
            self.write({'picking_ids': [(4, p.id) for p in pickings]})

        # Reconcile allocated_qty with what Odoo's assignment engine actually reserved.
        # This keeps the custom allocation figures honest when native availability differs
        # from the pre-allocation scan (e.g. due to concurrent transactions).
        self._sync_allocated_qty_from_moves()

    def _create_stock_move_for_line(self, line):
        self.ensure_one()
        if line.allocated_qty <= 0:
            raise UserError(_('Cannot generate a stock move for zero allocated quantity.'))
        dest_location = self._get_reservation_destination_location(line)
        return self.env['stock.move'].create({
            'name': _('Reservation %s') % self.name,
            'company_id': self.company_id.id,
            'product_id': line.product_id.id,
            'product_uom': line.product_id.uom_id.id,
            'product_uom_qty': line.allocated_qty,
            'location_id': line.location_id.id,
            'location_dest_id': dest_location.id,
            'origin': self.name,
            'reference': self.name,
        })

    def action_view_moves(self):
        self.ensure_one()
        moves = self.line_ids.mapped('move_id')
        return {
            'type': 'ir.actions.act_window',
            'name': _('Stock Moves'),
            'res_model': 'stock.move',
            'view_mode': 'list,form',
            'domain': [('id', 'in', moves.ids)],
            'context': dict(self.env.context, create=False),
        }

    def action_view_pickings(self):
        self.ensure_one()
        pickings = self.picking_ids
        action = self.env['ir.actions.act_window']._for_xml_id('stock.action_picking_tree_all')
        action['domain'] = [('id', 'in', pickings.ids)]
        action['context'] = dict(self.env.context, create=False)
        return action
