# -*- coding: utf-8 -*-
"""Demo inventory levels (idempotent). Used by post_init_hook and migrations."""
import logging
from datetime import timedelta

from odoo import fields

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    ensure_demo_stock(env)


def ensure_demo_stock(env):
    """Apply intended on-hand quantities for demo products. Safe to call multiple times."""
    if not env.ref('stock_reservation_engine.demo_pt_full', raise_if_not_found=False):
        return
    if not env.ref('stock_reservation_engine.warehouse_demo_mdw', raise_if_not_found=False):
        return

    wh = env.ref('stock_reservation_engine.warehouse_demo_mdw').sudo()
    lot_stock = wh.lot_stock_id
    shelf_a = env.ref('stock_reservation_engine.mdw_location_shelf_a').sudo()
    shelf_b = env.ref('stock_reservation_engine.mdw_location_shelf_b').sudo()
    cold = env.ref('stock_reservation_engine.mdw_location_cold_zone').sudo()

    pa = env.ref('stock_reservation_engine.demo_pt_full').product_variant_ids[:1]
    pb = env.ref('stock_reservation_engine.demo_pt_partial').product_variant_ids[:1]
    px = env.ref('stock_reservation_engine.demo_pt_lots').product_variant_ids[:1]

    lot_alpha = env.ref('stock_reservation_engine.demo_lot_alpha').sudo()
    lot_beta = env.ref('stock_reservation_engine.demo_lot_beta').sudo()

    Quant = env['stock.quant']

    def add_to_target(product, location, target_qty, lot=None):
        if not location or not product:
            return
        avail = Quant._get_available_quantity(product, location, lot_id=lot, strict=True)
        delta = target_qty - avail
        if delta <= 0:
            return
        Quant._update_available_quantity(product, location, delta, lot_id=lot)

    add_to_target(pa, shelf_a, 35.0)
    add_to_target(pa, shelf_b, 35.0)
    add_to_target(pb, lot_stock, 12.0)
    add_to_target(px, cold, 12.0, lot=lot_alpha)
    add_to_target(px, cold, 14.0, lot=lot_beta)

    now = fields.Datetime.now()
    lot_alpha.write({'expiration_date': now + timedelta(days=90)})
    lot_beta.write({'expiration_date': now + timedelta(days=365)})

    _logger.info('stock_reservation_engine: demo stock levels ensured (MDW)')
