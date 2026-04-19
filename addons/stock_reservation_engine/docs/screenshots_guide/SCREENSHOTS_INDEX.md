# Screenshot guide index

This folder holds PNG captures produced by `tools/playwright_guide/capture-guide.mjs`, aligned with **[`PRESENTATION_SCRIPT_EN.md`](../PRESENTATION_SCRIPT_EN.md)**.

**Note:** The live automation logs in as **Administrator** (`admin`). The script uses **demo database products** (for example **Demo Product A**, **Perishable Product X**) when the scenario text names **Antibiotic Kit**—the narrative is the same (storable product, variants, allocation). Screenshots **`12`** and **`13`** are real UI captures when Stock Moves / Transfers smart buttons exist after allocation; otherwise minimal **placeholder** PNGs keep the folder complete.

| File | Presentation part | Scenario (from script) |
|------|-------------------|-------------------------|
| `01-login-page.png` | **Part 1** – Open Odoo | “Open … Click Open Odoo. **Log in as the administrator.**” Captures the login screen before credentials are submitted. |
| `02-after-login-home.png` | **Part 1** – Open Odoo | Landing view immediately **after administrator login**, ready to open Apps or modules. |
| `03-apps-search-stock-reservation-engine.png` | **Part 2** – Install the custom module | **Apps** screen with search for **Stock Reservation Engine**: “Open the Apps screen. Search for Stock Reservation Engine.” (Install step may already be done in a seeded DB.) |
| `04-inventory-configuration-settings.png` | **Part 4** – Inventory settings required for the demo | **Inventory → Configuration → Settings** — settings needed so allocation can use locations, lots, expiry: Storage Locations, Lots & Serial Numbers, Expiration Dates, optional routes (**FEFO/FIFO narrative**). |
| `05-inventory-products-list.png` | **Part 5** – Create the product template | **Inventory → Products → Products** — list/kanban of products (“Create a new product … Storable … Tracking by Lots” in script). |
| `06-products-filtered-demo-product.png` | **Part 5** – Product setup | Same menu with search narrowed to a **demo storable product** (script example: Antibiotic Kit; automation may show **Demo Product A** / **Perishable Product X**). Supports the line “reservation lines work on the **real product variant**”. |
| `07-product-variants-list.png` | **Part 5** – Variants | **Inventory → Products → Product Variants** — “Then show the generated variants” so lines can target **`product_id`** variants. |
| `08-lots-serial-numbers.png` | **Part 6** – Lots / expiry (overview) | **Lots/Serial Numbers** overview — aligns with optional review “Inventory → Products → Lots/Serial Numbers” for **FEFO** storytelling (two lots with different expiry in script). |
| `09-stock-reservations-dashboard.png` | **Parts 7–8** – Dashboard | **Inventory → Stock Reservations → Dashboard** — graph/pivot visibility, filters (**Allocated**, **Partial**, **Not Available**), group by Product / State; “operational visibility into reservation outcomes”. |
| `10-reservation-batches-list.png` | **Part 9** – Reservation Batches list | **Inventory → Stock Reservations → Reservation Batches** — columns Name, Request User, State, Priority, Scheduled Date, Stock Moves count, Transfers count; **`stock.reservation.batch`** tree. |
| `11-reservation-batch-form-after-allocate.png` | **Part 10** – Use Case 1: Full allocation | Batch form after **Confirm / Allocate**: illustrates “**Allocated Qty**, line **Allocated**, batch **Allocated**, generated moves” narrative; smart buttons visible when **`move_count` / `picking_count` > 0**. |
| `12-stock-moves-from-batch.png` | **Part 11** – Generated stock moves | From the batch form: **Stock Moves smart button** — “generated **stock.move** records after allocation … link back to the reservation line.” May be placeholder if no moves exist in DB. |
| `13-transfers-from-batch.png` | **Part 11** – Transfers | **Transfers smart button** — internal transfer/picking linkage. May be placeholder if none generated. |
| `14-new-reservation-batch-form.png` | **Parts 10 / 12 / 13** – Create batch | **Reservation Batches → Create** — blank form path used for Use Case 1 (**Part 10**), and same entry point for **Part 12** (partial) and **Part 13** (no stock); separate scenario states are **not** extra PNGs in this automation set. |
| `15-api-tokens-list.png` | **Part 15** – API Tokens | **Inventory → Stock Reservations → API Tokens** (manager) — token-based authentication for external systems; “Create a token for one user.” |

## Scenarios from the script **not** represented by a dedicated PNG here

These are documented in **`PRESENTATION_SCRIPT_EN.md`** but have **no separate image** in this numbered set:

| Presentation part | Topic |
|-------------------|--------|
| **Part 3** | Creating **Demo Reservation User** / **Demo Reservation Manager** (Settings → Users). |
| **Part 14** | Security demo: login as reservation **user** vs **manager**, record isolation. |
| **Part 16** | **Postman/curl** API demo (endpoints `/api/reservation/create`, `/allocate`, `/status/<id>`). |
| **Parts 18+** | Sprint, tests, DB tuning, concurrency — spoken close-out, not screenshots. |

For **Part 12** (partial allocation) and **Part 13** (no stock), the script describes **different batches and quantities** on the **same Create** screen—see narrative in the main presentation file; capturing every state would need extra labeled screenshots beyond `01`–`15`.

---

See also: **[`../PRESENTATION_SCRIPT_EN.md`](../PRESENTATION_SCRIPT_EN.md)** for full “What to say” and requirement mapping.
