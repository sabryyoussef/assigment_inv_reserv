# Stock Reservation Engine - Test Report

## Test Command (Odoo 18)

```text
python odoo-bin -c <PATH_TO_CONFIG.conf> -d <DATABASE_NAME> -u stock_reservation_engine --test-enable --stop-after-init --http-port=<FREE_TCP_PORT>
```

Adjust the interpreter (`python`, `python3`, or `py -3.12`) and paths to match the host OS and installation layout.

## Requirements

- PostgreSQL reachable using the credentials and database name declared in the Odoo configuration file.
- Addons path (or `--addons-path`) includes the directory tree that exposes `stock_reservation_engine`, for example an `assigment`-style addons root already used by the project.

## Last Verified Run

**Date:** 2026-04-18

| Metric                         | Value |
| ------------------------------ | ----- |
| Failures                       | 0     |
| Errors                         | 0     |
| Executed post-install tests    | 24    |

Odoo discovers test methods independently of runtime outcome. Methods that resolve to `@tagged('post_install')` participation and are not skipped contribute to executed post-install counts. Additional discoverable entries (for example a skipped conditional test or framework-side accounting) may appear beside the aggregate the runner attaches to post-install execution; treat **24** as the authoritative executed count from the last verified run described here.

## Test Inventory

### tests/test_reservation.py (TransactionCase)

| Test method | Purpose |
| ----------- | ------- |
| `test_full_allocation` | Validates full allocation after confirmation when sufficient stock exists. |
| `test_partial_allocation` | Validates partial allocation when requested quantity exceeds available stock. |
| `test_no_stock` | Validates behaviour when no stock is available on the reservation location. |
| `test_fefo_preferred_lot` | Exercises preferred-lot preference when expiry-related fields exist; skips if the deployment lacks required lot-expiry fields. |
| `test_batch_state_all_cancelled` | Verifies terminal batch state when applicable lines are cancelled. |
| `test_confirm_without_lines_raises` | Ensures confirmation is rejected when the batch has no lines. |
| `test_allocate_denied_non_owner_non_manager` | Ensures a user who is neither owner nor reservation manager cannot allocate another user’s batch. |
| `test_owner_can_allocate_own_batch` | Ensures the reservation owner can allocate their own batch. |
| `test_manager_can_allocate_other_users_batch` | Ensures a reservation manager can allocate a batch owned by another user under record rules. |
| `test_allocate_raises_when_quant_rows_are_locked` | Uses a second database cursor to lock a `stock.quant` row and verifies the allocation fails with a predictable user-facing error instead of silently racing. |
| `test_second_allocate_does_not_duplicate_move` | Ensures a second allocation pass does not create duplicate moves when the batch remains partially fulfillable. |

### tests/test_reservation_http.py (HttpCase)

HTTP coverage uses JSON-RPC POST payloads (`jsonrpc`, `method`, `params`, `id`) against `type=json` routes `/api/reservation/create` and `/api/reservation/allocate`. Status checks use plain HTTP GET on `/api/reservation/status/<batch_id>` with `Authorization: Bearer <token>`.

The test class sets `readonly_enabled = False`. Odoo’s HTTP test harness can stack read-only transaction behaviour that blocks inserts required by allocation (`stock.move` and related rows). Disabling readonly mode on the case keeps HTTP requests aligned with production semantics for database writes during tests.

| Test method | Purpose |
| ----------- | ------- |
| `test_api_aaa_flow_jsonrpc_create_then_allocate` | Creates a reservation via JSON-RPC, confirms it through the ORM, then allocates via JSON-RPC end-to-end. |
| `test_api_create_unauthorized` | Create route rejects requests without a Bearer token in the JSON-RPC result payload. |
| `test_api_create_inactive_token_unauthorized` | Create route rejects inactive tokens. |
| `test_api_create_validation_empty_lines` | Create route validates non-empty `lines`. |
| `test_api_create_validation_bad_line` | Create route rejects lines missing mandatory keys (`product_id`, etc.). |
| `test_api_create_validation_line_must_be_object` | Create route rejects malformed non-object line entries with a clearer validation message. |
| `test_api_create_accepts_lowercase_bearer` | Confirms bearer authentication is handled robustly even when the authorization scheme uses lowercase spelling. |
| `test_api_allocate_unauthorized` | Allocate route rejects unauthenticated JSON-RPC calls. |
| `test_api_allocate_validation_missing_batch_id` | Allocate route validates presence of `batch_id`. |
| `test_api_allocate_not_found` | Allocate route maps unknown batch identifiers to the documented error contract. |
| `test_api_allocate_forbidden_non_owner` | Allocate route denies non-owner callers who are not reservation managers. |
| `test_api_zzz_allocate_success_admin_owner` | Successful allocation response for an owner/admin scenario using JSON-RPC. |
| `test_api_status_unauthorized` | GET `/status` returns `401` without Bearer authentication. |
| `test_api_status_not_found` | GET `/status` returns `404` for non-existent batches. |
| `test_api_status_forbidden_non_owner` | GET `/status` returns `403` when the caller is neither owner nor manager. |
| `test_api_status_success` | GET `/status` returns `200` with expected JSON shape for an authorized owner. |

## Environment / Implementation Notes

1. **Tests package import order** — `tests/__init__.py` imports `test_reservation_http` before `test_reservation`. Registration order influences execution scheduling between `HttpCase` and `TransactionCase`; ordering HTTP coverage first avoids brittle interactions between HTTP workers and the main test cursor lifecycle.

2. **Token authentication and environment** — Routes use `auth='none'` and resolve identity from API tokens. The resolved user must be loaded so stored foreign keys are visible (`read` on `user_id` plus `browse` under elevated access where needed). Batch creation uses `request.env(user=<token_user_id>, su=True)` so `mail.thread` creates messages under an environment whose `env.user` is a single record, satisfying `mail.message` expectations. Calling `sudo()` alone leaves `uid` tied to the public session while toggling superuser flags only; it does not substitute the token user’s identity for mail and related subsystems.

3. **Company handling under `auth='none'`** — Explicit `company_id` on batch creation derives from the authenticated user’s company, with a deterministic fallback when needed. Defaults that rely on `env.company` do not apply reliably on the public environment used for unsigned HTTP entrypoints.

4. **Reservation Dashboard** — Graph and pivot views on `stock.reservation.line` (`views/reservation_dashboard_views.xml`) have **no** automated test in this package. Validate manually: **Inventory → Stock Reservations → Dashboard**; switch graph ↔ pivot; confirm measures and filters behave as expected after creating or allocating batches (see README **How to verify**).

## Related Files

- `controllers/api.py` — REST-style JSON routes for create, allocate, and status.
- `security/reservation_security.xml` — Groups and record rules exercised by allocation and HTTP tests.
- `views/reservation_dashboard_views.xml` — Dashboard graph/pivot (manual QA only).
- `tests/__init__.py` — Controls import order for test modules.
- `tests/test_reservation.py` — Transaction-level reservation and allocation scenarios.
- `tests/test_reservation_http.py` — HTTP and JSON-RPC coverage.
