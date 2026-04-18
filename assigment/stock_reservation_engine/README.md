# Stock Reservation Engine

## Overview
This module adds a custom reservation and allocation layer on top of Odoo Inventory. It allows a user or an external system to create a reservation batch, allocate stock proactively from `stock.quant`, apply FEFO when lot expiration data exists, fall back to FIFO otherwise, and generate `stock.move` records that reflect the allocated quantity.

The objective is to support high-volume scenarios where competing demands may request the same stock before normal fulfillment flows are executed.

## Scope Delivered
- Custom models:
  - `stock.reservation.batch`
  - `stock.reservation.line`
  - `reservation.api.token`
- Allocation engine based on `stock.quant`
- FEFO / FIFO ordering
- Partial allocation support
- Generated `stock.move` per line when allocated quantity is greater than zero
- JSON API with token-based authentication
- Security groups and record rules
- Tree and form views with stock move smart button
- Odoo tests covering key scenarios

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

## Functional Flow
1. User creates a reservation batch.
2. User adds one or more lines.
3. User confirms the batch.
4. User or API calls Allocate.
5. The engine searches `stock.quant` by product, location, and child locations.
6. It orders quants using FEFO or FIFO.
7. It calculates allocated quantity and updates line state.
8. If allocated quantity is greater than zero, it creates a stock move.
9. Batch state is derived from line states.
10. External systems can query the status endpoint.

## Sprint Plan
### Day 1
- Designed data model and states
- Implemented security groups, record rules, and access rights
- Built basic menu, tree view, and form view
- Added batch sequence

### Day 2
- Implemented allocation engine
- Added FEFO / FIFO ordering
- Added partial allocation support
- Added stock move generation and smart button

### Day 3
- Implemented JSON APIs and token authentication
- Added tests for full allocation, partial allocation, no stock, and FEFO
- Wrote README covering architecture, performance, database design, and concurrency
- Added lightweight application-level protection against double processing

### What I intentionally did NOT implement and why
- Full row-level locking on `stock.quant` was not fully implemented to keep the sprint focused on correctness and clarity of the core allocation flow.
- Picking generation was intentionally deferred because the assignment requires move generation, not full warehouse workflow orchestration.
- A dedicated quant allocation trace table was deferred to avoid over-engineering within the sprint scope.

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

## Security Model
- Reservation users can access only their own batches and lines.
- Reservation managers can access all records.
- Allocation from the UI is restricted to the manager group.
- API access is token-based and resolves to an Odoo user.

## Performance Strategy
### Avoiding N+1 queries
Each reservation line uses a single ordered `stock.quant` query. The implementation avoids nested per-quant reads and delegates sorting to the database.

### Critical query
The most important query is the `stock.quant` lookup filtered by:
- `product_id`
- `location_id` with `child_of`
- `company_id`
- `quantity > 0`
- optional `lot_id`

### Scaling approach
The current implementation is intentionally simple and clear. A future optimization would group lines by product and location to reuse quant result sets and reduce repeated searches when many lines target the same product.

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
Concurrency was analyzed at design level, as required by the assignment.

### Current implementation
The module includes lightweight application-level protection using:
- state guards
- `allocation_in_progress` flag
- duplicate move prevention
- skipping already allocated lines

This reduces accidental double processing from repeated clicks or repeated API calls.

### Risk
Two concurrent transactions may still read the same available quantity before commit, which can lead to over-allocation in high-contention scenarios.

### Production-grade mitigation
For production-grade concurrency safety, the next step would be:
1. Lock candidate `stock.quant` rows with `SELECT ... FOR UPDATE`
2. Execute allocation inside a single transaction
3. Optionally add retry logic for lock contention or serialization failures

## Testing
Implemented Odoo test cases using `TransactionCase`.

Covered scenarios:
1. Full allocation when enough stock exists
2. Partial allocation when available stock is lower than requested quantity
3. No-stock scenario
4. FEFO selection when lots have expiration dates

## Known Limitations
- Full database-level locking is not implemented. The `allocation_in_progress` flag is an application-level guard only. In a multi-worker environment two concurrent transactions can still read the same available quantity before either commits, potentially causing over-allocation. The production-grade solution is to lock candidate `stock.quant` rows with `SELECT ... FOR UPDATE` before the allocation loop.
- No picking generation. The module generates `stock.move` records but does not create full `stock.picking` objects.
- No quant allocation trace table. The chosen lot is stored on the line for traceability, but per-quant breakdown is not persisted.
- FEFO stores the first chosen lot on the line. It does not persist a quant-by-quant breakdown.
- No UoM conversion on reservation lines. The `uom_id` is taken from `product_id.uom_id` only. Lines with a different requested unit of measure are not supported.
- API tokens are hashed with SHA-256 on save. Existing tokens created before this version stored their value in plaintext and must be deleted and re-created. Raw token values are never retrievable after saving.
- The API has no rate limiting. This is acceptable for the current sprint scope. A production deployment should add throttling at the reverse-proxy or middleware level.
- The `sudo()` scope in the API controller is intentionally broad for the sprint. Each write operation is guarded by a manual ownership or group check. A production hardening step would narrow `sudo()` to only the lookup operations and switch to `with_user(user)` for writes.

## Installation
1. Copy the module folder into your custom addons path.
2. Update the app list.
3. Install **Stock Reservation Engine**.
4. Grant users either:
   - `Stock Reservation User`
   - `Stock Reservation Manager`
5. Create API tokens from **Inventory > Stock Reservations > API Tokens** if external access is needed.

## Manual Test Scenarios
### Scenario 1: Full allocation
- Create on-hand stock for a product
- Create a reservation batch with requested quantity lower than available quantity
- Confirm and allocate
- Expected result: line state `allocated`, move created

### Scenario 2: Partial allocation
- Create on-hand stock lower than requested quantity
- Confirm and allocate
- Expected result: line state `partial`, allocated quantity lower than requested quantity

### Scenario 3: No stock
- Create reservation without any available stock
- Confirm and allocate
- Expected result: line state `not_available`, no move created

### Scenario 4: FEFO behavior
- Create two lots with different expiration dates
- Add stock to both lots
- Allocate one line
- Expected result: the line prefers the earliest expiration lot

## Future Improvements
- Full concurrency-safe allocation with SQL row locking (`SELECT FOR UPDATE` on `stock.quant`)
- Quant allocation trace model for full per-quant breakdown
- Picking generation from allocated moves
- Batch priority scheduling across multiple pending reservations
- API versioning and structured error codes
- API token expiry dates and scope restrictions
- Rate limiting at API layer
