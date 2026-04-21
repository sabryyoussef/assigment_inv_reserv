import hashlib
import logging

from odoo import http
from odoo.exceptions import AccessError, UserError
from odoo.http import request

_logger = logging.getLogger(__name__)


class ReservationAPI(http.Controller):

    _ERR_UNAUTHORIZED = 'ERR_UNAUTHORIZED'
    _ERR_VALIDATION = 'ERR_VALIDATION'
    _ERR_FORBIDDEN = 'ERR_FORBIDDEN'
    _ERR_NOT_FOUND = 'ERR_NOT_FOUND'
    _ERR_CONFLICT = 'ERR_CONFLICT'
    _ERR_INTERNAL = 'ERR_INTERNAL'

    def _json_error(self, message, status=400, code='ERR_VALIDATION'):
        payload = {'status': 'error', 'message': message, 'code': code}
        return request.make_json_response(payload, status=status)

    def _json_fail(self, message, code='ERR_VALIDATION'):
        """Consistent body for type=json routes (inside JSON-RPC result)."""
        return {'status': 'error', 'message': message, 'code': code}

    def _json_ok(self, data):
        return {'status': 'success', 'data': data}

    def _get_bearer_token(self):
        header = (request.httprequest.headers.get('Authorization') or '').strip()
        if not header:
            return None
        parts = header.split(None, 1)
        if len(parts) != 2 or parts[0].lower() != 'bearer':
            return None
        return parts[1].strip() or None

    def _authenticate(self):
        token_value = self._get_bearer_token()
        if not token_value:
            return None
        token_hash = hashlib.sha256(token_value.encode()).hexdigest()
        token = request.env['reservation.api.token'].sudo().search([
            ('token', '=', token_hash),
            ('active', '=', True),
        ], limit=1)
        if not token:
            return None
        row = token.sudo().read(['user_id'])
        if not row or not row[0].get('user_id'):
            return None
        uid = row[0]['user_id'][0]
        return request.env['res.users'].sudo().browse(uid).exists()

    def _validate_priority(self, priority):
        if priority in (None, False, ''):
            return '1'
        priority = str(priority)
        if priority not in {'0', '1', '2', '3'}:
            raise UserError('priority must be one of 0, 1, 2, or 3.')
        return priority

    def _prepare_line_commands(self, lines):
        if not isinstance(lines, list) or not lines:
            raise UserError('At least one line is required.')

        line_commands = []
        for item in lines:
            if not isinstance(item, dict):
                raise UserError('Each line must be an object.')

            product_id = item.get('product_id')
            qty = item.get('qty') if item.get('qty') is not None else item.get('requested_qty')
            location_id = item.get('location_id')
            lot_id = item.get('lot_id')

            if not product_id or not location_id or qty in (None, False, ''):
                raise UserError('Each line must include product_id, qty, and location_id.')

            try:
                product_id = int(product_id)
                location_id = int(location_id)
                qty = float(qty)
                if lot_id not in (None, False, ''):
                    lot_id = int(lot_id)
            except (TypeError, ValueError) as exc:
                raise UserError('Line values must use valid numeric identifiers and quantity.') from exc

            if qty <= 0:
                raise UserError('Quantity must be greater than zero.')

            line_commands.append((0, 0, {
                'product_id': product_id,
                'requested_qty': qty,
                'location_id': location_id,
                'lot_id': lot_id or False,
            }))
        return line_commands

    def _parse_batch_id(self, batch_id):
        if batch_id in (None, False, ''):
            raise UserError('batch_id is required.')
        try:
            batch_id = int(batch_id)
        except (TypeError, ValueError) as exc:
            raise UserError('batch_id must be a positive integer.') from exc
        if batch_id <= 0:
            raise UserError('batch_id must be a positive integer.')
        return batch_id

    @http.route([
        '/api/reservation/create',
        '/api/v1/reservation/create',
    ], type='json', auth='none', methods=['POST'], csrf=False)
    def create_reservation(self, **payload):
        user = self._authenticate()
        if not user:
            return self._json_fail('Unauthorized', code=self._ERR_UNAUTHORIZED)
        try:
            line_commands = self._prepare_line_commands(payload.get('lines'))
            # Use the authenticated user's own environment (no privilege escalation).
            # su=True was previously set here, which bypassed all access control checks.
            # Normal group-based rules now apply, keeping the permission boundary intact.
            env_u = request.env(user=user.id)
            company = user.company_id or env_u['res.company'].search([], limit=1)
            batch = env_u['stock.reservation.batch'].create({
                'company_id': company.id,
                'request_user_id': user.id,
                'priority': self._validate_priority(payload.get('priority')),
                'scheduled_date': payload.get('scheduled_date'),
                'line_ids': line_commands,
            })
            if payload.get('auto_confirm', True):
                batch.with_user(user).action_confirm()
            return self._json_ok({
                'batch_id': batch.id,
                'name': batch.name,
                'state': batch.state,
            })
        except AccessError as exc:
            return self._json_fail(str(exc), code=self._ERR_FORBIDDEN)
        except UserError as exc:
            return self._json_fail(str(exc), code=self._ERR_VALIDATION)
        except Exception:
            _logger.exception('Unexpected error while creating reservation via API')
            return self._json_fail('Unexpected server error.', code=self._ERR_INTERNAL)

    @http.route([
        '/api/reservation/allocate',
        '/api/v1/reservation/allocate',
    ], type='json', auth='none', methods=['POST'], csrf=False)
    def allocate_reservation(self, **payload):
        user = self._authenticate()
        if not user:
            return self._json_fail('Unauthorized', code=self._ERR_UNAUTHORIZED)
        try:
            batch_id = self._parse_batch_id(payload.get('batch_id'))
            batch = request.env['stock.reservation.batch'].sudo().browse(batch_id)
            if not batch.exists():
                return self._json_fail('Reservation batch not found.', code=self._ERR_NOT_FOUND)
            if batch.request_user_id != user and not user.has_group('stock_reservation_engine.group_stock_reservation_manager'):
                return self._json_fail('Access denied.', code=self._ERR_FORBIDDEN)
            batch.with_user(user).action_allocate()
            return self._json_ok({
                'batch_id': batch.id,
                'name': batch.name,
                'state': batch.state,
            })
        except AccessError as exc:
            return self._json_fail(str(exc), code=self._ERR_FORBIDDEN)
        except UserError as exc:
            # Distinguish concurrency/lock conflicts from ordinary validation errors so
            # API clients can implement retry logic without treating every UserError as a
            # permanent failure.
            msg = str(exc)
            if 'already being allocated' in msg or 'try again' in msg.lower():
                return self._json_fail(msg, code=self._ERR_CONFLICT)
            return self._json_fail(msg, code=self._ERR_VALIDATION)
        except Exception:
            _logger.exception('Unexpected error while allocating reservation via API')
            return self._json_fail('Unexpected server error.', code=self._ERR_INTERNAL)

    @http.route([
        '/api/reservation/status/<int:batch_id>',
        '/api/v1/reservation/status/<int:batch_id>',
    ], type='http', auth='none', methods=['GET'], csrf=False)
    def reservation_status(self, batch_id, **kwargs):
        user = self._authenticate()
        if not user:
            return self._json_error('Unauthorized', status=401, code=self._ERR_UNAUTHORIZED)
        batch = request.env['stock.reservation.batch'].sudo().browse(batch_id)
        if not batch.exists():
            return self._json_error('Reservation batch not found.', status=404, code=self._ERR_NOT_FOUND)
        if batch.request_user_id != user and not user.has_group('stock_reservation_engine.group_stock_reservation_manager'):
            return self._json_error('Access denied.', status=403, code=self._ERR_FORBIDDEN)
        data = {
            'status': 'success',
            'data': {
                'batch_id': batch.id,
                'name': batch.name,
                'state': batch.state,
                'priority': batch.priority,
                'scheduled_date': batch.scheduled_date.isoformat() if batch.scheduled_date else None,
                'lines': [
                    {
                        'line_id': line.id,
                        'product_id': line.product_id.id,
                        'product_name': line.product_id.display_name,
                        'requested_qty': line.requested_qty,
                        'allocated_qty': line.allocated_qty,
                        'location_id': line.location_id.id,
                        'location_name': line.location_id.display_name,
                        'lot_id': line.lot_id.id if line.lot_id else False,
                        'lot_name': line.lot_id.name if line.lot_id else False,
                        'state': line.state,
                        'move_id': line.move_id.id if line.move_id else False,
                    }
                    for line in batch.line_ids
                ]
            }
        }
        return request.make_json_response(data)
