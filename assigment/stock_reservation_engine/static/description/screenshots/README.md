# UI screenshots (`stock_reservation_engine`)

PNG captures for documentation and the Apps listing ship under Odoo’s standard **`static/description/screenshots/`** tree (web-served under `/stock_reservation_engine/static/description/screenshots/...`).

```
static/description/screenshots/
├── capture/          ← Playwright `npm run capture` (broad UI tour)
├── walkthrough/      ← Playwright `npm run walkthrough` (assignment delivery set)
└── README.md         ← this file
```

List and analysis screenshots from **`capture`** run **`clearSearchFilters`** first so **default search facets** are removed and **all matching records** can appear where rights allow.

## Generate — capture tour

From `tools/screenshots/`:

```bash
npm install
npx playwright install chromium
export ODOO_URL=http://127.0.0.1:8018
export ODOO_DB=odoo18
export ODOO_USER=admin
export ODOO_PASSWORD=admin
npm run capture
```

Default login in the script is **`admin` / `admin`** when `ODOO_USER` / `ODOO_PASSWORD` are not set.

Windows PowerShell:

```powershell
cd tools\screenshots
npm install
npx playwright install chromium
$env:ODOO_URL="http://127.0.0.1:8018"; $env:ODOO_DB="odoo18"; $env:ODOO_USER="admin"; $env:ODOO_PASSWORD="admin"; npm run capture
```

Or omit user/password env vars to use **`admin` / `admin`**:

```powershell
npm run capture
```

Optional: `HEADED=1` to watch the browser.

Output directory defaults to **`static/description/screenshots/capture/`**. Override with `SCREENSHOT_DIR`.

## Generate — delivery walkthrough

Same folder `tools/screenshots/`:

```powershell
npm run walkthrough
```

Output: **`static/description/screenshots/walkthrough/`**. See `walkthrough/SCREENSHOTS_INDEX.md`.

## Files (capture order)

| File | Content |
|------|---------|
| `01-login-page.png` | Login screen |
| `02-after-login.png` | Home after authentication |
| `03-inventory-app.png` | Inventory app open |
| `04-reservation-batches-list.png` | **Reservation Batches** list (filters cleared) |
| `05-reservation-batch-form-first-row.png` | First batch form |
| `06-reservation-batch-draft.png` | A batch in **Draft** (if present) |
| `07-api-tokens-list.png` | **API Tokens** list (filters cleared) |
| `08-api-token-form.png` | API token form |
| `09-warehouses-list.png` | **Warehouses** (filters cleared) |
| `10-warehouse-mdw-form.png` | **Main Demo Warehouse** |
| `11-products-templates-list.png` | **Products** templates (filters cleared) |
| `13-products-submenu.png` | **Products** submenu under Inventory |
| `14-locations-list.png` | **Locations** (`stock.action_location_form`; filters cleared) |
| `15-location-cold-zone-form.png` | **Cold Zone** location (if present) |
| `16-lots-serial-numbers-list.png` | **Lots / Serial Numbers** (filters cleared) |
| `17-lot-x001-form.png` | Lot **LOT-X-001** form (if present) |
| `18-product-demo-a-form.png` | **Demo Product A** template form |
| `19-product-perishable-x-form.png` | **Perishable Product X** template form |
| `20-reservation-batches-list-all.png` | **Reservation Batches** again after tour; filters cleared |
| `21-reservation-batch-partial-state.png` | A batch whose row shows **Partial** (if present) |
| `22-inventory-overview-kanban.png` | **Overview** kanban (`stock.stock_picking_type_action`; filters cleared) |
| `23-operations-types-list.png` | **Operations Types** list (filters cleared) |
| `24-operation-type-form-first.png` | First matching operation type form |
| `25-product-categories-list.png` | **Product Categories** (filters cleared) |
| `26-product-variants-list.png` | **Product Variants** (filters cleared; needs variant group) |
| `27-stock-reservations-menu-expanded.png` | **Stock Reservations** menu expanded |
| `28-reporting-menu-expanded.png` | **Reporting** menu expanded |
| `29-reporting-stock.png` | Reporting → **Stock** (`stock.action_product_stock_view`) |
| `30-reporting-locations-quants.png` | Reporting → **Locations** / quants (`stock.action_view_quants`; needs multi-location / owner / technical groups) |
| `31-reporting-moves-history.png` | Reporting → **Moves History** (`stock.stock_move_line_action`) |
| `32-reporting-moves-analysis.png` | Reporting → **Moves Analysis** (`stock.stock_move_action`) |
| `33-reporting-valuation.png` | Reporting → **Valuation** (`stock_account.stock_valuation_layer_action`; only if **stock_account** is installed) |

Extended steps need **Stock manager** (Reporting), **multi-location** / **lots** where noted, and **`product.group_product_variant`** for variants.

Many steps use **direct action URLs** (`/web#action=module.xmlid`) when menus are nested. Form screenshots skip automatic filter clearing so modal/list context stays stable.

If your build differs, re-run with `HEADED=1` and adjust `tools/screenshots/capture-screenshots.mjs`.

If only `01-login-page.png` appears, login detection failed: confirm Odoo is reachable and credentials work. On failure the script saves `99-login-failed.png` when possible.
