import json

from odoo import http
from odoo.http import request


class ReservationAPI(http.Controller):

    def _json_error(self, message, status=400):
        return request.make_json_response({'status': 'error', 'message': message}, status=status)

    def _get_bearer_token(self):
        header = request.httprequest.headers.get('Authorization', '')
        if not header.startswith('Bearer '):
            return None
        return header.split(' ', 1)[1].strip()

    def _authenticate(self):
        token_value = self._get_bearer_token()
        if not token_value:
            return None
        token = request.env['reservation.api.token'].sudo().search([
            ('token', '=', token_value),
            ('active', '=', True),
        ], limit=1)
        return token.user_id if token else None

    @http.route('/api/reservation/create', type='json', auth='none', methods=['POST'], csrf=False)
    def create_reservation(self, **payload):
        user = self._authenticate()
        if not user:
            return {'status': 'error', 'message': 'Unauthorized'}
        try:
            lines = payload.get('lines') or []
            if not lines:
                return {'status': 'error', 'message': 'At least one line is required.'}
            line_commands = []
            for item in lines:
                product_id = item.get('product_id')
                qty = item.get('qty') or item.get('requested_qty')
                location_id = item.get('location_id')
                lot_id = item.get('lot_id')
                if not product_id or not location_id or not qty:
                    return {'status': 'error', 'message': 'Each line must include product_id, qty, and location_id.'}
                line_commands.append((0, 0, {
                    'product_id': product_id,
                    'requested_qty': qty,
                    'location_id': location_id,
                    'lot_id': lot_id,
                }))
            batch = request.env['stock.reservation.batch'].sudo().create({
                'request_user_id': user.id,
                'priority': payload.get('priority', '1'),
                'scheduled_date': payload.get('scheduled_date'),
                'line_ids': line_commands,
            })
            if payload.get('auto_confirm', True):
                batch.action_confirm()
            return {
                'status': 'success',
                'data': {
                    'batch_id': batch.id,
                    'name': batch.name,
                    'state': batch.state,
                }
            }
        except Exception as exc:
            return {'status': 'error', 'message': str(exc)}

    @http.route('/api/reservation/allocate', type='json', auth='none', methods=['POST'], csrf=False)
    def allocate_reservation(self, **payload):
        user = self._authenticate()
        if not user:
            return {'status': 'error', 'message': 'Unauthorized'}
        try:
            batch_id = payload.get('batch_id')
            if not batch_id:
                return {'status': 'error', 'message': 'batch_id is required.'}
            batch = request.env['stock.reservation.batch'].sudo().browse(batch_id)
            if not batch.exists():
                return {'status': 'error', 'message': 'Reservation batch not found.'}
            if batch.request_user_id != user and not user.has_group('stock_reservation_engine.group_stock_reservation_manager'):
                return {'status': 'error', 'message': 'Access denied.'}
            batch.action_allocate()
            return {
                'status': 'success',
                'data': {
                    'batch_id': batch.id,
                    'name': batch.name,
                    'state': batch.state,
                }
            }
        except Exception as exc:
            return {'status': 'error', 'message': str(exc)}

    @http.route('/api/reservation/status/<int:batch_id>', type='http', auth='none', methods=['GET'], csrf=False)
    def reservation_status(self, batch_id, **kwargs):
        user = self._authenticate()
        if not user:
            return self._json_error('Unauthorized', status=401)
        batch = request.env['stock.reservation.batch'].sudo().browse(batch_id)
        if not batch.exists():
            return self._json_error('Reservation batch not found.', status=404)
        if batch.request_user_id != user and not user.has_group('stock_reservation_engine.group_stock_reservation_manager'):
            return self._json_error('Access denied.', status=403)
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
