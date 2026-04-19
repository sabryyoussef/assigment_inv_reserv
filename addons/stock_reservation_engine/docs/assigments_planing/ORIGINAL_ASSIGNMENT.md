# Original Assignment — Stock Reservation & Allocation Engine

> Historical reference: for the curated documentation entry point, start with [README.md](README.md).

This document preserves the **original assignment brief** as provided for the `stock_reservation_engine` module. It is **not** the implementation README; see the root `README.md` for architecture, sprint notes, and delivery details.

---

## Objective

Build a custom Odoo module that extends inventory behavior by introducing a **reservation and allocation engine** with **API exposure**, **performance awareness**, and **production-grade engineering practices**.

### Business context

Introduce a **controlled and intelligent** way to **reserve and allocate inventory before actual fulfillment**, especially where **volume is high** and **demand competes** (multiple orders, channels, or users targeting the same stock). Standard Odoo is often **reactive** (driven by stock moves); this system enables **proactive reservation** so critical requests are secured early, stock is allocated using rules such as **FEFO/FIFO**, and **shortages/conflicts** are handled predictably. **APIs** allow integration with external systems (marketplaces, POS, procurement, etc.). **Performance** and **database** choices aim to keep the system reliable at scale for **high-volume** operations.

---

## Scope overview

You are expected to:

1. Build a **working module**
2. Demonstrate **engineering quality** (not only functionality)
3. Show how you deliver in a **structured sprint**
4. **Validate performance** and **database** decisions

---

## Functional requirements

### 1. Custom models

**`stock.reservation.batch`**

- `name` (auto sequence)
- `request_user_id`
- `line_ids` (One2many → `stock.reservation.line`)
- `state` (draft, confirmed, allocated, done, cancelled)
- `priority`
- `scheduled_date`

**`stock.reservation.line`**

- `batch_id`
- `product_id`
- `requested_qty`
- `allocated_qty`
- `location_id`
- `lot_id` (optional)
- `state`
- `move_id` (link to generated `stock.move`)

### 2. Allocation engine (core logic)

When the user clicks **Allocate**:

- Reserve stock from **`stock.quant`**
- Apply:
  - **FEFO** if lots with expiry exist
  - Otherwise **FIFO**
- Respect:
  - Selected **location + child locations**
- Allow:
  - **Partial** allocation
- Update:
  - `allocated_qty`
  - Line **state** accordingly

### 3. Stock integration

- Generate **`stock.move`** records after allocation
- Link moves to reservation lines
- Moves reflect **allocated** quantities

### 4. API layer

Expose **JSON** endpoints:

| Method | Path |
|--------|------|
| POST | `/api/reservation/create` |
| POST | `/api/reservation/allocate` |
| GET | `/api/reservation/status/<id>` |

Requirements:

- **Token-based** authentication
- **Proper error handling** (clear JSON responses)
- **Clean** request/response structure

### 5. UI

- **Tree + Form** views
- **Smart button**: view related stock moves

### 6. Security

- Users: **only their own** reservations
- Managers: **all** reservations
- Allocation restricted to **authorized** users

---

## Engineering requirements (critical)

### 1. Sprint delivery simulation (mandatory)

Structure work as a **3-day sprint**. In **README**:

- Sprint breakdown (**Day 1 / Day 2 / Day 3**)
- Tasks prioritized
- What was **intentionally not** implemented and **why**

Evaluation: prioritization, realism, delivery thinking.

### 2. Testing (mandatory)

Include **at least 3–5** test cases covering:

- Allocation logic
- Partial allocation
- No-stock scenario

May be **Odoo unit tests** OR clearly documented **manual** test scenarios.

Evaluation: correctness thinking, edge-case awareness.

### 3. Performance validation (mandatory)

No requirement to simulate 100k rows, but you must **explain and demonstrate**:

- How allocation avoids **N+1** queries
- Which queries are **critical**
- How logic **scales**

Provide **sample logging** or explanation of query behavior and **time complexity** reasoning.

Evaluation: performance thinking, not raw benchmarking only.

### 4. Database design & tuning (mandatory)

Explicitly define:

- **Indexes** you would add (e.g. `product_id`, `location_id`, …)
- **Why** they matter
- **Constraints** (ORM or SQL)

Evaluation: DB awareness beyond the ORM.

### 5. Concurrency awareness (design level)

**No** full locking implementation required, but explain:

- What if **two users** allocate the **same** stock?
- **Risks** (over-allocation, races)
- **Proposed mitigation**: SQL locking? Retries? Transactional safeguards?

---

## Deliverables

### 1. Code

- Complete Odoo module
- Clean structure
- Readable, maintainable code

### 2. README (very important)

Must include:

| Section | Content |
|---------|---------|
| **A. Architecture decisions** | How allocation works; why designed this way |
| **B. Sprint plan** | Day-by-day; trade-offs |
| **C. Performance strategy** | Queries, bottlenecks, scaling |
| **D. Database design** | Indexes, constraints |
| **E. Concurrency strategy** | Risks and mitigation |
| **F. Testing** | Test cases or approach |
| **G. Known limitations** | What is missing or simplified |

### Bonus (optional, valued)

- Concurrency-safe allocation
- Picking generation from moves
- Profiling output (logs, timings)
- Kanban or dashboard
- Advanced API structure
- Test automation plan

---

## Timeline

Complete the assignment within **5 days max**.

---

## Source / contact (as provided)

**Yahya Najjar**

- +962 799 701 476  
- www.aumet.com  

*Best regards*