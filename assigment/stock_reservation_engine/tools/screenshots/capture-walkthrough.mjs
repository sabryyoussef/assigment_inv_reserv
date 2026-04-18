#!/usr/bin/env node
/**
 * Professional delivery-package walkthrough for stock_reservation_engine (Odoo 18).
 * Requires: Odoo running, module + demo data (demo_inventory_master + reservation_demo_data).
 *
 *   cd tools/screenshots && npm install && npx playwright install chromium
 *   npm run walkthrough
 *
 * Output: ../../static/description/screenshots/walkthrough/*.png (Odoo standard asset path).
 *
 * Uses authenticated JSON-RPC (call_kw) from the browser context to resolve stable xml ids → DB ids.
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
const API_TOKEN_RAW = process.env.DEMO_API_TOKEN || 'demo-reservation-api-token-change-me';

const MODULE_ROOT = path.resolve(__dirname, '..', '..');
const OUT_DIR =
  process.env.WALKTHROUGH_DIR ||
  path.join(MODULE_ROOT, 'static', 'description', 'screenshots', 'walkthrough');

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function hideChatterAndNoise(page) {
  await page.addStyleTag({
    content: `
      .o-mail-Chatter, .o_ChatterContainer, .o-mail-Form-chatter,
      .o_notification_manager, .o-toast-container { display: none !important; }
    `,
  });
}

async function waitNoBlockUI(page) {
  await page.locator('.o_blockUI').first().waitFor({ state: 'hidden', timeout: 60000 }).catch(() => {});
  await sleep(400);
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
  await page.locator('button[type="submit"], button.o_login_btn, .oe_login_form button.btn-primary').first().click();
  await page.waitForSelector('.o_web_client', { timeout: 180000 });
  await sleep(1200);
  await dismissTour(page);
}

/** Odoo 18 web client JSON-RPC (same shape as ORM.call): POST /web/dataset/call_kw/<model>/<method> */
async function callKw(page, model, method, args = [], kwargs = {}) {
  const urlPath = `/web/dataset/call_kw/${encodeURIComponent(model)}/${encodeURIComponent(method)}`;
  const result = await page.evaluate(
    async ({ urlPath, model, method, args, kwargs }) => {
      const res = await fetch(urlPath, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Requested-With': 'XMLHttpRequest',
        },
        credentials: 'same-origin',
        body: JSON.stringify({
          jsonrpc: '2.0',
          method: 'call',
          params: {
            model,
            method,
            args,
            kwargs,
          },
          id: Date.now(),
        }),
      });
      const json = await res.json();
      if (json.error) {
        throw new Error(json.error.data?.message || JSON.stringify(json.error));
      }
      return json.result;
    },
    { urlPath, model, method, args, kwargs },
  );
  return result;
}

async function resolveXmlId(page, module, name) {
  const rows = await callKw(page, 'ir.model.data', 'search_read', [
    [
      ['module', '=', module],
      ['name', '=', name],
    ],
  ], {
    fields: ['model', 'res_id'],
    limit: 1,
  });
  if (!rows?.length) return null;
  return { model: rows[0].model, res_id: rows[0].res_id };
}

/** Line `note` substring when xml_id row is missing (notes live on reservation lines, not batches). */
const BATCH_LINE_NOTE_FALLBACK = {
  demo_batch_draft: 'full allocation (Demo Product A',
  demo_batch_partial: 'Demo Product B: low on-hand',
  demo_batch_dual_full: 'Same product, two lines',
  demo_batch_empty: 'Demo Product C: no stock',
  demo_batch_fefo: 'earliest expiration',
};

async function resolveBatchResId(page, xmlRecordName) {
  const ref = await resolveXmlId(page, 'stock_reservation_engine', xmlRecordName);
  if (ref?.model === 'stock.reservation.batch' && ref.res_id) {
    return ref.res_id;
  }
  const needle = BATCH_LINE_NOTE_FALLBACK[xmlRecordName];
  if (needle) {
    const rows = await callKw(
      page,
      'stock.reservation.line',
      'search_read',
      [[['note', 'ilike', needle]]],
      { fields: ['batch_id'], limit: 1 },
    );
    const batchId = rows?.[0]?.batch_id;
    if (batchId) {
      return Array.isArray(batchId) ? batchId[0] : batchId;
    }
  }
  // FEFO demo: Perishable Product X + line note about expiration (no xml_id / float edge cases)
  if (xmlRecordName === 'demo_batch_fefo') {
    const byTmpl = await resolveXmlId(page, 'stock_reservation_engine', 'demo_pt_lots');
    const tmplId = byTmpl?.model === 'product.template' ? byTmpl.res_id : null;
    const tName = await callKw(
      page,
      'product.template',
      'search_read',
      [[['name', '=', 'Perishable Product X']]],
      { fields: ['id'], limit: 1 },
    );
    const effectiveTmpl = tmplId || tName?.[0]?.id;
    if (effectiveTmpl) {
      const pvs = await callKw(
        page,
        'product.product',
        'search_read',
        [[['product_tmpl_id', '=', effectiveTmpl]]],
        { fields: ['id'], limit: 1 },
      );
      const pid = pvs?.[0]?.id;
      if (pid) {
        for (const domain of [
          [['product_id', '=', pid], ['requested_qty', '=', 18]],
          [['product_id', '=', pid], ['requested_qty', '<=', 20], ['requested_qty', '>=', 10]],
        ]) {
          const lines = await callKw(page, 'stock.reservation.line', 'search_read', [domain], {
            fields: ['batch_id', 'note'],
            limit: 8,
          });
          const pick = lines.find(
            (l) => l.note && /expiration|FEFO|lot|perishable/i.test(l.note),
          ) || lines[0];
          if (pick?.batch_id) {
            const bid = pick.batch_id;
            return Array.isArray(bid) ? bid[0] : bid;
          }
        }
      }
    }
    try {
      const batchHit = await callKw(
        page,
        'stock.reservation.batch',
        'search_read',
        [[['line_ids.note', 'ilike', 'earliest expiration']]],
        { fields: ['id'], limit: 1 },
      );
      if (batchHit?.[0]?.id) return batchHit[0].id;
    } catch {
      /* One2many note domain may be unsupported in some builds */
    }
  }
  return null;
}

async function openBatchForm(page, xmlRecordName) {
  const resId = await resolveBatchResId(page, xmlRecordName);
  if (!resId) {
    throw new Error(`Could not resolve batch ${xmlRecordName}`);
  }
  const cleanBase = BASE_URL.replace(/\/$/, '');
  await page.goto(
    `${cleanBase}/web#id=${resId}&model=stock.reservation.batch&view_type=form`,
    { waitUntil: 'domcontentloaded', timeout: 120000 },
  );
  await sleep(1400);
  await waitNoBlockUI(page);
  await dismissTour(page);
  await hideChatterAndNoise(page);
}

async function gotoAction(page, actionXmlId) {
  const cleanBase = BASE_URL.replace(/\/$/, '');
  await page.goto(`${cleanBase}/web#action=${actionXmlId}`, {
    waitUntil: 'domcontentloaded',
    timeout: 120000,
  });
  await sleep(1400);
  await waitNoBlockUI(page);
  await dismissTour(page);
}

async function clearSearchFilters(page) {
  let guard = 0;
  while (guard++ < 35) {
    const facetRemove = page
      .locator(
        '.o_searchview .o_searchview_facet_remove, .o_searchview .o_facet_remove, .o_searchview_facet .o_facet_remove',
      )
      .first();
    const visible = await facetRemove.isVisible().catch(() => false);
    if (!visible) break;
    await facetRemove.click({ timeout: 1500 }).catch(() => {});
    await sleep(260);
  }
  const input = page.locator('.o_searchview .o_searchview_input').first();
  try {
    if (await input.isVisible({ timeout: 500 }).catch(() => false)) {
      await input.fill('');
      await input.press('Enter').catch(() => {});
      await sleep(400);
    }
  } catch {
    /* ignore */
  }
}

async function screenshotClean(page, filename, { fullPage = true } = {}) {
  await dismissTour(page);
  await waitNoBlockUI(page);
  await page.waitForSelector('.o_action_manager', { timeout: 45000 }).catch(() => {});
  await sleep(700);
  await page.screenshot({
    path: path.join(OUT_DIR, filename),
    fullPage,
  });
}

async function screenshotFormClean(page, filename) {
  await hideChatterAndNoise(page);
  await waitNoBlockUI(page);
  await page.waitForSelector('.o_form_view, .o_action_manager', { timeout: 45000 });
  await sleep(600);
  await page.screenshot({
    path: path.join(OUT_DIR, filename),
    fullPage: true,
  });
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
      /* next */
    }
  }
  const inv = page.getByText(/^Inventory$/i).first();
  try {
    await inv.waitFor({ state: 'visible', timeout: 5000 });
    await inv.click();
    await sleep(1800);
  } catch {
    /* already in inventory */
  }
}

async function clickAllocateIfVisible(page) {
  const btn = page.locator('button[name="action_allocate"]').first();
  if (await btn.isVisible({ timeout: 4000 }).catch(() => false)) {
    await btn.click();
    await waitNoBlockUI(page);
    await sleep(1200);
    return true;
  }
  return false;
}

async function clickStockMovesSmartButton(page) {
  const movesBtn = page.locator('.oe_stat_button[name="action_view_moves"], button[name="action_view_moves"]').first();
  await movesBtn.waitFor({ state: 'visible', timeout: 15000 });
  await movesBtn.click();
  await waitNoBlockUI(page);
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
    deviceScaleFactor: 1,
    locale: 'en-US',
  });

  const page = await context.newPage();
  page.setDefaultTimeout(120000);

  const skipped = [];
  const completed = [];

  console.log('Walkthrough output:', OUT_DIR);
  console.log('Odoo:', BASE_URL, 'db:', DB);

  try {
    await login(page);

    // --- A. Inventory setup ---
    await openInventoryApp(page);
    await gotoAction(page, 'stock.stock_picking_type_action');
    await clearSearchFilters(page);
    await screenshotClean(page, '01_inventory_overview.png');
    completed.push('01_inventory_overview.png');

    await openInventoryApp(page);
    await gotoAction(page, 'stock.action_warehouse_form');
    await clearSearchFilters(page);
    try {
      await page.locator('.o_searchview .o_searchview_input').first().fill('MDW');
      await page.keyboard.press('Enter');
      await sleep(1200);
    } catch {
      /* ignore */
    }
    await page
      .waitForSelector('.o_list_table tbody tr, tr.o_data_row', { timeout: 25000 })
      .catch(() => {});
    let mdw = page.locator('.o_list_table tbody tr.o_data_row').filter({ hasText: /Main Demo Warehouse|MDW/i }).first();
    if (!(await mdw.count())) {
      mdw = page.locator('.o_list_table tbody tr.o_data_row').first();
    }
    if (await mdw.count()) {
      await mdw.click();
      await sleep(1200);
      await hideChatterAndNoise(page);
      await screenshotFormClean(page, '02_warehouse_structure.png');
      await page.keyboard.press('Escape');
      await sleep(500);
      completed.push('02_warehouse_structure.png');
    } else {
      skipped.push('02_warehouse_structure.png (no warehouse rows in list)');
    }

    await openInventoryApp(page);
    await gotoAction(page, 'stock.action_location_form');
    await clearSearchFilters(page);
    await screenshotClean(page, '03_locations_tree.png');
    completed.push('03_locations_tree.png');

    await openInventoryApp(page);
    await gotoAction(page, 'stock.product_template_action_product');
    await clearSearchFilters(page);
    await screenshotClean(page, '04_products_list_demo.png');
    completed.push('04_products_list_demo.png');

    await openInventoryApp(page);
    await gotoAction(page, 'stock.action_production_lot_form');
    await clearSearchFilters(page);
    await screenshotClean(page, '05_lots_expiration_setup.png');
    completed.push('05_lots_expiration_setup.png');

    // --- B. Reservation flow (xml-id + note fallback) ---
    try {
      await openBatchForm(page, 'demo_batch_draft');
      await screenshotFormClean(page, '06_reservation_batch_form_draft.png');
      completed.push('06_reservation_batch_form_draft.png');
    } catch (e) {
      skipped.push(`06_reservation_batch_form_draft.png (${e.message})`);
    }

    try {
      await openBatchForm(page, 'demo_batch_partial');
      await screenshotFormClean(page, '07_reservation_batch_confirmed.png');
      completed.push('07_reservation_batch_confirmed.png');
    } catch (e) {
      skipped.push(`07_reservation_batch_confirmed.png (${e.message})`);
    }

    try {
      await openBatchForm(page, 'demo_batch_dual_full');
      await clickAllocateIfVisible(page);
      await hideChatterAndNoise(page);
      await screenshotFormClean(page, '08_full_allocation_result.png');
      completed.push('08_full_allocation_result.png');
    } catch (e) {
      skipped.push(`08_full_allocation_result.png (${e.message})`);
    }

    try {
      await openBatchForm(page, 'demo_batch_partial');
      await clickAllocateIfVisible(page);
      await hideChatterAndNoise(page);
      await screenshotFormClean(page, '09_partial_allocation_result.png');
      completed.push('09_partial_allocation_result.png');
    } catch (e) {
      skipped.push(`09_partial_allocation_result.png (${e.message})`);
    }

    try {
      await openBatchForm(page, 'demo_batch_empty');
      await clickAllocateIfVisible(page);
      await hideChatterAndNoise(page);
      await screenshotFormClean(page, '10_no_stock_result.png');
      completed.push('10_no_stock_result.png');
    } catch (e) {
      skipped.push(`10_no_stock_result.png (${e.message})`);
    }

    try {
      await openBatchForm(page, 'demo_batch_fefo');
      await clickAllocateIfVisible(page);
      await hideChatterAndNoise(page);
      await screenshotFormClean(page, '11_fefo_case.png');
      completed.push('11_fefo_case.png');
    } catch (e) {
      skipped.push(`11_fefo_case.png (${e.message})`);
    }

    // Related moves (batch that has moves after allocation)
    await openBatchForm(page, 'demo_batch_dual_full');
    try {
      await clickStockMovesSmartButton(page);
      await clearSearchFilters(page);
      await screenshotClean(page, '12_related_stock_moves.png');
      completed.push('12_related_stock_moves.png');
      await page.keyboard.press('Escape').catch(() => {});
    } catch (e) {
      skipped.push(`12_related_stock_moves.png (${e.message})`);
    }

    // C. Security: manager sees reservation API Tokens + Allocate
    try {
      await openInventoryApp(page);
      await page.locator('[data-menu-xmlid="stock_reservation_engine.menu_stock_reservation_root"]').first().waitFor({
        state: 'visible',
        timeout: 10000,
      });
      await page.locator('[data-menu-xmlid="stock_reservation_engine.menu_stock_reservation_root"]').first().click();
      await sleep(500);
      await page.locator('[data-menu-xmlid="stock_reservation_engine.menu_reservation_api_tokens"]').first().click();
      await waitNoBlockUI(page);
      await clearSearchFilters(page);
      await screenshotClean(page, '13_security_manager_api_tokens_menu.png');
      completed.push('13_security_manager_api_tokens_menu.png');
    } catch (e) {
      skipped.push(`13_security_manager_api_tokens_menu.png (${e.message})`);
    }

    // D. API proof (JSON response in browser)
    try {
      const batchId = await resolveBatchResId(page, 'demo_batch_dual_full');
      if (!batchId) {
        skipped.push('14_api_status_proof.png (could not resolve batch id)');
      } else {
        const apiPage = await context.newPage();
        await apiPage.setExtraHTTPHeaders({
          Authorization: `Bearer ${API_TOKEN_RAW}`,
        });
        const apiUrl = `${BASE_URL.replace(/\/$/, '')}/api/reservation/status/${batchId}`;
        await apiPage.goto(apiUrl, { waitUntil: 'domcontentloaded', timeout: 60000 });
        await sleep(600);
        await apiPage.screenshot({
          path: path.join(OUT_DIR, '14_api_status_proof.png'),
          fullPage: false,
        });
        await apiPage.close();
        completed.push('14_api_status_proof.png');
      }
    } catch (e) {
      skipped.push(`14_api_status_proof.png (${e.message})`);
    }

    const summaryPath = path.join(OUT_DIR, 'CAPTURE_SUMMARY.json');
    fs.writeFileSync(
      summaryPath,
      JSON.stringify(
        {
          completed,
          skipped,
          outputDir: OUT_DIR,
          timestamp: new Date().toISOString(),
        },
        null,
        2,
      ),
      'utf8',
    );

    console.log('Done. Completed:', completed.length, 'Skipped:', skipped.length);
    console.log(JSON.stringify({ completed, skipped }, null, 2));
  } finally {
    await browser.close();
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
