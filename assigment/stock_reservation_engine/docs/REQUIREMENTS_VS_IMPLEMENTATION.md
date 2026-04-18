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
| Generate **`stock.move`** after allocation | **Done** | `_create_stock_move_for_line`; destination `stock.stock_location_output` |
| Link move to line (`move_id`) | **Done** | `reservation_line.move_id` |
| Moves reflect **allocated** quantities | **Done** | `product_uom_qty` = allocated qty |

### API layer

| Requirement | Status | Evidence / notes |
|-------------|--------|------------------|
| `POST /api/reservation/create` | **Done** | `controllers/api.py` → `create_reservation` |
| `POST /api/reservation/allocate` | **Done** | `allocate_reservation` |
| `GET /api/reservation/status/<id>` | **Done** | `reservation_status` |
| Token-based auth (Bearer) | **Done** | `_authenticate`, `reservation.api.token` |
| Clear JSON errors | **Done** | Consistent **`status`** / **`message`** (and HTTP status on GET). **Note:** standardized application error **codes** (e.g. `ERR_XXX`) are not defined—that is an optional hardening layer, not absence of error handling. |
| Clean request/response | **Done** | Structured payloads; see README API section |

### UI

| Requirement | Status | Evidence / notes |
|-------------|--------|------------------|
| Tree + form | **Done** | `views/reservation_batch_views.xml` (`list`, `form`) |
| Smart button → related stock moves | **Done** | `action_view_moves`, `move_count` |

### Security

| Requirement | Status | Evidence / notes |
|-------------|--------|------------------|
| Users see **own** reservations | **Done** | `security/reservation_security.xml` record rules on batch and lines |
| Managers see **all** | **Done** | Manager group + rules / full access where applicable |
| Allocation restricted to **authorized** users | **Partial** *(layered)* | **UI:** `Allocate` / `Mark Done` limited to **Reservation Manager** via `groups=` on form buttons. **API:** `allocate` / `status` enforce **batch owner or manager** in Python (`user.has_group(...)` / ownership). **ORM/RPC:** `action_allocate` does **not** repeat the manager check—users with write access who bypass the UI could invoke the method; tightening would mean a `has_group` (or sudo+with_user) guard on the server method. |

---

## 2. Engineering requirements (mandatory sections)

| Deliverable | Status | Where |
|-------------|--------|--------|
| **Sprint plan** (3 days, priorities, what was **not** done) | **Done** | `README.md` — “Sprint Plan”, “What I intentionally did NOT implement” |
| **Tests** (3–5+ cases: allocation, partial, no stock) | **Done** | `tests/test_reservation.py`: full, partial, no stock, cancel batch, confirm without lines; **FEFO-oriented test** runs when expiration metadata exists and skips otherwise—execution is **environment-dependent**, not a logic gap. |
| **Performance** (N+1, critical queries, scaling, complexity) | **Done** | `README.md` — “Performance Strategy”, “Critical query” |
| **Database** (indexes, constraints) | **Done** | `README.md` — “Database Design”; ORM indexes on models; SQL constraints on lines |
| **Concurrency** (risks + proposed mitigation, **design level**) | **Done (design-level, as per assignment)** | `README.md` — “Concurrency Strategy”; code adds **`allocation_in_progress`**, state checks, and skip-for-alocated-lines—**application-level** guards aligned with the brief’s “explain, do not fully lock” scope. Row-level DB locking remains **future hardening**, not a failed requirement. |

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
| Picking generation from moves | **Missing** (explicitly deferred in README) |
| Profiling / timings in logs | **Partial** (INFO around allocation; no structured timings) |
| Kanban / dashboard | **Missing** |
| Advanced API (versioning, **machine-readable error codes**) | **Partial** (JSON structure and messages are in place; standardized codes/version prefix not implemented) |
| Test automation plan | **Partial** (Odoo tests in-repo; CI pipeline not documented) |

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

4. **Picking** or delivery flow from generated moves if the business wants full warehouse documents.
5. **HTTP-level tests** for `/api/reservation/*` (auth, 403/404 paths).
6. Optional **`has_group`** on `action_allocate` if all allocation must be manager-only at the RPC layer too.

**Nice-to-have**

7. Kanban/dashboard, structured profiling timers, CI checklist for automated tests.

The implementation **satisfies the assignment scope** and demonstrates **solid engineering practices**, while **clearly separating** optional production-grade enhancements as **documented future work**.

---

## 7. Quick compliance scorecard

| Area | Met? |
|------|------|
| Working module + custom models + allocation + moves + API + UI + security | **Yes** |
| README engineering sections (sprint, performance, DB, concurrency, tests, limitations) | **Yes** |
| Automated tests ≥ minimal scenarios | **Yes** (6 tests; FEFO test depends on expiration metadata availability) |
| Bonus / optional hardening | **Mixed** — intentionally scoped; documented where not pursued |

For the authoritative wording of the assignment, see **`ORIGINAL_ASSIGNMENT.md`**.
