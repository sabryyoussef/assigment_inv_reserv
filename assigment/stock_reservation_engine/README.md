# Stock Reservation Engine

## Overview

Custom reservation and allocation on top of Odoo Inventory: batches and lines, proactive allocation from `stock.quant`, FEFO when lot expiration exists (otherwise FIFO), generation of `stock.move` records, and **internal transfer** `stock.picking` documents grouped from those moves. Optional JSON HTTP API with Bearer tokens.

Designed for scenarios where multiple demands may compete for stock before standard fulfillment runs.

## Screenshots

Assets live under **`static/description/screenshots/`**. Capture tooling: **`tools/screenshots/`** (`npm run capture`, `npm run walkthrough`). Index: [static/description/screenshots/README.md](static/description/screenshots/README.md).

## Scope delivered

- Models: `stock.reservation.batch`, `stock.reservation.line`, `reservation.api.token`
- Allocation from `stock.quant` (FEFO / FIFO, partial and full)
- **`stock.move`** per line when `allocated_qty > 0` (destination: warehouse pack / staging — see below)
- **`stock.picking`** internal transfers: **`picking_ids`**, **`picking_count`**, **Transfers** smart button; grouping and idempotency documented below
- **`action_view_moves`**: filtered list/form on `stock.move` (inline window action; no dependency on stock menu XML ids)
- HTTP API: `/api/reservation/create`, `/api/reservation/allocate`, `/api/reservation/status/<id>`
- Security groups, record rules, server-side allocate authorization
- Demo XML + **`hooks.ensure_demo_stock`** (post-init + migrations)
- Tests: **`TransactionCase`** (allocation paths, auth, moves, pickings, idempotency); **`HttpCase`** (API routes)
- **`tools/qa_full_validation.py`** (shell): seven ORM scenarios → **`TEST_EXECUTION_REPORT.md`**

---

## Stock transfer (picking) generation

### What is implemented

After **`action_allocate`** completes, **`_generate_pickings_from_allocated_moves()`** runs. It considers only moves from lines with **`allocated_qty > 0`** (existing **`stock.move`** records).

- Moves are grouped by **`(location_id, location_dest_id)`**. Each group becomes **one** **`stock.picking`** (internal transfer operation type).
- Typical case: one source location and one staging destination → **one picking per batch**. Different source→destination pairs produce **multiple** pickings for the same batch.
- **`origin`** on the picking is **`batch.name`**. **`scheduled_date`** is copied from **`batch.scheduled_date`** when set.
- Moves are linked with **`picking_id`**; the batch stores links in **`picking_ids`** (Many2many).

### Behavior

- **Destination** for reservation moves: **`warehouse.wh_pack_stock_loc_id`** when the warehouse is resolved from the line’s source location; otherwise the **default destination** of the first **Internal** operation type for the company. If neither can be resolved, allocation still completes for quant logic, but move creation / picking setup raises a clear **`UserError`** (configuration required).
- **Operation type**: **`_get_internal_picking_type`** prefers the **Internal** picking type for the resolved warehouse, else any **Internal** type for the company.
- Picking is **`action_confirm()`** so it appears under standard Inventory operations. **`action_assign()`** is **not** called automatically; users may use **Check Availability** on the transfer when they want Odoo’s reservation layer aligned with warehouse rules.

### Idempotency

- Only moves with **`not m.picking_id`** are grouped into new pickings. Moves already on a picking are **skipped**.
- Re-running **Allocate** does **not** duplicate **`stock.move`** (same line reuses/refreshes quantity) and does **not** add duplicate pickings when moves were already attached.
- Covered by tests: **`test_second_allocate_same_picking_count`**, **`test_allocation_creates_picking_linked_moves`**.

---

## Transfer (picking) flow

**Why internal transfers:** Moves stock from the reservation **source location** (line / child locations) to an **in-warehouse staging** zone (pack location or internal-type default). This avoids forcing outbound customer delivery configuration in demo or mixed setups.

**Grouping:** Deterministic buckets by identical **`location_id`** and **`location_dest_id`**. Not heuristic route merging across incompatible pairs.

**Relationship:** **`stock.reservation.batch`** → lines → **`stock.move`** (`move_id`) → **`stock.picking`** (`picking_id`) → batch **`picking_ids`**. Smart button **Transfers** filters to **`picking_ids`**.

---

## Demo environment

> The module installs a ready-to-use demo environment with **no manual** warehouse or product setup required for the shipped scenarios (after install / hook run).

| Layer | Content |
| ----- | ------- |
| **Warehouse** | **Main Demo Warehouse (MDW, code `MDW`)** — standard Odoo warehouse create (receipt/delivery steps and routes as per core **stock**). |
| **Locations** | Under MDW stock: **Shelf A**, **Shelf B**, **Cold Zone** (FEFO removal strategy via `product_expiry`); optional **Quality Control** under the warehouse view location. Stock levels for demo products are applied by **`ensure_demo_stock`**, not only XML. |
| **Products** | **Demo Product A**, **Demo Product B**, **Demo Product C** (no stock); **Perishable Product X**, **Perishable Product Y** (lot / expiry where defined). Categories: **All / Reservation Demo**. |
| **Lots** | e.g. **LOT-X-001**, **LOT-X-002**, **LOT-Y-001** — Cold Zone FEFO demo; hook sets expiry so **LOT-X-001** is earlier than **LOT-X-002** for FEFO ordering. |
| **Stock distribution** | See **`hooks.ensure_demo_stock`** and README table under **Stock levels** — Shelf A/B split, partial stock, Cold Zone lots, empty lines. |

**Data files:** `data/demo_inventory_master.xml` (structure, templates, lots), `data/reservation_demo_data.xml` (users, tokens, sample batches). **`post_init_hook`** and migration **`18.0.1.5.0`** refresh quants idempotently.

---

## Functional flow

1. Create a **reservation batch**.
2. Add **lines** (product, requested qty, location; optional preferred lot).
3. **Confirm** the batch.
4. **Allocate** (UI or API): engine walks **`stock.quant`**, updates **`allocated_qty`** and line state.
5. For lines with **`allocated_qty > 0`**, create or refresh **`stock.move`** (destination = staging rule above).
6. **Generate pickings**: group moves without **`picking_id`**; create internal **Transfers**, confirm, link to **`picking_ids`**.
7. In Inventory, open the **Transfer**, optional **Check Availability**, then **Validate** when executing the physical move.

API **status** and existing integration points are unchanged.

---

## How to verify

1. **Upgrade** module **Stock Reservation Engine** (Apps → Upgrade, or `-u stock_reservation_engine`).
2. **Restart** the Odoo process if Python files were changed (reloads bytecode).
3. Open **Inventory → Stock Reservations → Reservation Batches** (or a demo batch).
4. **Confirm**, then **Allocate**.
5. On the batch form, open **Transfers** — expect at least one internal transfer when stock was allocated; **`origin`** matches batch name.
6. **Allocate** again on a **partial** batch (requested qty &gt; on hand): **picking count** and **picking ids** must stay stable (no duplicate picking for already-linked moves).

---

## Testing

### `TransactionCase` (`tests/test_reservation.py`)

| Area | Coverage |
| ---- | -------- |
| Full allocation | Allocated qty, move, batch state |
| Partial allocation | Partial line and batch |
| No stock | No move, no picking |
| FEFO | Skipped if lot expiry field unavailable in environment |
| Authorization | Non-owner/non-manager denied; owner and manager allowed |
| Move idempotency | **`test_second_allocate_does_not_duplicate_move`** |
| Picking creation | **`test_allocation_creates_picking_linked_moves`** — internal **`picking_type_id.code`**, **`origin`**, move on picking |
| No picking if no allocation | **`test_no_picking_when_nothing_allocated`** |
| Picking idempotency | **`test_second_allocate_same_picking_count`** |

### `HttpCase` (`tests/test_reservation_http.py`)

JSON-RPC **`POST`** to **`type='json'`** routes and **`GET`** status with **`Authorization: Bearer`**. Covers unauthorized / inactive token, validation errors, create → allocate success, forbidden / not-found paths, **`readonly_enabled = False`** where writes must be visible to the HTTP worker.

**Note:** Responses use the module’s JSON **`status` / `code`** shape. For **`401`**-class auth failures, behavior follows **`controllers/api.py`** (some paths return JSON body with **`ERR_UNAUTHORIZED`** on HTTP 200 JSON-RPC; align tests with actual implementation).

### Shell QA (`tools/qa_full_validation.py`)

Pipe into **`odoo-bin shell`** (same database as the server). Runs **`ensure_demo_stock`**, then **seven** scenarios: full allocation, partial, no stock, FEFO, child locations, **re-allocate idempotency** (partial batch), multi-line mixed. Asserts picking linkage where applicable. Writes **`TEST_EXECUTION_REPORT.md`** at module root.

---

## Known limitations

- **No `SELECT FOR UPDATE`** (or equivalent) on **`stock.quant`**. Concurrency relies on application guards (`allocation_in_progress`, state checks). High contention can still over-allocate across transactions.
- **`action_assign()`** on generated pickings is **not** automatic; operators run **Check Availability** if needed.
- **Multi-company**: logic uses **`company_id`** on the batch and standard domain filters; no extra cross-company isolation testing is implied.
- **Operation type / destination fallback** is **first matching Internal type** and **default destination** when pack location is missing — simplified, not a full routing engine.
- Batch **cancel** does **not** auto-cancel existing pickings.
- No per-quant audit table; line stores aggregate **`allocated_qty`** and a representative **`lot_id`** where applicable.
- No UoM conversion on lines (product UoM only).
- API: no built-in rate limiting; token stored as hash only.
- **`sudo()`** on some API helpers for token resolution; **`action_allocate`** runs **`with_user`** authenticated user.

---

## Architecture decisions

- **Batch + lines:** Request at batch level; allocation and moves per line for mixed outcomes.
- **`stock.quant`:** Availability = **`quantity - reserved_quantity`** (and domain filters).
- **FEFO then FIFO:** Expiry sort when lots expose expiration; else **`in_date`**, **`id`**.
- **One move per line:** Aligns business request granularity with **`stock.move`**.
- Picking generation is summarized in **Stock transfer (picking) generation** and **Transfer (picking) flow** above.

---

## API endpoints

### Create — `POST /api/reservation/create`

```json
{
  "priority": "2",
  "scheduled_date": "2026-04-20 10:00:00",
  "lines": [
    {"product_id": 10, "qty": 5, "location_id": 8},
    {"product_id": 20, "qty": 2, "location_id": 8}
  ]
}
```

### Allocate — `POST /api/reservation/allocate`

```json
{"batch_id": 12}
```

### Status — `GET /api/reservation/status/<id>`

### Authentication

`Authorization: Bearer <token>` — manage tokens under **Reservation API Tokens**.

---

## Demo reference tables

### Stock levels (`ensure_demo_stock`)

| Template (xml id) | Layout |
| ----------------- | ------ |
| `demo_pt_full` — Demo Product A | **35 + 35** on Shelf A and Shelf B ( **`child_of`** parent stock). |
| `demo_pt_partial` — Demo Product B | **12** on MDW lot stock root vs higher requests. |
| `demo_pt_empty` — Demo Product C | **No** stock. |
| `demo_pt_lots` — Perishable Product X | **LOT-X-001** / **LOT-X-002** in Cold Zone; hook sets earlier expiry on **LOT-X-001**. |
| `demo_pt_perishable_y` — Perishable Product Y | **No** stock for preferred-lot scenarios. |

### Users and API tokens (secrets stored hashed)

| Login | Groups | Bearer (demo xml id) |
| ----- | ------ | -------------------- |
| `admin` | Reservation Manager (demo) | `demo-reservation-api-token-change-me` (`demo_api_token`) |
| `demo_res_user` | Reservation User | `demo-res-user-api-token-change-me` (`demo_api_token_res_user`) |
| — | Inactive | `inactive-token-never-valid` — expect auth failure |

### Demo batches (xml ids)

| Xml id | Intent |
| ------ | ------ |
| `demo_batch_draft` | Draft → confirm → allocate (Product A). |
| `demo_batch_partial` | Product B partial. |
| `demo_batch_empty` | Product C not available. |
| `demo_batch_mixed` | Mixed line outcomes. |
| `demo_batch_dual_full` | Two lines → allocated. |
| `demo_batch_cancelled` / `demo_batch_done` | Terminal states. |
| `demo_batch_lot_ok` / `demo_batch_lot_bad` | Lot preference with/without stock. |
| `demo_batch_fefo` | FEFO from Cold Zone. |
| `demo_batch_shelf_parent` | **`child_of`** from parent stock. |
| `demo_batch_demo_user_owned` | Owned by **`demo_res_user`** (rules / API). |

---

## Security model

- Reservation **User**: own batches/lines.
- **Manager**: all batches.
- **`action_allocate`**: **`AccessError`** unless **Manager** or **owner** (`request_user_id`). Enforced on RPC and API (**`with_user`** for API identity).

---

## Performance strategy

- Per line: one **`stock.quant`** search (FEFO may sort in Python when expiry applies).
- Logging: **`Allocation line timing`** (`elapsed_ms`), **`Finished allocation`** (`total_elapsed_ms`).
- Scaling: possible future batching of lines by product/location to reuse quant reads.

---

## Database design

- Indexes: relies on core **`stock.quant`** / line foreign keys; see model definitions.
- Constraints: **`requested_qty > 0`**, **`allocated_qty`**, **`allocated_qty ≤ requested_qty`**.

---

## Concurrency strategy

Application-level: states, **`allocation_in_progress`**, single move per line refresh, picking skip when **`picking_id`** set. **Not** a substitute for database row locking under high contention.

---

## Code reference (models)

### `stock.reservation.batch`

| Kind | Name | Role |
| ---- | ---- | ---- |
| Override | `create` | Sequence when name is **New**. |
| Compute | `_compute_move_count` / `_compute_picking_count` | Smart button counts. |
| Button | `action_confirm` / `action_cancel` / `action_mark_done` | Lifecycle. |
| Button | `action_allocate` | **`_action_allocate_single`**, then **`_generate_pickings_from_allocated_moves`**. |
| Core | `_allocate_line`, `_get_quant_order`, `_compute_line_state`, `_compute_batch_state` | Allocation engine. |
| Core | `_get_reservation_destination_location`, `_get_internal_picking_type` | Staging destination and internal type. |
| Core | `_group_moves_for_pickings`, `_create_picking_for_moves`, `_generate_pickings_from_allocated_moves` | Picking generation. |
| Core | `_create_stock_move_for_line` | Move from line location to staging destination. |
| Button | `action_view_moves` / `action_view_pickings` | Window actions. |

### `stock.reservation.line`

Constraints on quantities; **`move_id`**, **`picking_id`** related from move.

### `reservation.api.token`

SHA-256 storage for secrets.

### HTTP (`controllers/api.py`)

Routes **`/api/reservation/create`**, **`allocate`**, **`status/<id>`**; **`_authenticate`**, **`_json_error`**.

---

## Sprint plan (historical)

Roughly six hours across model/security UI, allocation engine, API, tests, demo data, **`ensure_demo_stock`**, migrations, screenshot tooling, documentation.

---

## Installation

1. Addons path contains **`stock_reservation_engine`**.
2. Update apps list; install **Stock Reservation Engine**.
3. Assign **Stock Reservation User** or **Stock Reservation Manager**.
4. Create API tokens if needed.

---

## Future improvements

- Row-level locking on candidate quants + transactional retry.
- Quant-level allocation trace model.
- Batch scheduling / priority across competing batches.
- API versioning, structured error taxonomy, rate limiting.
- Token expiry and scopes.
- Optional auto-cancel pickings when batch cancelled.
