# Assignment Completion Plan

> Historical planning note: for the current documentation flow, start with [README.md](README.md).

Date: 2026-04-18
Project: stock_reservation_engine

## Goal
Deliver and document a production-minded Odoo reservation module that matches the assignment brief across functional scope, engineering quality, and reviewer-facing evidence.

---

## Current status summary

### Mandatory functional scope completed
- Working module with custom reservation batch and line models
- Allocation from stock.quant using FEFO when expiry exists, otherwise FIFO
- Respect for selected location plus child locations
- Partial allocation support with allocated quantity and line-state updates
- Stock move generation and linkage back to reservation lines
- JSON API for create, allocate, and status with bearer-token authentication
- Tree and form views with smart-button navigation for related inventory records
- Security rules for own-record access vs manager-wide access

### Mandatory engineering scope completed
- README includes architecture decisions plus a realistic Day 1 / Day 2 / Day 3 sprint simulation
- Testing covers allocation logic, partial allocation, no-stock behavior, authorization, and HTTP API flows
- Performance documentation explains N+1 avoidance, critical queries, query behavior, and scaling reasoning
- Database documentation calls out indexes, constraints, and why they matter
- Concurrency risks and mitigation are documented, with row-level NOWAIT locking added as extra hardening
- Known limitations and trade-offs are clearly stated for reviewer confidence

### Bonus items delivered
- Concurrency-safe allocation hardening
- Picking generation from allocated moves
- Profiling and timing logs during allocation
- Dashboard reporting for reservation visibility
- Advanced API polish with versioned aliases
- Test automation support through CI workflow documentation

### Remaining gaps
- No mandatory assignment gaps remain on the current branch
- Dashboard rendering still benefits from one final manual reviewer sanity check
- Any further work would be optional production polish beyond the assignment brief

---

## Priority plan

## Phase 1 — Finish the visible assignment gap
Priority: High
Estimated effort: 30–60 minutes
Status: Completed on the current branch

### Task 1: Align UI with backend authorization
Task status: Completed on the current branch

Problem:
- Backend allows allocation by batch owner or reservation manager
- Form button currently appears manager-only

Target file:
- addons/stock_reservation_engine/views/reservation_batch_views.xml

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
Task status: Completed on the current branch

Problem:
- Two users could still allocate overlapping stock in separate transactions

Target file:
- addons/stock_reservation_engine/models/reservation_batch.py

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
Task status: Completed on the current branch

Target file:
- addons/stock_reservation_engine/controllers/api.py

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
Status: Completed on the current branch with clearer README evidence for N+1, critical queries, scaling, indexes, and constraints

### Task 4: Make the engineering evidence explicit
Task status: Completed on the current branch

Target files:
- addons/stock_reservation_engine/README.md
- addons/stock_reservation_engine/models/reservation_batch.py
- addons/stock_reservation_engine/models/reservation_line.py

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
Status: Completed on the current branch with final reviewer-facing checklist and submission polish

### Task 5: Add a final reviewer-facing validation pass
Task status: Completed on the current branch

Target files:
- addons/stock_reservation_engine/README.md
- addons/stock_reservation_engine/docs/TEST_REPORT.md
- addons/stock_reservation_engine/docs/REQUIREMENTS_VS_IMPLEMENTATION.md

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

## Bonus items delivered
Priority: Optional but highly valued
Status: Completed on the current branch

These items now align directly with the assignment bonus section:
- Concurrency-safe allocation implementation with lock-aware handling
- Picking generation from allocated moves
- Profiling output and timing logs during allocation
- Dashboard reporting view for reviewer visibility
- Advanced API structure with versioned aliases for long-term maintainability
- Testing automation plan via CI workflow support

---

## Recommended execution order
1. Optionally do one last manual dashboard sanity check
2. Package or submit the branch for review
3. Only continue with extra polish if specifically requested

---

## Submission readiness definition
The assignment should be considered fully ready when:
- All mandatory requirements from the original brief are covered
- The UI and backend behavior are aligned
- Tests pass without regressions
- Documentation clearly explains design choices, trade-offs, and limitations

---

## Practical recommendation
The mandatory assignment scope is complete and submission-ready. From this point, focus only on optional dashboard/manual polish or final packaging for handoff.
