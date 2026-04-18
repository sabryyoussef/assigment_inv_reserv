# -*- coding: utf-8 -*-
"""
Run inside Odoo shell (stdin) to validate reservation + picking flows.

  Get-Content tools/qa_full_validation.py | python odoo-bin shell -c odoo.conf -d DBNAME

Writes: <module_root>/TEST_EXECUTION_REPORT.md
"""
from __future__ import annotations

import traceback
from datetime import datetime
from pathlib import Path

import odoo
from odoo import api
from odoo.modules.module import get_module_path

# shell provides env
admin = env.ref('base.user_admin')
env = api.Environment(env.cr, admin.id, {})

try:
    from odoo.addons.stock_reservation_engine import hooks as _sr_hooks

    ensure_demo_stock = _sr_hooks.ensure_demo_stock
except ImportError:
    ensure_demo_stock = None


def module_report_path():
    root = Path(get_module_path('stock_reservation_engine'))
    return root / 'TEST_EXECUTION_REPORT.md'


def fmt_pass(ok: bool) -> str:
    return 'PASS' if ok else 'FAIL'


results = []
notes_global = []
env_ctx = {'ts': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC'), 'db': env.cr.dbname}


def record(scenario: str, ok: bool, detail: str, validations: list[str]):
    results.append({
        'scenario': scenario,
        'status': fmt_pass(ok),
        'detail': detail,
        'validations': validations,
    })


def safe_float_eq(a, b, eps=1e-6):
    return abs(a - b) < eps


# --- Ensure demo stock (ORM, idempotent) ---
stock_ok = False
if ensure_demo_stock:
    try:
        ensure_demo_stock(env)
        stock_ok = True
    except Exception as e:
        notes_global.append(f'ensure_demo_stock error: {e}')
else:
    notes_global.append('ensure_demo_stock import failed (path?)')

wh = env.ref('stock_reservation_engine.warehouse_demo_mdw', raise_if_not_found=False)
lot_stock = wh.lot_stock_id if wh else None
shelf_a = env.ref('stock_reservation_engine.mdw_location_shelf_a', raise_if_not_found=False)
shelf_b = env.ref('stock_reservation_engine.mdw_location_shelf_b', raise_if_not_found=False)
cold = env.ref('stock_reservation_engine.mdw_location_cold_zone', raise_if_not_found=False)
pack_loc = wh.wh_pack_stock_loc_id if wh else None

def _variant(pt_xml_id):
    pt = env.ref(pt_xml_id)
    if getattr(pt, 'product_variant_id', False) and pt.product_variant_id:
        return pt.product_variant_id
    return pt.product_variant_ids[0]


pa = _variant('stock_reservation_engine.demo_pt_full')
pb = _variant('stock_reservation_engine.demo_pt_partial')
pc = _variant('stock_reservation_engine.demo_pt_empty')
px = _variant('stock_reservation_engine.demo_pt_lots')
lot_alpha = env.ref('stock_reservation_engine.demo_lot_alpha')
lot_beta = env.ref('stock_reservation_engine.demo_lot_beta')

Batch = env['stock.reservation.batch']

# Scenario 1: Full allocation
v1 = []
ok1 = False
try:
    b1 = Batch.create({
        'request_user_id': admin.id,
        'line_ids': [(0, 0, {
            'product_id': pa.id,
            'requested_qty': 10.0,
            'location_id': lot_stock.id,
        })],
    })
    b1.action_confirm()
    b1.action_allocate()
    line = b1.line_ids[0]
    ok1 = (
        safe_float_eq(line.allocated_qty, 10.0)
        and line.state == 'allocated'
        and bool(line.move_id)
        and len(b1.picking_ids) >= 1
        and line.move_id.picking_id in b1.picking_ids
    )
    if b1.picking_ids:
        pick = b1.picking_ids[0]
        v1.append(f'picking_type_code={pick.picking_type_id.code}')
        v1.append(f'origin={pick.origin!r} batch={b1.name!r}')
        v1.append(f'move.picking_id={line.move_id.picking_id.id}')
except Exception as e:
    v1.append(traceback.format_exc())
record('1 Full allocation', ok1, 'Product A 10 units from MDW stock (child locations).', v1)

# Scenario 2: Partial
v2 = []
ok2 = False
try:
    b2 = Batch.create({
        'request_user_id': admin.id,
        'line_ids': [(0, 0, {
            'product_id': pb.id,
            'requested_qty': 40.0,
            'location_id': lot_stock.id,
        })],
    })
    b2.action_confirm()
    b2.action_allocate()
    line = b2.line_ids[0]
    ok2 = (
        line.allocated_qty < line.requested_qty
        and line.state == 'partial'
        and bool(line.move_id)
        and safe_float_eq(line.move_id.product_uom_qty, line.allocated_qty)
        and len(b2.picking_ids) >= 1
    )
    v2.append(f'allocated={line.allocated_qty} requested={line.requested_qty}')
except Exception as e:
    v2.append(traceback.format_exc())
record('2 Partial allocation', ok2, 'Product B request 40 vs ~12 on hand.', v2)

# Scenario 3: No stock
v3 = []
ok3 = False
try:
    b3 = Batch.create({
        'request_user_id': admin.id,
        'line_ids': [(0, 0, {
            'product_id': pc.id,
            'requested_qty': 5.0,
            'location_id': lot_stock.id,
        })],
    })
    b3.action_confirm()
    b3.action_allocate()
    line = b3.line_ids[0]
    ok3 = (
        safe_float_eq(line.allocated_qty, 0.0)
        and not line.move_id
        and len(b3.picking_ids) == 0
    )
except Exception as e:
    v3.append(traceback.format_exc())
record('3 No stock', ok3, 'Product C zero inventory.', v3)

# Scenario 4: FEFO
v4 = []
ok4 = False
try:
    b4 = Batch.create({
        'request_user_id': admin.id,
        'line_ids': [(0, 0, {
            'product_id': px.id,
            'requested_qty': 1.0,
            'location_id': cold.id,
        })],
    })
    b4.action_confirm()
    b4.action_allocate()
    line = b4.line_ids[0]
    ok4 = (
        line.lot_id.id == lot_alpha.id
        and line.state == 'allocated'
        and len(b4.picking_ids) >= 1
        and bool(line.move_id.picking_id)
    )
    exp_a = lot_alpha.expiration_date
    exp_b = lot_beta.expiration_date
    v4.append(f'chosen_lot={line.lot_id.name} LOT-X-001 expiry before LOT-X-002: {exp_a < exp_b if exp_a and exp_b else "n/a"}')
except Exception as e:
    v4.append(traceback.format_exc())
record('4 FEFO perishable X', ok4, 'Cold zone; earliest expiry lot consumed.', v4)

# Scenario 5: Child locations (request from parent stock; stock on Shelf A+B)
v5 = []
ok5 = False
try:
    b5 = Batch.create({
        'request_user_id': admin.id,
        'line_ids': [(0, 0, {
            'product_id': pa.id,
            'requested_qty': 50.0,
            'location_id': lot_stock.id,
        })],
    })
    b5.action_confirm()
    b5.action_allocate()
    line = b5.line_ids[0]
    ok5 = (
        safe_float_eq(line.allocated_qty, 50.0)
        and line.state == 'allocated'
        and len(b5.picking_ids) >= 1
    )
    v5.append('Stock split Shelf A/B; domain uses child_of(lot_stock)')
except Exception as e:
    v5.append(traceback.format_exc())
record('5 Child locations', ok5, 'Product A 50 from parent stock location.', v5)

# Scenario 6: Idempotency (batch must stay partial on line so second allocate is allowed by engine)
v6 = []
ok6 = False
try:
    # Request more than total on-hand for Product A (~70 across shelves) so batch stays `partial`
    b6 = Batch.create({
        'request_user_id': admin.id,
        'line_ids': [(0, 0, {
            'product_id': pa.id,
            'requested_qty': 500.0,
            'location_id': lot_stock.id,
        })],
    })
    b6.action_confirm()
    b6.action_allocate()
    n1 = len(b6.picking_ids)
    pid1 = sorted(b6.picking_ids.ids)
    b6.action_allocate()
    b6.invalidate_recordset()
    n2 = len(b6.picking_ids)
    pid2 = sorted(b6.picking_ids.ids)
    mv = b6.line_ids[0].move_id.id
    ok6 = (n1 == n2 >= 1 and pid1 == pid2 and b6.state == 'partial')
    v6.append(f'picking_ids before={pid1} after={pid2} move_id={mv} batch.state={b6.state}')
except Exception as e:
    v6.append(traceback.format_exc())
record('6 Re-allocate idempotency', ok6, 'Partial batch; second allocate must not duplicate picking.', v6)

# Scenario 7: Multi-line mixed (replenish quants — earlier scenarios depleted Product A/B pools)
v7 = []
ok7 = False
try:
    if ensure_demo_stock:
        ensure_demo_stock(env)

    b7 = Batch.create({
        'request_user_id': admin.id,
        'line_ids': [
            (0, 0, {'product_id': pa.id, 'requested_qty': 2.0, 'location_id': lot_stock.id}),
            (0, 0, {'product_id': pb.id, 'requested_qty': 99.0, 'location_id': lot_stock.id}),
            (0, 0, {'product_id': pc.id, 'requested_qty': 2.0, 'location_id': lot_stock.id}),
        ],
    })
    b7.action_confirm()
    b7.action_allocate()
    states = set(b7.line_ids.mapped('state'))
    per_line = ', '.join(
        f'{l.product_id.product_tmpl_id.name}:{l.state}:{l.allocated_qty}'
        for l in b7.line_ids
    )
    ok7 = (
        b7.state == 'partial'
        and 'not_available' in states
        and 'allocated' in states
        and 'partial' in states
        and len(b7.line_ids) == 3
        and len(b7.picking_ids) >= 1
    )
    v7.append(f'unique_states={sorted(states)} batch.state={b7.state}')
    v7.append(f'lines=[{per_line}]')
except Exception as e:
    v7.append(traceback.format_exc())
record('7 Multi-line mixed batch', ok7, 'Lines A full / B partial / C none.', v7)

# --- Write report ---
passed = sum(1 for r in results if r['status'] == 'PASS')
failed = len(results) - passed

lines_out = []
lines_out.append('# Stock Reservation Engine - Test execution report')
lines_out.append('')
lines_out.append(f'Generated: **{env_ctx["ts"]}**  ')
lines_out.append(f'Database: `{env_ctx["db"]}`  ')
lines_out.append('')
lines_out.append('## 1. Summary')
lines_out.append('')
lines_out.append(f'- **Scenarios executed:** {len(results)}')
lines_out.append(f'- **Passed:** {passed}')
lines_out.append(f'- **Failed:** {failed}')
lines_out.append(f'- **Demo stock hook:** {"OK" if stock_ok else "skipped/error"}')
lines_out.append('')
lines_out.append('## 2. Scenario results')
lines_out.append('')
lines_out.append('| Scenario | Status | Notes |')
lines_out.append('| -------- | ------ | ----- |')
for r in results:
    short = r['detail'].replace('|', '\\|')
    lines_out.append(f'| {r["scenario"]} | **{r["status"]}** | {short} |')
lines_out.append('')
lines_out.append('## 3. Detailed observations')
lines_out.append('')
for r in results:
    lines_out.append(f'### {r["scenario"]}')
    lines_out.append('')
    for v in r['validations']:
        lines_out.append(f'- {v}')
    lines_out.append('')
lines_out.append('## 4. Issues / global notes')
lines_out.append('')
if notes_global:
    for n in notes_global:
        lines_out.append(f'- {n}')
else:
    lines_out.append('- None recorded.')
lines_out.append('')
lines_out.append('## 5. Environment')
lines_out.append('')
lines_out.append(f'- **Warehouse:** {wh.display_name if wh else "n/a"} (code {wh.code if wh else ""})')
lines_out.append(f'- **Lot stock:** {lot_stock.display_name if lot_stock else "n/a"} (id {lot_stock.id if lot_stock else ""})')
lines_out.append(f'- **Pack / staging (`wh_pack_stock_loc_id`):** {pack_loc.display_name if pack_loc else "missing — picking creation may error"}')
lines_out.append(f'- **Shelf A / B / Cold:** {bool(shelf_a)}, {bool(shelf_b)}, {bool(cold)}')
lines_out.append('- **Picking type:** Internal transfer (`stock.picking.type` code `internal`) from allocation code path.')
lines_out.append('- **Allocation:** Quant-based; pickings confirmed without auto `action_assign()`.')
lines_out.append('- **Scenario 7:** calls `ensure_demo_stock` again so earlier scenarios do not exhaust demo quants.')
lines_out.append('')
lines_out.append('---')
lines_out.append('*Automated by `tools/qa_full_validation.py` (Odoo shell).*')

out_path = module_report_path()
out_path.write_text('\n'.join(lines_out), encoding='utf-8')
print(f'QA report written to: {out_path}')
print(f'Summary: PASS={passed} FAIL={failed}')
