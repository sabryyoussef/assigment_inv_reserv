# Stock Reservation Engine - Test execution report

Generated: **2026-04-18 08:12:17 UTC**  
Database: `odoo18`  

## 1. Summary

- **Scenarios executed:** 7
- **Passed:** 7
- **Failed:** 0
- **Demo stock hook:** OK

## 2. Scenario results

| Scenario | Status | Notes |
| -------- | ------ | ----- |
| 1 Full allocation | **PASS** | Product A 10 units from MDW stock (child locations). |
| 2 Partial allocation | **PASS** | Product B request 40 vs ~12 on hand. |
| 3 No stock | **PASS** | Product C zero inventory. |
| 4 FEFO perishable X | **PASS** | Cold zone; earliest expiry lot consumed. |
| 5 Child locations | **PASS** | Product A 50 from parent stock location. |
| 6 Re-allocate idempotency | **PASS** | Partial batch; second allocate must not duplicate picking. |
| 7 Multi-line mixed batch | **PASS** | Lines A full / B partial / C none. |

## 3. Detailed observations

### 1 Full allocation

- picking_type_code=internal
- origin='RES00403' batch='RES00403'
- move.picking_id=72

### 2 Partial allocation

- allocated=12.0 requested=40.0

### 3 No stock


### 4 FEFO perishable X

- chosen_lot=DEMO-LOT-ALPHA LOT-X-001 expiry before LOT-X-002: True

### 5 Child locations

- Stock split Shelf A/B; domain uses child_of(lot_stock)

### 6 Re-allocate idempotency

- picking_ids before=[76] after=[76] move_id=189 batch.state=partial

### 7 Multi-line mixed batch

- unique_states=['allocated', 'not_available', 'partial'] batch.state=partial
- lines=[[DEMO] Reservation — full allocation:allocated:2.0, [DEMO] Reservation — partial allocation:partial:12.0, [DEMO] Reservation — no stock:not_available:0.0]

## 4. Issues / global notes

- None recorded.

## 5. Environment

- **Warehouse:** Main Demo Warehouse (code MDW)
- **Lot stock:** MDW/Stock (id 19)
- **Pack / staging (`wh_pack_stock_loc_id`):** MDW/Packing Zone
- **Shelf A / B / Cold:** True, True, True
- **Picking type:** Internal transfer (`stock.picking.type` code `internal`) from allocation code path.
- **Allocation:** Quant-based; pickings confirmed without auto `action_assign()`.
- **Scenario 7:** calls `ensure_demo_stock` again so earlier scenarios do not exhaust demo quants.

---
*Automated by `tools/qa_full_validation.py` (Odoo shell).*
