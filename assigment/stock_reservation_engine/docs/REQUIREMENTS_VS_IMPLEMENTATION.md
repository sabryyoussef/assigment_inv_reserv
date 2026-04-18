# Assignment requirements vs current implementation

This document maps the **original brief** (`ORIGINAL_ASSIGNMENT.md`) to **what the codebase delivers today**, and lists **gaps / follow-ups**.

Legend: **Done** = implemented and usable | **Done (extended)** = requirement met and intentionally augmented | **Done (design-level)** = meets brief’s “design / explain” scope, not full production implementation | **Partial** = simplified, conditional, or layered (see notes) | **Missing** = not delivered | **Extra** = beyond the brief.

---

## 1. Functional requirements

| Requirement | Status | Evidence / notes |
|-------------|--------|------------------|
| **`stock.reservation.batch`**: sequence `name`, `request_user_id`, `line_ids`, `state`, `priority`, `scheduled_date` | **Done** | `models/reservation_batch.py`, `data/sequence.xml` |
| Batch `state`: draft, confirmed, allocated, done, cancelled *(as per assignment)* | **Done (extended)** | All required states are present; an additional **`partial`** state models mixed line outcomes without misusing “allocated”. See `state` in `reservation_batch.py`. |
| **`stock.reservation.line`**: batch, product, requested/allocated qty, location, optional lot, state, `move_id` | **Done** | `models/reservation_line.py` |
| Extra model **`reservation.api.token`** + hashing | **Extra** | Supports token auth; `models/api_token.py` |
| **`company_id`**, chatter (`mail.thread`) on batch | **Extra** | Multi-company and messaging; not required by brief |

### Allocation engine

| Requirement | Status | Evidence / notes |
|-------------|--------|------------------|
| Allocate from **`stock.quant`** | **Done** | `_allocate_line`, `_action_allocate_single` |
| **FEFO** when expiry lots exist | **Done** *(conditional on data)* | Ordering logic is implemented: when lots expose expiration metadata (e.g. `lot_id.expiration_date` with **`product_expiry`** or equivalent), quants are sorted by earliest expiry then FIFO. If no expiry fields are present, behavior correctly degrades to FIFO-only—an **environment/module** dependency, not a missing algorithm. |
| Otherwise **FIFO** | **Done** | `search(..., order='in_date asc, id asc')` with explicit resort when FEFO applies |
| **Location + child locations** (`child_of`) | **Done** | Domain uses `child_of` on `location_id` |
| **Partial** allocation | **Done** | Line states `partial` / `not_available`; `allocated_qty` updated |
| Update **`allocated_qty`** and line **state** | **Done** | `_compute_line_state`, writes on line |

### Stock integration

| Requirement | Status | Evidence / notes |
|-------------|--------|------------------|
| Generate **`stock.move`** after allocation | **Done** | `_create_stock_move_for_line`; destination via `_get_reservation_destination_location` (warehouse **Pack** location, else internal picking type **default destination**; **`UserError`** if neither resolvable) |
| Link move to line (`move_id`) | **Done** | `reservation_line.move_id` |
| Moves reflect **allocated** quantities | **Done** | `product_uom_qty` = allocated qty (refreshed on re-allocate) |

| Feature | Status | Notes |
|---------|--------|-------|
| **Picking generation** | **Implemented** | Internal **`stock.picking`** per **`(location_id, location_dest_id)`** group; **`origin`** = batch name; **`action_confirm`** only — **`action_assign`** not automated; **`picking_ids`** on batch; moves with **`picking_id`** skipped on re-run (**idempotent**) |

**Design:** Internal transfers avoid mandatory outbound/customer flows in demo or mixed warehouses. **Limitation:** Fallback internal operation type is **first match** by company — not a full routing solver; multi-company edge cases rely on Odoo defaults.

### API layer

| Requirement | Status | Evidence / notes |
|-------------|--------|------------------|
| `POST /api/reservation/create` | **Done** | `controllers/api.py` → `create_reservation` |
| `POST /api/reservation/allocate` | **Done** | `allocate_reservation` |
| `GET /api/reservation/status/<id>` | **Done** | `reservation_status` |
| Token-based auth (Bearer) | **Done** | `_authenticate`, `reservation.api.token` |
| Clear JSON errors | **Done** | Consistent **`status`** / **`message`** / **`code`** (e.g. `ERR_UNAUTHORIZED`, `ERR_VALIDATION`) on JSON-RPC bodies; GET routes use HTTP status plus the same payload shape. |
| Clean request/response | **Done** | Structured payloads; see README API section |

### UI

| Requirement | Status | Evidence / notes |
|-------------|--------|------------------|
| Tree + form | **Done** | `views/reservation_batch_views.xml` (`list`, `form`) |
| Smart button → related stock moves | **Done** | `action_view_moves`, `move_count` (inline `ir.actions.act_window` dict — no dependency on **`stock.stock_move_action`** / legacy menu XML ids) |
| Smart button → transfers | **Done** | `action_view_pickings`, `picking_count`, `picking_ids` |

| Feature | Status | Notes |
|---------|--------|-------|
| **Dashboard / reporting** | **Implemented** | **`views/reservation_dashboard_views.xml`**: native **Graph** (bar, stacked by state/product; measures `requested_qty`, `allocated_qty`) + **Pivot** (rows `product_id`, cols `state`, same measures on **`stock.reservation.line`**). Menu **Stock Reservations → Dashboard** (`action_reservation_dashboard`). **No automated tests** for dashboard views (manual verification). |

### Security

| Requirement | Status | Evidence / notes |
|-------------|--------|------------------|
| Users see **own** reservations | **Done** | `security/reservation_security.xml` record rules on batch and lines |
| Managers see **all** | **Done** | Manager group + rules / full access where applicable |
| Allocation restricted to **authorized** users | **Done** | **Server-side:** `_check_allocate_authorization` on `action_allocate` raises **`AccessError`** unless the user is **Reservation Manager** (`has_group`) **or** the batch **owner** (`request_user_id`). Applies to RPC, buttons, and API paths that call `action_allocate`. UI button groups may further limit visibility; enforcement is not UI-only. |

---

## 2. Engineering requirements (mandatory sections)

| Deliverable | Status | Where |
|-------------|--------|--------|
| **Sprint plan** (3 days, priorities, what was **not** done) | **Done** | `README.md` — “Sprint plan (historical)” |
| **Tests** (3–5+ cases: allocation, partial, no stock) | **Done** | `tests/test_reservation.py`: full, partial, no stock, FEFO when expiry fields exist (skip otherwise), cancel batch, confirm without lines, allocate auth, **picking linkage**, **no picking without stock**, **re-allocate picking idempotency**. **`tests/test_reservation_http.py`**: JSON-RPC API routes and Bearer auth. **`tools/qa_full_validation.py`**: seven ORM scenarios including picking and idempotency → **`TEST_EXECUTION_REPORT.md`**. |
| **Performance** (N+1, critical queries, scaling, complexity) | **Done** | `README.md` — “Performance strategy” |
| **Database** (indexes, constraints) | **Done** | `README.md` — “Database design” |
| **Concurrency** (risks + proposed mitigation, **design level**) | **Done (design-level, as per assignment)** | `README.md` — “Concurrency strategy”; **`allocation_in_progress`**, skip moves already on pickings — **application-level**; row-level DB locking documented as future work. |

---

## 3. README checklist (assignment section G + structure)

| Section | Status |
|---------|--------|
| A. Architecture / how allocation works | **Done** (`README.md`) |
| B. Sprint plan | **Done** |
| C. Performance strategy | **Done** |
| D. Database design | **Done** |
| E. Concurrency strategy | **Done** |
| F. Testing | **Done** |
| G. Known limitations | **Done** |

---

## 4. Bonus items (optional)

| Bonus | Status |
|-------|--------|
| Concurrency-safe allocation (DB locking) | **Missing** (documented; optional beyond brief) |
| Picking generation from moves | **Done** — internal transfer **`stock.picking`** grouped by **`(location_id, location_dest_id)`**; **`picking_ids`** + **Transfers** smart button; confirm without auto-assign (see README **Stock transfer (picking) generation**) |
| Profiling / timings in logs | **Done** — INFO **`Allocation line timing`** (`elapsed_ms` per line) and **`Finished allocation`** (`total_elapsed_ms`) |
| Kanban | **Missing** |
| Lightweight reporting dashboard (graph/pivot on lines) | **Done (extra)** — see README **Reservation dashboard**; not Kanban |
| Advanced API (versioning, machine-readable error codes) | **Partial** (basic **`code`** strings on errors; versioning / prefixes not implemented) |
| Test automation plan | **Partial** (Odoo tests in-repo; CI pipeline not documented) |

---

## Supplement: picking generation behavior

| Item | Notes |
|------|--------|
| **`picking_ids`** | Many2many on **`stock.reservation.batch`** linking generated transfers |
| **`picking_id`** | Related on **`stock.reservation.line`** from **`move_id.picking_id`** |
| **Grouping** | Moves grouped by `(location_id, location_dest_id)`; **one picking per group** |
| **Confirm vs assign** | **`action_confirm()`** on picking; **`action_assign()`** left to users |

---

## 5. Demo data & hooks (not in original brief)

| Item | Notes |
|------|--------|
| `data/reservation_demo_data.xml`, `hooks.py`, migration `18.0.1.0.2` | **Extra** — accelerates manual QA; idempotent stock setup |

---

## 6. Summary: what remains / suggested next steps

**High value (production hardening beyond assignment scope)**

1. **Row-level locking** on candidate `stock.quant` (or equivalent) + transactional allocation if strict concurrency safety is required in production.
2. Ensure **expiration fields** on lots in deployed environments (e.g. **`product_expiry`**) so FEFO paths are **observable in QA**—the implementation already consumes metadata when present.
3. **API hardening**: optional error **codes**, rate limiting, narrower `sudo()` patterns (see README).

**Medium**

4. Optional **delivery / outbound** chaining from staging if the business requires customer shipments from reservation output (not in current scope).
5. Extend **HTTP-level tests** if regression coverage for additional edge routes is required (many paths already covered in **`test_reservation_http.py`**).

**Nice-to-have**

7. Kanban board view; structured profiling timers; CI checklist for automated tests. (Native graph/pivot dashboard is already implemented.)

The implementation **satisfies the assignment scope** and demonstrates **solid engineering practices**, while **clearly separating** optional production-grade enhancements as **documented future work**.

---

## 7. Quick compliance scorecard

| Area | Met? |
|------|------|
| Working module + custom models + allocation + moves + API + UI + security | **Yes** |
| README engineering sections (sprint, performance, DB, concurrency, tests, limitations) | **Yes** |
| Automated tests ≥ minimal scenarios | **Yes** (`tests/test_reservation.py` ~15 **`TransactionCase`** methods including picking and idempotency; **`test_reservation_http.py`**; shell QA script — FEFO test skips if expiry metadata unavailable) |
| Bonus / optional hardening | **Mixed** — intentionally scoped; documented where not pursued |

For the authoritative wording of the assignment, see **`ORIGINAL_ASSIGNMENT.md`**.
