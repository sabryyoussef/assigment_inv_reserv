# -*- coding: utf-8 -*-
"""Demo inventory levels (idempotent). Used by post_init_hook and migrations."""
import logging

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    ensure_demo_stock(env)


def ensure_demo_stock(env):
    """Set on-hand quantities for demo products; safe to call multiple times."""
    if not env.ref('stock_reservation_engine.demo_pt_full', raise_if_not_found=False):
        return
    wh_loc = env.ref('stock.warehouse0').lot_stock_id
    shelf_loc = env.ref('stock_reservation_engine.demo_location_shelf', raise_if_not_found=False)
    Quant = env['stock.quant']

    def add_to_target(product, location, target_qty, lot=None):
        if not location or not product:
            return
        avail = Quant._get_available_quantity(product, location, lot_id=lot, strict=True)
        delta = target_qty - avail
        if delta <= 0:
            return
        Quant._update_available_quantity(product, location, delta, lot_id=lot)

    # Simple products @ main stock
    add_to_target(
        env.ref('stock_reservation_engine.demo_pt_full').product_variant_ids[:1],
        wh_loc,
        50.0,
    )
    add_to_target(
        env.ref('stock_reservation_engine.demo_pt_partial').product_variant_ids[:1],
        wh_loc,
        25.0,
    )
    # demo_pt_empty: intentionally no stock

    # Child location: stock only on shelf (tests location child_of aggregation)
    if shelf_loc:
        add_to_target(
            env.ref('stock_reservation_engine.demo_pt_shelf_only').product_variant_ids[:1],
            shelf_loc,
            12.0,
        )

    # Lot-tracked product: stock on LOT-ALPHA only
    lot_a = env.ref('stock_reservation_engine.demo_lot_alpha', raise_if_not_found=False)
    p_lots = env.ref('stock_reservation_engine.demo_pt_lots', raise_if_not_found=False)
    if lot_a and p_lots:
        add_to_target(
            p_lots.product_variant_ids[:1],
            wh_loc,
            18.0,
            lot=lot_a,
        )

    _logger.info('stock_reservation_engine: demo stock levels ensured')
