# Assignment Completion Plan

Date: 2026-04-18
Project: stock_reservation_engine

## Goal
Close the remaining gaps between the delivered module and the original assignment, with priority on items that improve reviewer confidence and submission quality.

---

## Current status summary

### Already completed
- Custom reservation batch and line models
- Allocation engine using stock.quant with FEFO or FIFO behavior
- Partial allocation handling
- Stock move generation and picking linkage
- API endpoints with bearer-token authentication
- Security rules for user-owned vs manager-wide access
- UI authorization aligned for reservation allocation
- Concurrency protection strengthened with row-level NOWAIT locking
- API validation and response handling hardened
- README, requirement mapping, and test report documentation
- Automated ORM and HTTP tests

### Remaining gaps
- Dashboard is still primarily manually verified
- Final performance and database evidence should be reviewed one more time for submission polish
- Final README and reviewer checklist polish is still pending

### Additional assignment-verification items
Even where the feature already exists, the final delivery should explicitly prove:
- The 3-day sprint story is easy to find and clearly prioritized
- The performance section explicitly covers N+1 avoidance, critical queries, and scaling reasoning
- The database section clearly maps indexes and constraints to the implemented models
- The code and docs look clean, readable, and reviewer-friendly

---

## Priority plan

## Phase 1 — Finish the visible assignment gap
Priority: High
Estimated effort: 30–60 minutes
Status: Completed on the current branch

### Task 1: Align UI with backend authorization
Problem:
- Backend allows allocation by batch owner or reservation manager
- Form button currently appears manager-only

Target file:
- assigment/stock_reservation_engine/views/reservation_batch_views.xml

Action:
- Make the Allocate button available to reservation users as well, while keeping server-side authorization as the final guard

Acceptance criteria:
- Batch owner can see and use Allocate from the UI
- Unauthorized users still cannot allocate another user’s batch
- Existing authorization tests continue to pass

---

## Phase 2 — Strengthen concurrency handling
Priority: Medium to High
Estimated effort: 2–4 hours
Status: Completed on the current branch with lock-aware handling and regression coverage

### Task 2: Add safer allocation under contention
Problem:
- Two users could still allocate overlapping stock in separate transactions

Target file:
- assigment/stock_reservation_engine/models/reservation_batch.py

Action:
- Add row-level locking or transactional protection around the candidate stock.quant records during allocation
- Return a clear user-facing error or retry flow when stock is being allocated concurrently

Suggested approach:
1. Identify candidate quants first
2. Lock them using SQL row locking
3. Recompute availability after lock acquisition
4. Proceed with allocation only from the locked rows

Acceptance criteria:
- Competing allocation attempts do not silently over-allocate the same stock
- Failure mode is predictable and documented
- README concurrency section is updated to reflect the stronger implementation

---

## Phase 3 — Improve API robustness
Priority: Medium
Estimated effort: 1–2 hours
Status: Completed on the current branch with stronger validation and response consistency

### Task 3: Harden the HTTP API
Target file:
- assigment/stock_reservation_engine/controllers/api.py

Actions:
- Keep response shapes fully consistent across all endpoints
- Narrow elevated access where possible
- Add better validation messages for malformed payloads
- Optionally add lightweight request logging or throttling notes

Acceptance criteria:
- Error bodies are consistent for create, allocate, and status
- No unnecessary sudo usage remains in business actions
- HTTP tests still pass

---

## Phase 4 — Verify performance and database requirements
Priority: Medium
Estimated effort: 45–90 minutes

### Task 4: Make the engineering evidence explicit
Target files:
- assigment/stock_reservation_engine/README.md
- assigment/stock_reservation_engine/models/reservation_batch.py
- assigment/stock_reservation_engine/models/reservation_line.py

Actions:
- Cross-check the README wording against the assignment’s mandatory performance section
- Make sure sample timing or logging evidence is easy for the reviewer to find
- Verify that documented indexes and constraints are actually present in the models, or clearly marked as design recommendations
- Add a short explanation of query behavior and scaling so the performance story is explicit

Acceptance criteria:
- Reviewer can immediately see the N+1, critical query, and scaling discussion
- Database design claims match the real code
- No ambiguity remains around the mandatory engineering requirements

---

## Phase 5 — Close documentation and QA polish
Priority: Medium
Estimated effort: 45–90 minutes

### Task 5: Add a final reviewer-facing validation pass
Target files:
- assigment/stock_reservation_engine/README.md
- assigment/stock_reservation_engine/docs/TEST_REPORT.md
- assigment/stock_reservation_engine/docs/REQUIREMENTS_VS_IMPLEMENTATION.md

Actions:
- Update docs to match the exact final behavior after the UI and concurrency improvements
- Add a short final verification checklist for a reviewer
- Confirm the README contains the exact assignment-friendly sections: architecture, sprint plan, performance, database, concurrency, testing, and known limitations
- Make sure intentionally omitted items are clearly explained as trade-offs, not accidental misses

Acceptance criteria:
- Documentation matches the code exactly
- Reviewer can understand what is delivered, what is optional, and what was intentionally scoped
- The README is submission-ready even if the reviewer only reads documentation once

---

## Optional nice-to-have items
Priority: Low
Estimated effort: variable

These are not required to satisfy the assignment, but can improve polish:
- Auto-run picking assignment when appropriate
- Cancel linked pickings when a batch is cancelled
- Add one more manual or automated dashboard check
- Add CI instructions for running tests automatically
- Add API version prefixing for long-term maintainability

---

## Recommended execution order
1. Verify the performance and database evidence against the assignment wording
2. Update docs to reflect the final delivered behavior
3. Do one final submission review against the original assignment

---

## Submission readiness definition
The assignment should be considered fully ready when:
- All mandatory requirements from the original brief are covered
- The UI and backend behavior are aligned
- Tests pass without regressions
- Documentation clearly explains design choices, trade-offs, and limitations

---

## Practical recommendation
If time is limited, complete Phase 1, Phase 4, and Phase 5 first. Those give the highest value for assignment review quality with the lowest effort.
