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
    readonly_enabled = False

    def _flush(self):
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

    def test_api_create_and_status_support_v1_prefix(self):
        token_raw = self._make_token_for_user(self.env.ref('base.user_admin'))
        variant, loc = self._make_storable_variant_with_stock(5.0)
        self._flush()
        create_response = self.url_open(
            '/api/v1/reservation/create',
            data=_rpc_json(7, {
                'lines': [{'product_id': variant.id, 'qty': 2, 'location_id': loc.id}],
            }),
            headers={
                'Content-Type': 'application/json',
                'Authorization': 'Bearer %s' % token_raw,
            },
        )
        self.assertEqual(create_response.status_code, 200)
