# -*- coding: utf-8 -*-
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    from odoo.addons.stock_reservation_engine.hooks import ensure_demo_stock

    ensure_demo_stock(env)
