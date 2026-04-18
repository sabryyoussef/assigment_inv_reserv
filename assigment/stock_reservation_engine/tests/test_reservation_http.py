# -*- coding: utf-8 -*-
import json
import uuid

from odoo.tests import tagged
from odoo.tests.common import HttpCase


def _rpc_json(call_id, params):
    return json.dumps({
        'jsonrpc': '2.0',
        'method': 'call',
        'params': params,
        'id': call_id,
    })


@tagged('post_install', '-at_install')
class TestReservationApiHttp(HttpCase):
    """HTTP-level tests for JSON-RPC routes and GET status (Bearer auth)."""

    # Allow POST handlers to write (stock.move, etc.); default HttpCase test mode uses readonly cursors.
    readonly_enabled = False

    def _flush(self):
        """Expose ORM changes to the HTTP worker (same transaction; commit is forbidden in tests)."""
        self.env.flush_all()

    def _make_token_for_user(self, user, raw=None):
        raw = raw or ('tok-%s' % uuid.uuid4().hex)
        self.env['reservation.api.token'].sudo().create({
            'name': 'HTTP test %s' % uuid.uuid4().hex,
            'user_id': user.id,
            'token': raw,
        })
        return raw

    def _make_storable_variant_with_stock(self, qty=10.0):
        loc = self.env.ref('stock.stock_location_stock')
        tmpl = self.env['product.template'].create({
            'name': 'HTTP API Product %s' % uuid.uuid4().hex[:8],
            'type': 'consu',
            'is_storable': True,
            'uom_id': self.env.ref('uom.product_uom_unit').id,
            'uom_po_id': self.env.ref('uom.product_uom_unit').id,
            'categ_id': self.env.ref('product.product_category_all').id,
        })
        variant = tmpl.product_variant_ids[:1]
        self.env['stock.quant'].sudo()._update_available_quantity(variant, loc, qty)
        return variant, loc

    # --- POST /api/reservation/create ---

    def test_api_create_unauthorized(self):
        response = self.url_open(
            '/api/reservation/create',
            data=_rpc_json(1, {'lines': []}),
            headers={'Content-Type': 'application/json'},
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        result = body.get('result') or {}
        self.assertEqual(result.get('status'), 'error')
        self.assertEqual(result.get('code'), 'ERR_UNAUTHORIZED')

    def test_api_create_inactive_token_unauthorized(self):
        raw = 'inactive-%s' % uuid.uuid4().hex
        self.env['reservation.api.token'].sudo().create({
            'name': 'inactive token',
            'user_id': self.env.ref('base.user_admin').id,
            'token': raw,
            'active': False,
        })
        self._flush()
        response = self.url_open(
            '/api/reservation/create',
            data=_rpc_json(2, {
                'lines': [{'product_id': 1, 'qty': 1, 'location_id': self.env.ref('stock.stock_location_stock').id}],
            }),
            headers={
                'Content-Type': 'application/json',
                'Authorization': 'Bearer %s' % raw,
            },
        )
        self.assertEqual(response.status_code, 200)
        res = (response.json().get('result') or {})
        self.assertEqual(res.get('code'), 'ERR_UNAUTHORIZED')

    def test_api_create_validation_empty_lines(self):
        token_raw = self._make_token_for_user(self.env.ref('base.user_admin'))
        self._flush()
        response = self.url_open(
            '/api/reservation/create',
            data=_rpc_json(3, {'lines': []}),
            headers={
                'Content-Type': 'application/json',
                'Authorization': 'Bearer %s' % token_raw,
            },
        )
        self.assertEqual(response.status_code, 200)
        res = response.json().get('result') or {}
        self.assertEqual(res.get('status'), 'error')
        self.assertEqual(res.get('code'), 'ERR_VALIDATION')

    def test_api_create_validation_bad_line(self):
        token_raw = self._make_token_for_user(self.env.ref('base.user_admin'))
        loc = self.env.ref('stock.stock_location_stock')
        self._flush()
        response = self.url_open(
            '/api/reservation/create',
            data=_rpc_json(4, {
                'lines': [{'qty': 2, 'location_id': loc.id}],
            }),
            headers={
                'Content-Type': 'application/json',
                'Authorization': 'Bearer %s' % token_raw,
            },
        )
        self.assertEqual(response.status_code, 200)
        res = response.json().get('result') or {}
        self.assertEqual(res.get('code'), 'ERR_VALIDATION')

    def test_api_aaa_flow_jsonrpc_create_then_allocate(self):
        """Runs first among api_* HTTP tests (before test_api_allocate_*) so the cursor is clean for DB writes."""
        token_raw = self._make_token_for_user(self.env.ref('base.user_admin'))
        variant, loc = self._make_storable_variant_with_stock(12.0)
        self._flush()
        cr = self.url_open(
            '/api/reservation/create',
            data=_rpc_json(101, {
                'lines': [{'product_id': variant.id, 'qty': 4, 'location_id': loc.id}],
                'auto_confirm': False,
            }),
            headers={
                'Content-Type': 'application/json',
                'Authorization': 'Bearer %s' % token_raw,
            },
        )
        self.assertEqual(cr.status_code, 200)
        cbody = cr.json()
        self.assertNotIn('error', cbody, msg=cbody)
        cres = cbody.get('result') or {}
        self.assertEqual(cres.get('status'), 'success')
        batch_id = cres['data']['batch_id']

        batch = self.env['stock.reservation.batch'].browse(batch_id)
        batch.action_confirm()

        self._flush()
        ar = self.url_open(
            '/api/reservation/allocate',
            data=_rpc_json(102, {'batch_id': batch_id}),
            headers={
                'Content-Type': 'application/json',
                'Authorization': 'Bearer %s' % token_raw,
            },
        )
        self.assertEqual(ar.status_code, 200)
        abody = ar.json()
        self.assertNotIn('error', abody, msg=abody)
        ares = abody.get('result') or {}
        self.assertEqual(ares.get('status'), 'success')
        self.assertEqual(ares.get('data', {}).get('state'), 'allocated')

    # --- POST /api/reservation/allocate ---

    def test_api_allocate_unauthorized(self):
        response = self.url_open(
            '/api/reservation/allocate',
            data=_rpc_json(10, {'batch_id': 1}),
            headers={'Content-Type': 'application/json'},
        )
        self.assertEqual(response.status_code, 200)
        res = response.json().get('result') or {}
        self.assertEqual(res.get('code'), 'ERR_UNAUTHORIZED')

    def test_api_allocate_validation_missing_batch_id(self):
        token_raw = self._make_token_for_user(self.env.ref('base.user_admin'))
        self._flush()
        response = self.url_open(
            '/api/reservation/allocate',
            data=_rpc_json(11, {}),
            headers={
                'Content-Type': 'application/json',
                'Authorization': 'Bearer %s' % token_raw,
            },
        )
        self.assertEqual(response.status_code, 200)
        res = response.json().get('result') or {}
        self.assertEqual(res.get('code'), 'ERR_VALIDATION')

    def test_api_allocate_not_found(self):
        token_raw = self._make_token_for_user(self.env.ref('base.user_admin'))
        self._flush()
        response = self.url_open(
            '/api/reservation/allocate',
            data=_rpc_json(12, {'batch_id': 999999997}),
            headers={
                'Content-Type': 'application/json',
                'Authorization': 'Bearer %s' % token_raw,
            },
        )
        self.assertEqual(response.status_code, 200)
        res = response.json().get('result') or {}
        self.assertEqual(res.get('code'), 'ERR_NOT_FOUND')

    def test_api_allocate_forbidden_non_owner(self):
        admin = self.env.ref('base.user_admin')
        peer = self.env['res.users'].create({
            'name': 'API peer',
            'login': 'api_peer_%s' % uuid.uuid4().hex,
            'password': 'peer',
            'company_id': self.env.company.id,
            'company_ids': [(6, 0, [self.env.company.id])],
            'groups_id': [(6, 0, [
                self.env.ref('base.group_user').id,
                self.env.ref('stock.group_stock_user').id,
                self.env.ref('stock_reservation_engine.group_stock_reservation_user').id,
            ])],
        })
        variant, loc = self._make_storable_variant_with_stock(10.0)
        batch = self.env['stock.reservation.batch'].sudo().create({
            'request_user_id': admin.id,
            'line_ids': [(0, 0, {
                'product_id': variant.id,
                'requested_qty': 1.0,
                'location_id': loc.id,
            })],
        })
        batch.sudo().action_confirm()
        token_peer = self._make_token_for_user(peer)
        self._flush()
        response = self.url_open(
            '/api/reservation/allocate',
            data=_rpc_json(13, {'batch_id': batch.id}),
            headers={
                'Content-Type': 'application/json',
                'Authorization': 'Bearer %s' % token_peer,
            },
        )
        self.assertEqual(response.status_code, 200)
        res = response.json().get('result') or {}
        self.assertEqual(res.get('code'), 'ERR_FORBIDDEN')

    def test_api_zzz_allocate_success_admin_owner(self):
        """Happy-path allocate via JSON-RPC; name prefix keeps this last (allocate_* runs before create_* alphabetically)."""
        admin = self.env.ref('base.user_admin')
        variant, loc = self._make_storable_variant_with_stock(10.0)
        batch = self.env['stock.reservation.batch'].sudo().create({
            'request_user_id': admin.id,
            'line_ids': [(0, 0, {
                'product_id': variant.id,
                'requested_qty': 2.0,
                'location_id': loc.id,
            })],
        })
        batch.sudo().action_confirm()
        token_raw = self._make_token_for_user(admin)
        self._flush()
        response = self.url_open(
            '/api/reservation/allocate',
            data=_rpc_json(14, {'batch_id': batch.id}),
            headers={
                'Content-Type': 'application/json',
                'Authorization': 'Bearer %s' % token_raw,
            },
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertNotIn('error', body, msg=body)
        res = body.get('result') or {}
        self.assertEqual(res.get('status'), 'success', msg=body)
        self.assertIn(res.get('data', {}).get('state'), ('allocated', 'partial'))

    # --- GET /api/reservation/status/<id> ---

    def test_api_status_unauthorized(self):
        response = self.url_open('/api/reservation/status/1', headers={})
        self.assertEqual(response.status_code, 401)
        body = response.json()
        self.assertEqual(body.get('status'), 'error')
        self.assertEqual(body.get('code'), 'ERR_UNAUTHORIZED')

    def test_api_status_not_found(self):
        token_raw = self._make_token_for_user(self.env.ref('base.user_admin'))
        self._flush()
        response = self.url_open(
            '/api/reservation/status/999999996',
            headers={
                'Authorization': 'Bearer %s' % token_raw,
            },
        )
        self.assertEqual(response.status_code, 404)
        body = response.json()
        self.assertEqual(body.get('code'), 'ERR_NOT_FOUND')

    def test_api_status_forbidden_non_owner(self):
        admin = self.env.ref('base.user_admin')
        peer = self.env['res.users'].create({
            'name': 'API status peer',
            'login': 'api_st_peer_%s' % uuid.uuid4().hex,
            'password': 'x',
            'company_id': self.env.company.id,
            'company_ids': [(6, 0, [self.env.company.id])],
            'groups_id': [(6, 0, [
                self.env.ref('base.group_user').id,
                self.env.ref('stock.group_stock_user').id,
                self.env.ref('stock_reservation_engine.group_stock_reservation_user').id,
            ])],
        })
        variant, loc = self._make_storable_variant_with_stock(1.0)
        batch = self.env['stock.reservation.batch'].sudo().create({
            'request_user_id': admin.id,
            'line_ids': [(0, 0, {
                'product_id': variant.id,
                'requested_qty': 1.0,
                'location_id': loc.id,
            })],
        })
        tok = self._make_token_for_user(peer)
        self._flush()
        response = self.url_open(
            '/api/reservation/status/%s' % batch.id,
            headers={'Authorization': 'Bearer %s' % tok},
        )
        self.assertEqual(response.status_code, 403)
        body = response.json()
        self.assertEqual(body.get('code'), 'ERR_FORBIDDEN')

    def test_api_status_success(self):
        token_raw = self._make_token_for_user(self.env.ref('base.user_admin'))
        variant, loc = self._make_storable_variant_with_stock(3.0)
        batch = self.env['stock.reservation.batch'].sudo().create({
            'request_user_id': self.env.ref('base.user_admin').id,
            'line_ids': [(0, 0, {
                'product_id': variant.id,
                'requested_qty': 1.0,
                'location_id': loc.id,
            })],
        })
        batch.sudo().action_confirm()
        self._flush()
        response = self.url_open(
            '/api/reservation/status/%s' % batch.id,
            headers={
                'Authorization': 'Bearer %s' % token_raw,
            },
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body['status'], 'success')
        self.assertEqual(body['data']['batch_id'], batch.id)
        self.assertTrue('lines' in body['data'])
