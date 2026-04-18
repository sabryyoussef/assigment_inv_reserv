#!/usr/bin/env node
/**
 * Capture UI screenshots for stock_reservation_engine (Odoo 18 web client).
 *
 * Prerequisites: Odoo running; module + demo data installed.
 *
 *   cd tools/screenshots
 *   npm install
 *   npx playwright install chromium
 *   set ODOO_URL=http://127.0.0.1:8018 && set ODOO_DB=odoo18 && set ODOO_USER=admin && set ODOO_PASSWORD=admin
 *   npm run capture
 *
 * Output: ../../static/description/screenshots/capture/*.png (Odoo standard asset path).
 */
import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const BASE_URL = process.env.ODOO_URL || 'http://127.0.0.1:8018';
const DB = process.env.ODOO_DB || 'odoo18';
const USER = process.env.ODOO_USER || 'admin';
const PASS = process.env.ODOO_PASSWORD || 'admin';

const MODULE_ROOT = path.resolve(__dirname, '..', '..');
const OUT_DIR =
  process.env.SCREENSHOT_DIR ||
  path.join(MODULE_ROOT, 'static', 'description', 'screenshots', 'capture');

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/** Remove search facets and text so list/pivot views show unfiltered rows (handles `search_default_*` actions). */
async function clearSearchFilters(page) {
  let guard = 0;
  while (guard++ < 40) {
    const facetRemove = page
      .locator(
        '.o_searchview .o_searchview_facet_remove, .o_searchview .o_facet_remove, .o_searchview_facet .o_facet_remove',
      )
      .first();
    const visible = await facetRemove.isVisible().catch(() => false);
    if (!visible) break;
    await facetRemove.click({ timeout: 1500 }).catch(() => {});
    await sleep(280);
  }
  const input = page.locator('.o_searchview .o_searchview_input').first();
  try {
    if (await input.isVisible({ timeout: 600 }).catch(() => false)) {
      await input.fill('');
      await input.press('Enter').catch(() => {});
      await sleep(450);
    }
  } catch {
    /* ignore */
  }
}

/** Open an ir.actions.act_window by external id (works when nested menus lack data-menu-xmlid in the DOM). */
async function gotoOdooAction(page, actionXmlId) {
  const cleanBase = BASE_URL.replace(/\/$/, '');
  await page.goto(`${cleanBase}/web#action=${actionXmlId}`, {
    waitUntil: 'domcontentloaded',
    timeout: 120000,
  });
  await sleep(1800);
  await dismissTour(page);
}

async function dismissTour(page) {
  try {
    await page.locator('.o_onboarding_container .close, .modal-header .btn-close').first().click({ timeout: 2000 });
  } catch {
    /* ignore */
  }
}

async function login(page) {
  const loginUrl = `${BASE_URL.replace(/\/$/, '')}/web/login?db=${encodeURIComponent(DB)}`;
  await page.goto(loginUrl, { waitUntil: 'domcontentloaded', timeout: 120000 });
  await sleep(400);

  const dbSelect = page.locator('select[name="db"], select#db');
  if (await dbSelect.count()) {
    await dbSelect.selectOption({ label: DB }).catch(async () => {
      await dbSelect.selectOption({ value: DB }).catch(() => {});
    });
    await sleep(300);
  }

  await page.locator('input[name="login"]').fill(USER);
  await page.locator('input[name="password"]').fill(PASS);
  await page.screenshot({ path: path.join(OUT_DIR, '01-login-page.png'), fullPage: true });

  await page.locator('button[type="submit"], button.o_login_btn, .oe_login_form button.btn-primary').first().click();

  // Never use waitForURL(/\/web/) — /web/login matches that pattern and resolves before auth completes.
  try {
    await page.waitForSelector('.o_web_client', { timeout: 180000 });
  } catch (e) {
    await page.screenshot({ path: path.join(OUT_DIR, '99-login-failed.png'), fullPage: true });
    throw new Error(
      `Login did not reach the web client (.o_web_client). Check URL ${BASE_URL}, database ${DB}, and credentials. ${e.message}`,
    );
  }
  await sleep(1500);
  await dismissTour(page);
}

async function clickMenuByXmlId(page, xmlId, { optional = false } = {}) {
  const sel = `[data-menu-xmlid="${xmlId}"]`;
  const loc = page.locator(sel).first();
  try {
    await loc.waitFor({ state: 'visible', timeout: 10000 });
    await loc.scrollIntoViewIfNeeded();
    await loc.click();
    await sleep(1200);
    return true;
  } catch (e) {
    if (!optional) {
      console.warn(`Menu not found or not clickable: ${xmlId}`, e.message);
    }
    return false;
  }
}

/** Products → Products (templates). Child menu is not top-level; parent must be opened first. */
async function openProductTemplatesList(page) {
  await openInventoryApp(page);
  await clickMenuByXmlId(page, 'stock.menu_stock_inventory_control');
  await sleep(400);
  await clickMenuByXmlId(page, 'stock.menu_product_variant_config_stock');
}

/** Stock Reservations → Reservation Batches (nested under root). */
async function openReservationBatches(page) {
  await openInventoryApp(page);
  await clickMenuByXmlId(page, 'stock_reservation_engine.menu_stock_reservation_root');
  await sleep(400);
  await clickMenuByXmlId(page, 'stock_reservation_engine.menu_stock_reservation_batches');
}

async function openInventoryApp(page) {
  await dismissTour(page);
  const toggles = [
    page.locator('.o_navbar_apps_menu button'),
    page.locator('[data-hotkey="a"]'),
    page.locator('.o_menu_toggle'),
  ];
  for (const t of toggles) {
    try {
      if (await t.first().isVisible({ timeout: 1500 }).catch(() => false)) {
        await t.first().click();
        await sleep(500);
        break;
      }
    } catch {
      /* try next */
    }
  }
  const inv = page.getByText(/^Inventory$/i).first();
  try {
    await inv.waitFor({ state: 'visible', timeout: 5000 });
    await inv.click();
    await sleep(2000);
  } catch {
    /* may already be in Inventory */
  }
}

async function screenshotAction(page, filename, { clearFilters = true } = {}) {
  await dismissTour(page);
  await page.waitForSelector('.o_action_manager', { timeout: 30000 }).catch(() => {});
  if (clearFilters) {
    await clearSearchFilters(page);
  }
  await sleep(900);
  await page.screenshot({ path: path.join(OUT_DIR, filename), fullPage: true });
}

async function openFirstListRow(page) {
  const row = page.locator('.o_list_table tbody tr.o_data_row, table.o_list_table tbody tr.o_data_row').first();
  await row.waitFor({ state: 'visible', timeout: 15000 });
  await row.click();
  await sleep(1200);
}

async function main() {
  fs.mkdirSync(OUT_DIR, { recursive: true });

  const browser = await chromium.launch({
    headless: process.env.HEADED ? false : true,
    args: ['--window-size=1920,1080'],
  });

  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 },
    locale: 'en-US',
  });

  const page = await context.newPage();
  page.setDefaultTimeout(90000);

  console.log('Screenshot output:', OUT_DIR);
  console.log('Target Odoo:', BASE_URL, 'db:', DB);

  try {
    await login(page);
    await page.screenshot({ path: path.join(OUT_DIR, '02-after-login.png'), fullPage: true });

    await openInventoryApp(page);
    await page.screenshot({ path: path.join(OUT_DIR, '03-inventory-app.png'), fullPage: true });

    await openReservationBatches(page);
    await screenshotAction(page, '04-reservation-batches-list.png');

    try {
      await openFirstListRow(page);
      await screenshotAction(page, '05-reservation-batch-form-first-row.png', { clearFilters: false });
      await page.keyboard.press('Escape');
      await sleep(600);
    } catch (e) {
      console.warn('Batch form (first row):', e.message);
    }

    try {
      await openReservationBatches(page);
      await sleep(400);
      const draftRow = page.locator('.o_list_table tbody tr.o_data_row').filter({ hasText: /Draft/i }).first();
      if (await draftRow.count()) {
        await draftRow.click();
        await sleep(1500);
        await screenshotAction(page, '06-reservation-batch-draft.png', { clearFilters: false });
        await page.keyboard.press('Escape');
        await sleep(500);
      }
    } catch (e) {
      console.warn('Draft batch:', e.message);
    }

    await openInventoryApp(page);
    await clickMenuByXmlId(page, 'stock_reservation_engine.menu_stock_reservation_root');
    await clickMenuByXmlId(page, 'stock_reservation_engine.menu_reservation_api_tokens');
    await screenshotAction(page, '07-api-tokens-list.png');

    try {
      await openFirstListRow(page);
      await screenshotAction(page, '08-api-token-form.png', { clearFilters: false });
      await page.keyboard.press('Escape');
      await sleep(500);
    } catch (e) {
      console.warn('API token form:', e.message);
    }

    await openInventoryApp(page);
    await clickMenuByXmlId(page, 'stock.menu_stock_config_settings');
    await sleep(600);
    await clickMenuByXmlId(page, 'stock.menu_action_warehouse_form');
    await screenshotAction(page, '09-warehouses-list.png');

    try {
      const mdw = page.locator('.o_list_table tbody tr.o_data_row').filter({ hasText: /Main Demo Warehouse/i }).first();
      if (await mdw.count()) {
        await mdw.click();
        await sleep(1500);
        await screenshotAction(page, '10-warehouse-mdw-form.png', { clearFilters: false });
      }
    } catch (e) {
      console.warn('MDW form:', e.message);
    }

    await openProductTemplatesList(page);
    await screenshotAction(page, '11-products-templates-list.png');

    await openInventoryApp(page);
    await clickMenuByXmlId(page, 'stock.menu_stock_inventory_control');
    await sleep(500);
    await screenshotAction(page, '13-products-submenu.png');

    // --- Extended: warehouse locations, lots, products (detail), batches, operations ---
    try {
      await openInventoryApp(page);
      await gotoOdooAction(page, 'stock.action_location_form');
      await screenshotAction(page, '14-locations-list.png');
      const coldLoc = page.locator('.o_list_table tbody tr.o_data_row').filter({ hasText: /Cold Zone/i }).first();
      if (await coldLoc.count()) {
        await coldLoc.click();
        await sleep(1200);
        await screenshotAction(page, '15-location-cold-zone-form.png', { clearFilters: false });
        await page.keyboard.press('Escape');
        await sleep(500);
      }
    } catch (e) {
      console.warn('14-15 locations:', e.message);
    }

    try {
      await openInventoryApp(page);
      await gotoOdooAction(page, 'stock.action_production_lot_form');
      await screenshotAction(page, '16-lots-serial-numbers-list.png');
      const lot001 = page.locator('.o_list_table tbody tr.o_data_row').filter({ hasText: /LOT-X-001/i }).first();
      if (await lot001.count()) {
        await lot001.click();
        await sleep(1200);
        await screenshotAction(page, '17-lot-x001-form.png', { clearFilters: false });
        await page.keyboard.press('Escape');
        await sleep(400);
      }
    } catch (e) {
      console.warn('16-17 lots:', e.message);
    }

    try {
      await openProductTemplatesList(page);
      await sleep(600);
      await clearSearchFilters(page);
      await page.locator('.o_searchview input.o_searchview_input').first().fill('Demo Product A');
      await page.keyboard.press('Enter');
      await sleep(1500);
      const rowA = page.locator('.o_list_table tbody tr.o_data_row').filter({ hasText: /Demo Product A/i }).first();
      if (await rowA.count()) {
        await rowA.click();
        await sleep(1200);
        await screenshotAction(page, '18-product-demo-a-form.png', { clearFilters: false });
        await page.keyboard.press('Escape');
        await sleep(400);
      }
    } catch (e) {
      console.warn('18 product A:', e.message);
    }

    try {
      await openProductTemplatesList(page);
      await sleep(600);
      await clearSearchFilters(page);
      await page.locator('.o_searchview input.o_searchview_input').first().fill('Perishable Product X');
      await page.keyboard.press('Enter');
      await sleep(1500);
      const rowX = page.locator('.o_list_table tbody tr.o_data_row').filter({ hasText: /Perishable Product X/i }).first();
      if (await rowX.count()) {
        await rowX.click();
        await sleep(1200);
        await screenshotAction(page, '19-product-perishable-x-form.png', { clearFilters: false });
        await page.keyboard.press('Escape');
        await sleep(400);
      }
    } catch (e) {
      console.warn('19 perishable X:', e.message);
    }

    try {
      await openReservationBatches(page);
      await screenshotAction(page, '20-reservation-batches-list-all.png');
    } catch (e) {
      console.warn('20 batches list:', e.message);
    }

    try {
      await openReservationBatches(page);
      await sleep(800);
      const partialRow = page.locator('.o_list_table tbody tr.o_data_row').filter({ hasText: /Partial/i }).first();
      if (await partialRow.count()) {
        await partialRow.click();
        await sleep(1200);
        await screenshotAction(page, '21-reservation-batch-partial-state.png', { clearFilters: false });
        await page.keyboard.press('Escape');
        await sleep(400);
      }
    } catch (e) {
      console.warn('21 partial batch:', e.message);
    }

    try {
      await openInventoryApp(page);
      await gotoOdooAction(page, 'stock.stock_picking_type_action');
      await screenshotAction(page, '22-inventory-overview-kanban.png');
    } catch (e) {
      console.warn('22 overview:', e.message);
    }

    try {
      await openInventoryApp(page);
      await gotoOdooAction(page, 'stock.action_picking_type_list');
      await screenshotAction(page, '23-operations-types-list.png');
      const mdwPick = page.locator('.o_list_table tbody tr.o_data_row').filter({ hasText: /MDW|Main Demo Warehouse|Receipts|Delivery/i }).first();
      if (await mdwPick.count()) {
        await mdwPick.click();
        await sleep(1200);
        await screenshotAction(page, '24-operation-type-form-first.png', { clearFilters: false });
        await page.keyboard.press('Escape');
        await sleep(400);
      }
    } catch (e) {
      console.warn('23-24 operations types:', e.message);
    }

    try {
      await openInventoryApp(page);
      await gotoOdooAction(page, 'product.product_category_action_form');
      await screenshotAction(page, '25-product-categories-list.png');
    } catch (e) {
      console.warn('25 categories:', e.message);
    }

    try {
      await openInventoryApp(page);
      await clickMenuByXmlId(page, 'stock.menu_stock_inventory_control');
      await sleep(400);
      await clickMenuByXmlId(page, 'stock.product_product_menu');
      await screenshotAction(page, '26-product-variants-list.png');
    } catch (e) {
      console.warn('26 variants:', e.message);
    }

    try {
      await openInventoryApp(page);
      await clickMenuByXmlId(page, 'stock_reservation_engine.menu_stock_reservation_root');
      await sleep(600);
      await page.screenshot({ path: path.join(OUT_DIR, '27-stock-reservations-menu-expanded.png'), fullPage: true });
    } catch (e) {
      console.warn('27 reservations menu:', e.message);
    }

    // --- Reporting (Inventory): parent menu + every standard submenu action, filters cleared on data views ---
    try {
      await openInventoryApp(page);
      await clickMenuByXmlId(page, 'stock.menu_warehouse_report');
      await sleep(800);
      await page.screenshot({ path: path.join(OUT_DIR, '28-reporting-menu-expanded.png'), fullPage: true });
    } catch (e) {
      console.warn('28 reporting menu:', e.message);
    }

    const reportingScreens = [
      ['29-reporting-stock.png', 'stock.action_product_stock_view'],
      ['30-reporting-locations-quants.png', 'stock.action_view_quants'],
      ['31-reporting-moves-history.png', 'stock.stock_move_line_action'],
      ['32-reporting-moves-analysis.png', 'stock.stock_move_action'],
    ];
    for (const [fname, actionXml] of reportingScreens) {
      try {
        await openInventoryApp(page);
        await gotoOdooAction(page, actionXml);
        await screenshotAction(page, fname);
      } catch (e) {
        console.warn(fname, e.message);
      }
    }

    try {
      await openInventoryApp(page);
      await gotoOdooAction(page, 'stock_account.stock_valuation_layer_action');
      await screenshotAction(page, '33-reporting-valuation.png');
    } catch (e) {
      console.warn('33 valuation (needs stock_account):', e.message);
    }

    console.log('Done. Images in:', OUT_DIR);
  } finally {
    await browser.close();
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
