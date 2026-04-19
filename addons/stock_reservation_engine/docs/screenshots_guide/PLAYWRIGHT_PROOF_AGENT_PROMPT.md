# Playwright Proof Capture Prompt

Use the following prompt with a local AI agent that can run Playwright and access the live demo environment.

---

## Prompt

You are validating the Stock Reservation Engine demo environment and must collect **reviewer-proof evidence** with Playwright.

### Target system
- URL: https://sabryyoussef-assigment-inv-reserv.odoo.com/odoo

### Test users
- Assignment Admin
  - login: admin@stock-reservation-demo.local
  - password: 123
- Assignment User
  - login: reviewer@stock-reservation-demo.local
  - password: 123

### Mission
Use Playwright to log in and collect clear evidence that the module is working as documented.

### Required proof to capture
1. Login page and successful login
2. Inventory configuration screen
3. Stock Reservations dashboard
4. Reservation Batches list
5. One reservation batch opened after allocation
6. Stock Moves smart button result
7. Transfers smart button result
8. API Tokens page as manager/admin user
9. User-level visibility proof showing that the normal reviewer user can access only allowed reservation views

### Output expectations
- Save screenshots with clear names and timestamps
- Record the exact pages visited
- Record any visible batch names, states, allocated quantities, moves, or transfer counts
- Note any errors, warnings, or broken flows
- Provide a short final summary of what was verified successfully

### Performance and concurrency proof support
If possible, also use Playwright request handling or browser-side fetch calls to create a lightweight proof set for:
- repeated API status checks
- multiple rapid allocate or status requests
- evidence that the application responds consistently under repeated calls

If true 50-user load simulation is not practical inside Playwright alone, note that dedicated tools such as k6 or Locust are more appropriate for full concurrency load testing, and still capture Playwright-based proof of endpoint behavior and UI stability.

### Final deliverables
Return:
- the saved screenshot list
- a summary of validated UI flows
- any evidence of allocation timing, status stability, or concurrency-related behavior
- a short pass/fail checklist for reviewer use
