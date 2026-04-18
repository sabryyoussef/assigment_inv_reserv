# Stock Reservation Engine – Presentation Script (English)

## Purpose of this demo
This script guides you step by step from opening Odoo on Odoo.sh all the way to demonstrating the assignment requirements in the UI.

Goal of the story:
- show proactive inventory reservation before fulfillment
- show FEFO/FIFO allocation behavior
- show partial allocation and no-stock handling
- show stock move and transfer generation
- show security and API exposure
- close with engineering quality points

---

## Demo actors
Create two users for the presentation:

1. Reservation User
   - example name: Demo Reservation User
   - should belong to:
     - Internal User
     - Inventory / User
     - Stock Reservation User

2. Reservation Manager
   - example name: Demo Reservation Manager
   - should belong to:
     - Internal User
     - Inventory / Administrator
     - Stock Reservation Manager

Use one storable tracked product with variants.

Suggested example product:
- Product template: Antibiotic Kit
- Variants: 250mg and 500mg
- Tracking: By Lots
- Expiration Dates: Enabled

---

## Opening statement you can say
Today I will demonstrate a custom Odoo inventory reservation and allocation engine. The business value is that stock can be reserved before actual fulfillment, which helps avoid conflicts when several users or channels compete for the same inventory.

---

## Part 1 – Open Odoo on Odoo.sh

### What to do
1. Open your Odoo.sh project.
2. Open the desired branch environment.
3. Click Open Odoo.
4. Log in as the administrator.

### What to say
I am starting from the Odoo.sh environment to show that the solution is deployed in a realistic hosted setup.

---

## Part 2 – Install the custom module

### Menu path
Apps → Search for Stock Reservation Engine → Install

### What to do
1. Open the Apps screen.
2. Search for Stock Reservation Engine.
3. Click Install.

### What to say
This module extends Inventory by adding a reservation batch workflow, allocation logic, API access, dashboard analysis, and role-based security.

### Requirement covered
- Build a working module
- UI integration inside Inventory

---

## Part 3 – Create users and permissions

### Menu path
Settings → Users & Companies → Users

### What to do
1. Create Demo Reservation User.
2. Give this user the Stock Reservation User group.
3. Create Demo Reservation Manager.
4. Give this user the Stock Reservation Manager group.

### What to say
This step covers the security requirement. Regular users can only access their own reservations, while managers can see all reservations and manage API tokens.

### Requirement covered
- Security
- Access restriction by role

---

## Part 4 – Inventory settings required for the demo

### Menu path
Inventory → Configuration → Settings

### Enable these options
- Storage Locations
- Lots & Serial Numbers
- Expiration Dates
- Multi-Step Routes if you want a more realistic internal transfer flow

### What to say
These settings are important because the allocation engine can work with warehouse locations, child locations, and lots with expiry dates. When expiry exists, the logic behaves as FEFO; otherwise it falls back to FIFO.

### Requirement covered
- FEFO when lots with expiry exist
- FIFO otherwise
- Respect selected location and child locations

---

## Part 5 – Create the product template and variants

### Menu path
Inventory → Products → Products

### What to do
1. Create a new product named Antibiotic Kit.
2. Product Type: Storable Product.
3. Turn on Tracking by Lots.
4. Add an attribute such as Strength with values 250mg and 500mg.
5. Save the product.

### Then show the generated variants
Menu path:
Inventory → Products → Product Variants

### What to say
I am creating a product with variants because the reservation line works on the real product variant record, not just the template. This also reflects real inventory operations.

### Requirement covered
- Reservation lines linked to product variants through product_id

---

## Part 6 – Add stock and lot expiry data

### Recommended screen path
Inventory → Products → Product Variants → open a variant → On Hand / Update Quantity

### What to do
For the 250mg variant:
1. Add quantity in WH/Stock.
2. Use two lots, for example:
   - LOT-250-A with an earlier expiration date
   - LOT-250-B with a later expiration date
3. Make sure both lots have on-hand stock.

Optional review screen:
Inventory → Products → Lots/Serial Numbers

### What to say
This is the key setup for demonstrating FEFO. Because the product is tracked by lots and expiry dates are present, the allocation engine should pick the earliest expiring lot first.

---

## Part 7 – Show the custom Inventory menus

### Main custom menu path
Inventory → Stock Reservations

### Show these screens one by one
1. Dashboard
2. Reservation Batches
3. API Tokens

### What to say
The custom module is integrated directly under Inventory. I will now walk through each screen.

---

## Part 8 – Dashboard screen

### Menu path
Inventory → Stock Reservations → Dashboard

### What appears on the screen
- Graph view
- Pivot view
- Search filters:
  - Allocated
  - Partial
  - Not Available
- Group by options:
  - Product
  - State

### What to say
This dashboard gives operational visibility into reservation outcomes. It helps users analyze demand, shortages, and successful allocations.

### Requirement covered
- UI enhancement
- Reporting visibility as a bonus item

---

## Part 9 – Reservation Batches list screen

### Menu path
Inventory → Stock Reservations → Reservation Batches

### What appears on the list
- Name
- Request User
- State
- Priority
- Scheduled Date
- Stock Moves count
- Transfers count

### What to say
This is the main working screen for the assignment. Each reservation request is grouped inside a batch, and each batch contains one or more reservation lines.

### Requirement covered
- Custom model: stock.reservation.batch
- Tree view

---

## Part 10 – Use Case 1: Full allocation with FEFO

### Screen path
Inventory → Stock Reservations → Reservation Batches → Create

### What to do in the form
1. Open a new Reservation Batch form.
2. Confirm the Request User is correct.
3. Set Priority to Urgent or High.
4. Set Scheduled Date.
5. In the Lines tab, add one line:
   - Product: Antibiotic Kit, 250mg variant
   - Requested Qty: 6
   - Location: WH/Stock
6. Save.
7. Click Confirm.
8. Click Allocate.

### What you should show after allocation
- line Allocated Qty is updated
- line State becomes Allocated if enough stock exists
- selected lot is automatically set if applicable
- batch state becomes Allocated
- Stock Moves smart button appears
- Transfers smart button appears

### What to say
Here I am demonstrating the main business flow. The user creates a reservation before fulfillment. When I click Allocate, the system checks stock.quant, applies FEFO because lot expiry exists, and creates inventory moves for the allocated quantity.

### Requirement covered
- Allocation engine
- FEFO logic
- allocated_qty update
- state update
- stock.move generation
- smart buttons for related records

---

## Part 11 – Show the generated stock move and transfer

### Screen path from the batch form
Click Stock Moves smart button

### Then
Click Transfers smart button

### What to say
The requirement asked for generated stock moves after allocation and a link back to the reservation line. The UI proves that the move and internal transfer records were created successfully.

### Requirement covered
- Stock integration
- View related moves through UI

---

## Part 12 – Use Case 2: Partial allocation

### Screen path
Inventory → Stock Reservations → Reservation Batches → Create

### What to do
1. Create another batch for the same variant.
2. Request a quantity larger than the remaining available stock, for example 20.
3. Save, Confirm, then Allocate.

### What to show
- Allocated Qty is less than Requested Qty
- Line State becomes Partial
- Batch State becomes Partial

### What to say
This demonstrates that the solution allows partial allocation instead of failing completely. This is useful in high-demand environments where some stock can still be secured.

### Requirement covered
- Partial allocation
- predictable shortage handling

---

## Part 13 – Use Case 3: No stock scenario

### Preparation
Create another product variant with zero available stock.

### Screen path
Inventory → Stock Reservations → Reservation Batches → Create

### What to do
1. Add a line for a product that has no on-hand quantity.
2. Save, Confirm, then Allocate.

### What to show
- Allocated Qty stays 0
- Line State becomes Not Available
- No move is created
- Batch ends in Partial state because demand was not satisfied

### What to say
This covers the no-stock scenario required by the assignment and shows clear behavior instead of hidden failures.

### Requirement covered
- No stock scenario
- clear state management

---

## Part 14 – Show security behavior

### What to do
1. Log in as Demo Reservation User.
2. Open Inventory → Stock Reservations → Reservation Batches.
3. Show that this user only sees their own records.
4. Log in as Demo Reservation Manager.
5. Show that the manager can see all reservation batches and API tokens.

### What to say
The record rules enforce data isolation for normal users, while managers have broader access for supervision and support.

### Requirement covered
- Users can only access their own reservations
- Managers can access all
- Allocation restricted by authorization

---

## Part 15 – API Tokens screen

### Menu path
Inventory → Stock Reservations → API Tokens

### Important note
This menu is visible to managers.

### What to do
1. Create a token for one user.
2. Save the token.

### What to say
The module includes token-based authentication for external systems such as marketplaces, POS, or procurement tools.

### Requirement covered
- Token-based API authentication

---

## Part 16 – API use case demo

### Endpoints to mention
- POST /api/reservation/create
- POST /api/reservation/allocate
- GET /api/reservation/status/<id>

### What to say while showing Postman or curl
First, an external system sends a create request with product, quantity, and location. Then it triggers allocation. Finally, it checks status and receives the reservation state, allocated quantity, and linked move information in JSON.

### Suggested talking points
- clean request and response structure
- error handling for unauthorized, validation, forbidden, not found, and internal errors
- practical integration readiness

### Requirement covered
- API layer
- proper error handling
- clean JSON structure

---

## Part 17 – Map the UI demo back to the assignment text

### 1. Custom Models
Shown in Reservation Batches and Lines inside the form view.

### 2. Allocation Engine
Shown by the Allocate button using FEFO/FIFO and updating allocated quantities and states.

### 3. Stock Integration
Shown by the Stock Moves and Transfers smart buttons.

### 4. API Layer
Shown by the API Tokens screen and the three reservation endpoints.

### 5. UI
Shown through list view, form view, smart buttons, dashboard graph, and pivot analysis.

### 6. Security
Shown by separate user and manager access levels.

---

## Part 18 – Engineering quality close-out

At the end of the UI demo, briefly say:

This submission is not only functional. It also includes engineering thinking: a sprint-based delivery plan, automated tests for full, partial, and no-stock allocation, performance awareness around critical queries, database constraints and indexes, and concurrency risk handling.

### Key points to mention
- 3-day sprint breakdown is documented
- tests cover allocation logic and API behavior
- indexes and SQL constraints are defined on important fields
- concurrency risk is acknowledged and handled with lock-aware allocation logic
- logging and timing are included for performance visibility

### Requirement covered
- Sprint Delivery Simulation
- Testing
- Performance Validation
- Database Design & Tuning
- Concurrency Awareness

---

## Short closing statement
To conclude, this module provides a proactive inventory reservation workflow inside Odoo. It supports operational users through the UI, external systems through secure APIs, and business reliability through engineering practices and controlled allocation behavior.

---

## Quick 10-minute presenter version
If you need a shorter version during the interview, follow this order:

1. Open Odoo.sh and log in
2. Install the module
3. Show Inventory settings
4. Create one tracked product with variants and lots
5. Add stock with expiry dates
6. Open Inventory → Stock Reservations → Reservation Batches
7. Create one full allocation batch
8. Create one partial allocation batch
9. Show Stock Moves and Transfers
10. Show Dashboard and API Tokens
11. Close with testing, performance, DB, and concurrency notes
