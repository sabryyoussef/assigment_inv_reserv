import hashlib

from odoo import http
from odoo.http import request


class ReservationAPI(http.Controller):

    _ERR_UNAUTHORIZED = 'ERR_UNAUTHORIZED'
    _ERR_VALIDATION = 'ERR_VALIDATION'
    _ERR_FORBIDDEN = 'ERR_FORBIDDEN'
    _ERR_NOT_FOUND = 'ERR_NOT_FOUND'

    def _json_error(self, message, status=400, code='ERR_VALIDATION'):
        payload = {'status': 'error', 'message': message, 'code': code}
        return request.make_json_response(payload, status=status)

    def _json_fail(self, message, code='ERR_VALIDATION'):
        """Consistent body for type=json routes (inside JSON-RPC result)."""
        return {'status': 'error', 'message': message, 'code': code}

    def _get_bearer_token(self):
        header = request.httprequest.headers.get('Authorization', '')
        if not header.startswith('Bearer '):
            return None
        return header.split(' ', 1)[1].strip()

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
        # Relation field can resolve to res.users() for public uid; read() returns stored FK regardless.
        row = token.sudo().read(['user_id'])
        if not row or not row[0].get('user_id'):
            return None
        uid = row[0]['user_id'][0]
        return request.env['res.users'].sudo().browse(uid)

    @http.route('/api/reservation/create', type='json', auth='none', methods=['POST'], csrf=False)
    def create_reservation(self, **payload):
        user = self._authenticate()
        if not user:
            return self._json_fail('Unauthorized', code=self._ERR_UNAUTHORIZED)
        try:
            lines = payload.get('lines') or []
            if not lines:
                return self._json_fail('At least one line is required.', code=self._ERR_VALIDATION)
            line_commands = []
            for item in lines:
                product_id = item.get('product_id')
                qty = item.get('qty') or item.get('requested_qty')
                location_id = item.get('location_id')
                lot_id = item.get('lot_id')
                if not product_id or not location_id or not qty:
                    return self._json_fail(
                        'Each line must include product_id, qty, and location_id.',
                        code=self._ERR_VALIDATION,
                    )
                line_commands.append((0, 0, {
                    'product_id': product_id,
                    'requested_qty': qty,
                    'location_id': location_id,
                    'lot_id': lot_id or False,
                }))
            # auth='none': request.env.uid stays public; sudo() does not change uid. Mail needs env.user singleton.
            env_u = request.env(user=user.id, su=True)
            company = user.company_id or env_u['res.company'].search([], limit=1)
            batch = env_u['stock.reservation.batch'].create({
                'company_id': company.id,
                'request_user_id': user.id,
                'priority': payload.get('priority', '1'),
                'scheduled_date': payload.get('scheduled_date'),
                'line_ids': line_commands,
            })
            if payload.get('auto_confirm', True):
                batch.with_user(user).action_confirm()
            return {
                'status': 'success',
                'data': {
                    'batch_id': batch.id,
                    'name': batch.name,
                    'state': batch.state,
                }
            }
        except Exception as exc:
            return self._json_fail(str(exc), code=self._ERR_VALIDATION)

    @http.route('/api/reservation/allocate', type='json', auth='none', methods=['POST'], csrf=False)
    def allocate_reservation(self, **payload):
        user = self._authenticate()
        if not user:
            return self._json_fail('Unauthorized', code=self._ERR_UNAUTHORIZED)
        try:
            batch_id = payload.get('batch_id')
            if not batch_id:
                return self._json_fail('batch_id is required.', code=self._ERR_VALIDATION)
            batch = request.env['stock.reservation.batch'].sudo().browse(batch_id)
            if not batch.exists():
                return self._json_fail('Reservation batch not found.', code=self._ERR_NOT_FOUND)
            if batch.request_user_id != user and not user.has_group('stock_reservation_engine.group_stock_reservation_manager'):
                return self._json_fail('Access denied.', code=self._ERR_FORBIDDEN)
            batch.with_user(user).action_allocate()
            return {
                'status': 'success',
                'data': {
                    'batch_id': batch.id,
                    'name': batch.name,
                    'state': batch.state,
                }
            }
        except Exception as exc:
            return self._json_fail(str(exc), code=self._ERR_VALIDATION)

    @http.route('/api/reservation/status/<int:batch_id>', type='http', auth='none', methods=['GET'], csrf=False)
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
