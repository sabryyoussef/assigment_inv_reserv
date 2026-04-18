import json
import secrets

from odoo.tests import tagged
from odoo.tests.common import HttpCase


@tagged('post_install', '-at_install')
class TestReservationAPIController(HttpCase):
    """Integration tests for the ReservationAPI HTTP controller."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.stock_location = cls.env.ref('stock.stock_location_stock')
        cls.uom_unit = cls.env.ref('uom.product_uom_unit')
        cls.product = cls.env['product.product'].create({
            'name': 'API Test Product',
            'type': 'consu',
            'uom_id': cls.uom_unit.id,
            'uom_po_id': cls.uom_unit.id,
        })
        cls.valid_token = secrets.token_hex(32)
        cls.api_token = cls.env['reservation.api.token'].create({
            'name': 'Test API Token',
            'user_id': cls.env.user.id,
            'token': cls.valid_token,
            'active': True,
        })

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _post_json(self, url, params, token=None):
        """POST to a JSON-RPC endpoint and return the parsed 'result'."""
        headers = {'Content-Type': 'application/json'}
        if token:
            headers['Authorization'] = f'Bearer {token}'
        body = json.dumps({
            'jsonrpc': '2.0',
            'method': 'call',
            'id': 1,
            'params': params,
        }).encode()
        resp = self.url_open(url, data=body, headers=headers)
        return json.loads(resp.read()).get('result', {})

    def _get_json(self, url, token=None):
        """GET an HTTP endpoint and return the parsed JSON body."""
        headers = {}
        if token:
            headers['Authorization'] = f'Bearer {token}'
        resp = self.url_open(url, headers=headers)
        return json.loads(resp.read())

    # ------------------------------------------------------------------
    # POST /api/reservation/create
    # ------------------------------------------------------------------

    def test_create_unauthorized_no_token(self):
        result = self._post_json('/api/reservation/create', {
            'lines': [{'product_id': self.product.id, 'qty': 1.0,
                       'location_id': self.stock_location.id}],
        })
        self.assertEqual(result.get('status'), 'error')

    def test_create_unauthorized_invalid_token(self):
        result = self._post_json('/api/reservation/create', {
            'lines': [{'product_id': self.product.id, 'qty': 1.0,
                       'location_id': self.stock_location.id}],
        }, token='invalid-token-xyz')
        self.assertEqual(result.get('status'), 'error')

    def test_create_error_empty_lines(self):
        result = self._post_json('/api/reservation/create',
                                 {'lines': []},
                                 token=self.valid_token)
        self.assertEqual(result.get('status'), 'error')

    def test_create_error_line_missing_location(self):
        result = self._post_json('/api/reservation/create', {
            'lines': [{'product_id': self.product.id, 'qty': 1.0}],
        }, token=self.valid_token)
        self.assertEqual(result.get('status'), 'error')

    def test_create_error_line_missing_qty(self):
        result = self._post_json('/api/reservation/create', {
            'lines': [{'product_id': self.product.id,
                       'location_id': self.stock_location.id}],
        }, token=self.valid_token)
        self.assertEqual(result.get('status'), 'error')

    def test_create_error_line_missing_product(self):
        result = self._post_json('/api/reservation/create', {
            'lines': [{'qty': 1.0, 'location_id': self.stock_location.id}],
        }, token=self.valid_token)
        self.assertEqual(result.get('status'), 'error')

    def test_create_success_auto_confirm(self):
        result = self._post_json('/api/reservation/create', {
            'lines': [{'product_id': self.product.id, 'qty': 2.0,
                       'location_id': self.stock_location.id}],
            'auto_confirm': True,
        }, token=self.valid_token)
        self.assertEqual(result.get('status'), 'success')
        data = result.get('data', {})
        self.assertIn('batch_id', data)
        self.assertIn('name', data)
        self.assertEqual(data['state'], 'confirmed')

    def test_create_success_no_auto_confirm(self):
        result = self._post_json('/api/reservation/create', {
            'lines': [{'product_id': self.product.id, 'qty': 1.0,
                       'location_id': self.stock_location.id}],
            'auto_confirm': False,
        }, token=self.valid_token)
        self.assertEqual(result.get('status'), 'success')
        self.assertEqual(result['data']['state'], 'draft')

    def test_create_with_priority(self):
        result = self._post_json('/api/reservation/create', {
            'lines': [{'product_id': self.product.id, 'qty': 1.0,
                       'location_id': self.stock_location.id}],
            'priority': '2',
        }, token=self.valid_token)
        self.assertEqual(result.get('status'), 'success')
        batch = self.env['stock.reservation.batch'].browse(result['data']['batch_id'])
        self.assertEqual(batch.priority, '2')

    # ------------------------------------------------------------------
    # POST /api/reservation/allocate
    # ------------------------------------------------------------------

    def test_allocate_unauthorized(self):
        result = self._post_json('/api/reservation/allocate',
                                 {'batch_id': 999})
        self.assertEqual(result.get('status'), 'error')

    def test_allocate_missing_batch_id(self):
        result = self._post_json('/api/reservation/allocate', {},
                                 token=self.valid_token)
        self.assertEqual(result.get('status'), 'error')

    def test_allocate_batch_not_found(self):
        result = self._post_json('/api/reservation/allocate',
                                 {'batch_id': 99999999},
                                 token=self.valid_token)
        self.assertEqual(result.get('status'), 'error')

    def test_allocate_success(self):
        self.env['stock.quant']._update_available_quantity(
            self.product, self.stock_location, 10.0
        )
        batch = self.env['stock.reservation.batch'].create({
            'request_user_id': self.env.user.id,
            'line_ids': [(0, 0, {
                'product_id': self.product.id,
                'requested_qty': 3.0,
                'location_id': self.stock_location.id,
            })],
        })
        batch.action_confirm()
        result = self._post_json('/api/reservation/allocate',
                                 {'batch_id': batch.id},
                                 token=self.valid_token)
        self.assertEqual(result.get('status'), 'success')
        self.assertEqual(result['data']['state'], 'allocated')

    # ------------------------------------------------------------------
    # GET /api/reservation/status/<id>
    # ------------------------------------------------------------------

    def test_status_unauthorized_no_token(self):
        data = self._get_json('/api/reservation/status/1')
        self.assertEqual(data.get('status'), 'error')

    def test_status_unauthorized_invalid_token(self):
        data = self._get_json('/api/reservation/status/1',
                              token='bad-token')
        self.assertEqual(data.get('status'), 'error')

    def test_status_batch_not_found(self):
        data = self._get_json('/api/reservation/status/99999999',
                              token=self.valid_token)
        self.assertEqual(data.get('status'), 'error')

    def test_status_success(self):
        batch = self.env['stock.reservation.batch'].create({
            'request_user_id': self.env.user.id,
            'line_ids': [(0, 0, {
                'product_id': self.product.id,
                'requested_qty': 1.0,
                'location_id': self.stock_location.id,
            })],
        })
        data = self._get_json(f'/api/reservation/status/{batch.id}',
                              token=self.valid_token)
        self.assertEqual(data.get('status'), 'success')
        payload = data.get('data', {})
        self.assertEqual(payload['batch_id'], batch.id)
        self.assertIn('lines', payload)
        self.assertEqual(len(payload['lines']), 1)

    def test_status_line_fields(self):
        """Status response must include all documented line fields."""
        batch = self.env['stock.reservation.batch'].create({
            'request_user_id': self.env.user.id,
            'line_ids': [(0, 0, {
                'product_id': self.product.id,
                'requested_qty': 2.0,
                'location_id': self.stock_location.id,
            })],
        })
        data = self._get_json(f'/api/reservation/status/{batch.id}',
                              token=self.valid_token)
        line = data['data']['lines'][0]
        for field in ('line_id', 'product_id', 'product_name',
                      'requested_qty', 'allocated_qty',
                      'location_id', 'location_name',
                      'lot_id', 'lot_name', 'state', 'move_id'):
            self.assertIn(field, line, f"Field '{field}' missing from line response")

    # ------------------------------------------------------------------
    # End-to-end workflow
    # ------------------------------------------------------------------

    def test_full_workflow_create_allocate_status(self):
        """E2E: create → auto-confirm → allocate → check status = allocated."""
        self.env['stock.quant']._update_available_quantity(
            self.product, self.stock_location, 20.0
        )
        # Step 1: create
        r1 = self._post_json('/api/reservation/create', {
            'lines': [{'product_id': self.product.id, 'qty': 5.0,
                       'location_id': self.stock_location.id}],
            'auto_confirm': True,
        }, token=self.valid_token)
        self.assertEqual(r1['status'], 'success')
        batch_id = r1['data']['batch_id']

        # Step 2: allocate
        r2 = self._post_json('/api/reservation/allocate',
                             {'batch_id': batch_id},
                             token=self.valid_token)
        self.assertEqual(r2['status'], 'success')

        # Step 3: check status
        r3 = self._get_json(f'/api/reservation/status/{batch_id}',
                            token=self.valid_token)
        self.assertEqual(r3['status'], 'success')
        self.assertEqual(r3['data']['state'], 'allocated')
        self.assertEqual(r3['data']['lines'][0]['allocated_qty'], 5.0)
