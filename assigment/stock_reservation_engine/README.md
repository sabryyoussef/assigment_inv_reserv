# Stock Reservation Engine

## Overview
This module adds a custom reservation and allocation layer on top of Odoo Inventory. It allows a user or an external system to create a reservation batch, allocate stock proactively from `stock.quant`, apply FEFO when lot expiration data exists, fall back to FIFO otherwise, and generate `stock.move` records that reflect the allocated quantity.

The objective is to support high-volume scenarios where competing demands may request the same stock before normal fulfillment flows are executed.

## Screenshots

Screenshots ship under Odoo’s standard asset path **`static/description/screenshots/`** (available in the Apps UI when listed, and ideal for README / assignment packages).

| Folder | Script | Purpose |
|--------|--------|---------|
| `static/description/screenshots/capture/` | `tools/screenshots/` → `npm run capture` | Broad inventory + reservation UI tour |
| `static/description/screenshots/walkthrough/` | `tools/screenshots/` → `npm run walkthrough` | Structured assignment walkthrough ([index](static/description/screenshots/walkthrough/SCREENSHOTS_INDEX.md)) |

**Examples** (refresh PNGs after install with demo data):

![Reservation batches list](static/description/screenshots/capture/04-reservation-batches-list.png)

![Reservation batch draft state](static/description/screenshots/capture/06-reservation-batch-draft.png)

![Stock Reservations reporting menu](static/description/screenshots/capture/28-reporting-menu-expanded.png)

Full procedure: [static/description/screenshots/README.md](static/description/screenshots/README.md).

## Scope delivered
- Custom models:
  - `stock.reservation.batch`
  - `stock.reservation.line`
  - `reservation.api.token`
- Allocation engine based on `stock.quant`
- FEFO / FIFO ordering
- Partial allocation support
- Generated `stock.move` per line when allocated quantity is greater than zero
- **`stock.picking`** internal transfers linked to those moves with **Transfers** smart button on the batch
- JSON HTTP API (`/api/reservation/create`, `/api/reservation/allocate`, `/api/reservation/status/<id>`) with Bearer token authentication
- Security groups, record rules, and server-side enforcement on allocate (owner or manager)
- Tree and form views with **Stock Moves** smart button
- **Automated tests**: `TransactionCase` (allocation paths, authorization, idempotent re-allocate); **`HttpCase`** for API errors and success paths (create, allocate, status — unauthorized, validation, forbidden, not found)
- **Install-ready demo**: MDW warehouse, locations, products, lots, sample batches, demo users/API tokens (`data/demo_inventory_master.xml`, `data/reservation_demo_data.xml`)
- **`hooks.ensure_demo_stock`**: idempotent quant levels via `post_init_hook` and migration **`18.0.1.5.0`**
- **UI capture tooling**: Playwright scripts under `tools/screenshots/`; PNG outputs and indexes under `static/description/screenshots/`
- **Documentation**: this README; `docs/REQUIREMENTS_VS_IMPLEMENTATION.md`, `docs/TEST_REPORT.md`, assignment notes under `docs/`

## Architecture Decisions
### Why Batch + Lines
The batch model acts as the business request container. The line model acts as the execution unit. Allocation is executed per line to keep the logic granular and to support mixed results inside one batch.

### Why `stock.quant`
`stock.quant` is the correct source for current physical stock availability. The engine calculates available quantity as:

`available_qty = quantity - reserved_quantity`

### Why FEFO then FIFO
If lots with valid expiration dates exist, the engine prioritizes the earliest expiration date first. Otherwise it falls back to FIFO using `in_date`, keeping stock selection deterministic.

### Why one move per line
The business request exists at line level, not quant level. Therefore the module generates one `stock.move` per line using the final allocated quantity, while keeping quant-level allocation abstracted.

### Transfer (`stock.picking`) generation
Allocated moves move product from each line’s **source location** to the warehouse **Packing / staging zone** (`wh_pack_stock_loc_id` when present), producing **internal transfer** operation types. That keeps behavior safe in demo databases (no mandatory customer delivery setup).

After allocation completes, moves that still need a transfer are grouped by **(`location_id`, `location_dest_id`)**. Each group becomes **one picking** — so batches where every line shares the same source→destination pair yield **one picking**; mixed incompatible pairs split into multiple pickings (deterministic grouping, not heuristic merging across different routes).

Pickings receive **`origin = batch.name`** and **`scheduled_date`** from `batch.scheduled_date` when set. The picking is **`action_confirm()`’d** so it appears under **Inventory → Operations** like a normal transfer; **`action_assign()` is not called automatically**: allocation quantity already came from `stock.quant`; users can run **Check Availability** on the transfer when they want Odoo’s reservation layer aligned with warehouse configuration.

Moves that already belong to a picking are skipped on re-allocation — no duplicate transfers when **Allocate** is clicked again.

## Functional Flow
1. User creates a reservation batch.
2. User adds one or more lines.
3. User confirms the batch.
4. User or API calls Allocate.
5. The engine searches `stock.quant` by product, location, and child locations.
6. It orders quants using FEFO or FIFO.
7. It calculates allocated quantity and updates line state.
8. If allocated quantity is greater than zero, it creates or updates a `stock.move`.
9. Batch state is derived from line states.
10. For moves without a picking, the engine creates **`stock.picking`** records (internal transfers), links the moves, confirms them, and attaches them to the batch (`picking_ids`).
11. External systems can query the status endpoint (unchanged).

### Limitations
- Transfers assume the company has at least one **Internal** operation type and a resolvable **staging destination** (warehouse pack location or internal operation defaults). Otherwise allocation still completes for moves, but picking creation raises a clear configuration error when building the transfer.
- Cancelling a reservation batch does **not** auto-cancel existing pickings (optional future enhancement).

## Sprint plan (~6 hours total)

Work was compressed into roughly three two-hour segments (same scope as the original multi-day outline).

### Hours 1–2
- Designed data model and states
- Implemented security groups, record rules, and access rights
- Built basic menu, tree view, and form view
- Added batch sequence

### Hours 3–4
- Implemented allocation engine
- Added FEFO / FIFO ordering
- Added partial allocation support
- Added stock move generation and smart button

### Hours 5–6
- Implemented JSON APIs and token authentication
- Expanded automated tests (transaction + HTTP/API coverage)
- Wrote and iterated README (architecture, performance, concurrency, demo, screenshots)
- Added lightweight application-level protection against double processing (`allocation_in_progress`, skip lines already allocated with moves)
- Added install-ready demo XML, **`ensure_demo_stock`** hook, and upgrade migration for demo stock
- Added Playwright screenshot tooling and packaged assets under **`static/description/screenshots/`**
- Added supplementary docs under **`docs/`** (requirements mapping, test report)

### Stretch goals / not implemented (by design)
These are **optional production or v2 features**, not gaps in the delivered assignment:

- **SQL row-level locking** on `stock.quant` (`SELECT FOR UPDATE`) was not added; the core flow uses application-level guards (see **Concurrency Strategy**).
- **Per-quant allocation audit table** was not added; the reservation line stores aggregate allocated quantity and (where applicable) a representative lot reference.

## API Endpoints
### Create reservation
`POST /api/reservation/create`

Example payload:
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

### Allocate reservation
`POST /api/reservation/allocate`

Example payload:
```json
{
  "batch_id": 12
}
```

### Reservation status
`GET /api/reservation/status/<id>`

### Authentication
The API expects a bearer token:

`Authorization: Bearer <token>`

Tokens are managed using the `Reservation API Tokens` menu.

## Demo environment (install-ready)
The module ships a **self-contained demo** for clean databases: warehouse **Main Demo Warehouse (MDW)**, internal sub-locations, product categories under **All / Reservation Demo**, storable demo products, lot-tracked perishables with **Products Expiration Date** (`product_expiry` dependency), and sample reservation batches. No manual inventory structure is required to try allocation.

### Data files
| File | Role |
|------|------|
| `data/demo_inventory_master.xml` | Company-scoped **MDW** warehouse (code `MDW`, standard receipt/delivery steps and routes from core `stock`), sub-locations (*Shelf A*, *Shelf B*, *Cold Zone* with FEFO removal strategy, optional *Quality Control*), product categories, product templates, lots (`LOT-X-001`, `LOT-X-002`, `LOT-Y-001`). |
| `data/reservation_demo_data.xml` | Users, API token records, reservation batches/lines referencing MDW stock. |

**Accounting:** demo uses default product categories and Odoo inventory configuration. No extra chart of accounts, journals, or valuation modes are introduced; add only if your company policy requires them.

### Stock levels (`hooks.ensure_demo_stock`)
Quantities are **not** stored in XML; `hooks.ensure_demo_stock()` adjusts `stock.quant` idempotently (safe to replay). Triggers:
- **`post_init_hook`** on first install.
- **`migrations/18.0.1.5.0/post-demo_stock.py`** when upgrading to **18.0.1.5.0+** (and the earlier migration for 18.0.1.0.2 remains for older upgrades).

| Product (template xml id) | Inventory layout |
|---------------------------|------------------|
| `demo_pt_full` — *Demo Product A* | **35 + 35** units on **Shelf A** and **Shelf B** under MDW/Stock (none on the stock root — exercises `child_of`). |
| `demo_pt_partial` — *Demo Product B* | **12** units on MDW **lot stock** root — partial vs **40** requested on `demo_batch_partial`. |
| `demo_pt_empty` — *Demo Product C* | **No** stock. |
| `demo_pt_lots` — *Perishable Product X* | **LOT-X-001**: **12** units in **Cold Zone**; **LOT-X-002**: **14** units in **Cold Zone**. Expiration dates set in the hook so **LOT-X-001** expires sooner (FEFO ordering). |
| `demo_pt_perishable_y` — *Perishable Product Y* | **No** stock (preferred-lot-not-available demo). |

### Users & API tokens (plaintext secrets — stored hashed)
| Login / name | Groups | Bearer secret (if applicable) |
|----------------|--------|-------------------------------|
| `admin` | Multi-warehouses, **Reservation Manager** (demo data) | `demo-reservation-api-token-change-me` (`demo_api_token`) |
| `demo_res_user` | Internal, stock user, multi-warehouses, **Reservation User** | `demo-res-user-api-token-change-me` (`demo_api_token_res_user`) |
| — | Inactive token record | `inactive-token-never-valid` (`demo_api_token_inactive`, `active=False`) — expect 401 |

### Reservation batches (xml ids) — quick checks
| Batch xml:id | Intent |
|--------------|--------|
| `demo_batch_draft` | Draft → **Confirm** → **Allocate** (Demo Product A). |
| `demo_batch_partial` | Partial line vs on-hand Demo Product B. |
| `demo_batch_empty` | Demo Product C — **not_available**. |
| `demo_batch_mixed` | Mixed line outcomes in one allocate. |
| `demo_batch_dual_full` | Two lines; batch can reach **allocated**. |
| `demo_batch_cancelled` | Cancelled snapshot. |
| `demo_batch_done` | Done snapshot. |
| `demo_batch_lot_ok` | Perishable X + preferred **LOT-X-001** with stock. |
| `demo_batch_lot_bad` | Perishable Y + preferred **LOT-Y-001**, **no** stock. |
| `demo_batch_fefo` | Perishable X — multi-lot FEFO from Cold Zone. |
| `demo_batch_shelf_parent` | Parent MDW/Stock line; quantity only under Shelf A/B (`child_of`). |
| `demo_batch_demo_user_owned` | Owned by `demo_res_user` (record rules / API). |

**Quick test:** Install module → **Inventory → Configuration → Warehouses** → open **Main Demo Warehouse** → review locations; **Reservation** menu → open `demo_batch_draft` → Confirm → Allocate.

To strip demo artefacts from a database, remove related records or restore a backup.

## Code reference (models & controllers)

### `stock.reservation.batch`
| Kind | Name | Role |
|------|------|------|
| Override | `create` | Assigns sequence `stock.reservation.batch` when `name` is `New`. |
| Compute | `_compute_move_count` | Counts lines that have a `stock.move`. |
| Button | `action_confirm` | Requires lines; sets batch `state` to `confirmed`. |
| Button | `action_cancel` | Cancels non-allocated lines; batch `cancelled`. |
| Button | `action_mark_done` | Sets batch `done`. |
| Button | `action_allocate` → `_action_allocate_single` | Runs allocation loop; guards with `allocation_in_progress` and valid states. |
| Core | `_allocate_line` | Walks `stock.quant` (FIFO by DB order or FEFO via Python sort when expiry lots exist); returns `allocated_qty` and first `lot_id` consumed. |
| Core | `_get_quant_order` | Returns whether to apply FEFO (any quant with lot + expiration on this product/location). |
| Core | `_compute_line_state` | Maps requested vs allocated → `not_available` / `partial` / `allocated`. |
| Core | `_compute_batch_state` | Aggregates line states into batch `draft` / `confirmed` / `partial` / `allocated` / `cancelled`. |
| Core | `_create_stock_move_for_line` | Creates `stock.move` from line location to `stock.stock_location_output` for allocated qty. |
| Button | `action_view_moves` | Opens stock moves for all lines (smart button). |

### `stock.reservation.line`
| Kind | Name | Role |
|------|------|------|
| Constraint | `_check_allocated_qty` | Ensures `allocated_qty` ≤ `requested_qty`. |
| SQL | *(constraints)* | `requested_qty > 0`, `allocated_qty >= 0`. |

### `reservation.api.token`
| Kind | Name | Role |
|------|------|------|
| Helper | `_hash_token` | SHA-256 hex digest of raw secret. |
| Override | `create` / `write` | Hashes `token` field on store. |

### HTTP (`controllers/api.py`)
| Route | Method | Handler | Behavior |
|-------|--------|---------|----------|
| `/api/reservation/create` | POST JSON | `create_reservation` | Bearer auth; builds batch + optional `auto_confirm`. |
| `/api/reservation/allocate` | POST JSON | `allocate_reservation` | Bearer auth; owner or manager; calls `action_allocate`. |
| `/api/reservation/status/<batch_id>` | GET | `reservation_status` | JSON detail of batch and lines. |
| *(helpers)* | | `_get_bearer_token`, `_authenticate`, `_json_error` | Authorization header parsing and token lookup (hashed match). |

## Security Model
- Reservation users can access only their own batches and lines.
- Reservation managers can access all records.
- **`action_allocate` is enforced on the server** (`AccessError` if unauthorized): callers must be either **Stock Reservation Manager** or the **batch owner** (`request_user_id`). UI button visibility may still narrow who sees **Allocate**, but RPC and API calls cannot bypass this check.
- API access is token-based and resolves to an Odoo user; API handlers call batch methods **with that user** (`with_user`) so authorization runs as the authenticated identity, not only as UI restrictions.

## Performance Strategy
### Avoiding N+1 queries
Each reservation line performs a **`stock.quant` `search`** for that line’s product/location (and optional lot domain). Candidate quants are then consumed in a single pass for that line (FEFO may apply an additional ordering pass when expiry data exists).

### Critical query
The most important query is the `stock.quant` lookup filtered by:
- `product_id`
- `location_id` with `child_of`
- `company_id`
- `quantity > 0`
- optional `lot_id`

### Scaling approach
The current implementation is intentionally simple and clear. A future optimization would group lines by product and location to reuse quant result sets and reduce repeated searches when many lines target the same product.

### Sample log output
Allocation emits **INFO** lines from `reservation_batch` with wall-clock timings using `time.perf_counter()`:

- **`Allocation line timing`** — `elapsed_ms` for each processed line (quant search + line writes + move create/update for that line).
- **`Finished allocation`** — `total_elapsed_ms` for the whole batch pass (excluding the “Starting” line and the `allocation_in_progress` flag write).

Example (2-line batch; values vary with DB and load):

```
... INFO odoo18 odoo.addons.stock_reservation_engine.models.reservation_batch: Starting allocation for reservation batch RES00018 user=admin id=2
... INFO odoo18 odoo.addons.stock_reservation_engine.models.reservation_batch: Allocation line timing batch=RES00018 line_id=101 product_id=42 elapsed_ms=48.23 allocated_qty=5.0
... INFO odoo18 odoo.addons.stock_reservation_engine.models.reservation_batch: Allocation line timing batch=RES00018 line_id=102 product_id=43 elapsed_ms=52.11 allocated_qty=3.0
... INFO odoo18 odoo.addons.stock_reservation_engine.models.reservation_batch: Finished allocation for reservation batch RES00018 state=allocated lines=2 moves=2 total_elapsed_ms=101.05
```

### Time complexity
At a high level, allocation is linear in relation to the number of candidate quants returned for a line. Database ordering keeps the complexity predictable and avoids Python-side sorting overhead.

## Database Design
### Indexes
The module relies on indexes that matter for allocation lookups and joins.

Recommended / used indexes:
- `stock.quant(product_id)`
- `stock.quant(location_id)`
- `stock.quant(lot_id)`
- `stock.reservation.line(batch_id)`
- `stock.reservation.line(product_id)`
- `reservation.api.token(token)`

### Constraints
- `requested_qty > 0`
- `allocated_qty >= 0`
- ORM constraint to prevent `allocated_qty > requested_qty`

These constraints keep reservation data valid and guard against inconsistent updates.

## Concurrency Strategy
Concurrency is handled at the **application level** in this module. **Database row locking** (`SELECT FOR UPDATE` on `stock.quant` or related rows) is **not** implemented here; it remains a future hardening step for high-contention deployments.

### Current implementation
The module includes lightweight application-level protection using:
- state guards
- `allocation_in_progress` flag
- duplicate move prevention (one move per line; refresh qty on re-allocation)
- skipping lines that are already fully allocated with an existing move

This reduces accidental double processing from repeated clicks or repeated API calls.

### Risk
Two concurrent transactions may still read the same available quantity before commit, which can lead to over-allocation in high-contention scenarios.

### Production-grade mitigation
For production-grade concurrency safety, the next step would be:
1. Lock candidate `stock.quant` rows with `SELECT ... FOR UPDATE`
2. Execute allocation inside a single transaction
3. Optionally add retry logic for lock contention or serialization failures

## Testing

### Transaction tests (`tests/test_reservation.py`)
- Allocation: **full**, **partial**, **no stock**, **FEFO** (preferred lot context)
- Batch lifecycle: cancel-all-lines state, confirm without lines (error)
- **`action_allocate`** authorization: denied for neither owner nor manager; allowed for owner and for manager on another user’s batch
- Re-running allocate on an already satisfied line does **not** duplicate **`stock.move`**

### HTTP / API tests (`tests/test_reservation_http.py`)
Uses JSON-RPC **`POST`** bodies to `type='json'` routes (`/api/reservation/create`, `/api/reservation/allocate`) and **`GET`** `/api/reservation/status/<id>` with **`Authorization: Bearer`**.

Includes: unauthorized / inactive token; validation (empty lines, bad line shape); **create → allocate** success path; allocate unauthorized / missing batch / not found / forbidden (non-owner); status unauthorized / not found / forbidden / success.

`HttpCase` runs with **`readonly_enabled = False`** where writes are required so the HTTP layer sees created tokens/quants (**`flush_all`** where appropriate).

## Known Limitations
- Full database-level locking is not implemented. The `allocation_in_progress` flag is an application-level guard only. In a multi-worker environment two concurrent transactions can still read the same available quantity before either commits, potentially causing over-allocation. The production-grade solution is to lock candidate `stock.quant` rows with `SELECT ... FOR UPDATE` before the allocation loop.
- No picking generation. The module generates `stock.move` records but does not create full `stock.picking` objects.
- No quant allocation trace table. The chosen lot is stored on the line for traceability, but per-quant breakdown is not persisted.
- FEFO stores the first chosen lot on the line. It does not persist a quant-by-quant breakdown.
- No UoM conversion on reservation lines. The `uom_id` is taken from `product_id.uom_id` only. Lines with a different requested unit of measure are not supported.
- API tokens are stored as **SHA-256** hashes; only the hash is persisted. Raw secrets cannot be read back from the database after save—issue a new token if you lose the secret.
- The API has no built-in rate limiting. For production, add throttling at the reverse proxy or API gateway.
- Create/list paths still use `sudo()` where needed for cross-company/token lookup; sensitive actions (`action_allocate`, `action_confirm`) are invoked **with the authenticated API user** so record rules and `has_group` checks apply correctly.

## Installation
1. Copy the module folder into your custom addons path.
2. Update the app list.
3. Install **Stock Reservation Engine**.
4. Grant users either:
   - `Stock Reservation User`
   - `Stock Reservation Manager`
5. Create API tokens from **Inventory > Stock Reservations > API Tokens** if external access is needed.

## Manual test scenarios

With **demo data** installed, you can open **Inventory → Stock Reservations → Reservation Batches** and use the pre-built batches in the **Reservation batches (xml ids)** table below (e.g. `demo_batch_draft`, `demo_batch_partial`, `demo_batch_fefo`) instead of creating products and quants from scratch.

### Scenario 1: Full allocation
- **Demo shortcut:** open batch **`demo_batch_dual_full`** (or draft flow with Product A), **Allocate**.
- **From scratch:** create on-hand stock, add a batch line with requested quantity lower than available, confirm and allocate.
- **Expected:** line state **`allocated`**, **`stock.move`** created when allocated quantity &gt; 0.

### Scenario 2: Partial allocation
- **Demo shortcut:** **`demo_batch_partial`** after **Allocate** (Demo Product B vs 40 requested, 12 on hand).
- **Expected:** line **`partial`**, allocated quantity &lt; requested.

### Scenario 3: No stock
- **Demo shortcut:** **`demo_batch_empty`** (Demo Product C), **Allocate**.
- **Expected:** line **`not_available`**, no move.

### Scenario 4: FEFO behavior
- **Demo shortcut:** **`demo_batch_fefo`** with Perishable X stock in **Cold Zone** (two lots; hook sets earlier expiry on LOT-X-001).
- **Expected:** allocation consumes earlier-expiring lot stock first; line shows aggregate result (see **Known Limitations** for stored detail).

## Future Improvements
- Full concurrency-safe allocation with SQL row locking (`SELECT FOR UPDATE` on `stock.quant`)
- Quant allocation trace model for full per-quant breakdown
- Picking generation from allocated moves
- Batch priority scheduling across multiple pending reservations
- API versioning and structured error codes
- API token expiry dates and scope restrictions
- Rate limiting at API layer
