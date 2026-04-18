#!/usr/bin/env node
/**
 * Screenshots for docs/PRESENTATION_SCRIPT_EN.md (guide flow).
 * Env: ODOO_URL (default http://127.0.0.1:8018), ODOO_DB (aumit),
 * ODOO_LOGIN, ODOO_PASSWORD, PGHOST, PGPORT, PGUSER, PGPASSWORD
 * SCREENSHOT_DIR overrides output folder.
 * NEXT_STEP (1–15): only write screenshots with this number and above (full nav still runs).
 * If unset, uses (max existing NN-*.png prefix) + 1 to continue from last file.
 */

function getMaxExistingStep() {
  if (!fs.existsSync(OUT_DIR)) return 0;
  let max = 0;
  for (const f of fs.readdirSync(OUT_DIR)) {
    const m = String(f).match(/^(\d{2})-.*\.png$/i);
    if (m) max = Math.max(max, parseInt(m[1], 10));
  }
  return max;
}

/** First step 1..15 with no `NN-*.png` on disk (fills gaps; not just max+1). */
function getFirstMissingStep() {
  if (!fs.existsSync(OUT_DIR)) return 1;
  const files = fs.readdirSync(OUT_DIR);
  for (let s = 1; s <= 15; s++) {
    const prefix = `${String(s).padStart(2, '0')}-`;
    const has = files.some(
      (f) => f.startsWith(prefix) && f.toLowerCase().endsWith('.png')
    );
    if (!has) return s;
  }
  return 16;
}

function getNextStep() {
  if (process.env.NEXT_STEP !== undefined && String(process.env.NEXT_STEP).length) {
    return parseInt(process.env.NEXT_STEP, 10);
  }
  return getFirstMissingStep();
}

/** Minimal valid 1×1 PNG — used when smart buttons have no moves (presentation placeholder). */
const MIN_PNG_BASE64 =
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==';

function writePlaceholderPng(filename) {
  const target = path.join(OUT_DIR, filename);
  fs.mkdirSync(path.dirname(target), { recursive: true });
  fs.writeFileSync(target, Buffer.from(MIN_PNG_BASE64, 'base64'));
  console.log('wrote placeholder', target);
}

function snapPlaceholderStep(stepNum, filename) {
  if (stepNum < NEXT_STEP_NUM) return;
  writePlaceholderPng(filename);
}

import { chromium } from 'playwright';
import { execSync } from 'child_process';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const BASE_URL = process.env.ODOO_URL || 'http://127.0.0.1:8018';
const DB = process.env.ODOO_DB || 'aumit';
const LOGIN = process.env.ODOO_LOGIN || 'admin';
const PASSWORD = process.env.ODOO_PASSWORD || 'admin';

const OUT_DIR =
  process.env.SCREENSHOT_DIR ||
  path.resolve(
    __dirname,
    '../../addons/stock_reservation_engine/docs/screenshots_guide'
  );

const PG = {
  host: process.env.PGHOST || 'localhost',
  port: process.env.PGPORT || '5432',
  user: process.env.PGUSER || 'odoo18',
  password: process.env.PGPASSWORD || 'odoo18',
};

function delay(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

function queryActionMap() {
  const pairs = [
    ['stock', 'action_stock_config_settings'],
    ['stock', 'product_template_action_product'],
    ['stock', 'stock_product_normal_action'],
    ['stock', 'action_production_lot_form'],
    ['stock_reservation_engine', 'action_reservation_dashboard'],
    ['stock_reservation_engine', 'action_stock_reservation_batch'],
    ['stock_reservation_engine', 'action_reservation_api_token'],
  ];
  const tupleList = pairs.map(([m, n]) => `('${m}','${n}')`).join(',');
  const sql = `SELECT module || '.' || name AS k, res_id::text FROM ir_model_data WHERE model='ir.actions.act_window' AND (module, name) IN (${tupleList});`;
  const env = { ...process.env, PGPASSWORD: PG.password };
  const cmd = `psql -h ${PG.host} -p ${PG.port} -U ${PG.user} -d ${DB} -tA -c ${JSON.stringify(sql)}`;
  try {
    const out = execSync(cmd, { encoding: 'utf8', env }).trim();
    const map = {};
    for (const line of out.split('\n')) {
      if (!line || !line.includes('|')) continue;
      const [k, id] = line.split('|');
      map[k.trim()] = id.trim();
    }
    return map;
  } catch (e) {
    console.error('psql failed:', e.message);
    return {};
  }
}

let NEXT_STEP_NUM = 1;

async function screenshot(page, name) {
  await delay(500);
  const target = path.join(OUT_DIR, name);
  await page.screenshot({ path: target, fullPage: true });
  console.log('wrote', target);
}

/** Only capture if step index (1–15) is >= NEXT_STEP_NUM. */
async function snap(stepNum, page, filename) {
  if (stepNum < NEXT_STEP_NUM) {
    console.log('skip screenshot', filename, '(resume from step', String(NEXT_STEP_NUM) + ')');
    return;
  }
  await screenshot(page, filename);
}

async function gotoAction(page, actionMap, fullXmlId, shotName) {
  const id = actionMap[fullXmlId];
  if (!id) {
    console.warn('missing action id for', fullXmlId);
    return false;
  }
  await page.goto(`${BASE_URL}/web#action=${id}`, {
    waitUntil: 'domcontentloaded',
    timeout: 120000,
  });
  await page.waitForSelector('.o_action_manager, .o_web_client', {
    timeout: 120000,
  });
  await delay(1500);
  if (shotName) {
    const m = shotName.match(/^(\d{2})-/);
    const step = m ? parseInt(m[1], 10) : 0;
    if (step) await snap(step, page, shotName);
    else await screenshot(page, shotName);
  }
  return true;
}

async function login(page) {
  await page.goto(`${BASE_URL}/web/login?db=${encodeURIComponent(DB)}`, {
    waitUntil: 'networkidle',
    timeout: 120000,
  });
  await snap(1, page, '01-login-page.png');
  await page.locator('input[name="login"]').fill(LOGIN);
  await page.locator('input[name="password"]').fill(PASSWORD);
  await page.locator('button[type="submit"]').click();
  await page.waitForSelector('.o_web_client', { timeout: 120000 });
  await delay(1500);
  await snap(2, page, '02-after-login-home.png');
}

async function captureAppsSearch(page) {
  try {
    await page.goto(`${BASE_URL}/odoo`, {
      waitUntil: 'domcontentloaded',
      timeout: 60000,
    });
    await delay(2500);
    const search = page
      .locator('input[type="search"], input[placeholder*="Search"], input.o_searchview_input')
      .first();
    if (await search.isVisible({ timeout: 10000 }).catch(() => false)) {
      await search.fill('Stock Reservation');
      await delay(1500);
    }
    await snap(3, page, '03-apps-search-stock-reservation-engine.png');
  } catch (e) {
    console.warn('Apps screen:', e.message);
  }
}

async function searchProductInList(page, terms) {
  const box = page.locator('.o_searchview input.o_searchview_input').first();
  await box.click({ timeout: 8000 }).catch(() => {});
  for (const t of terms) {
    await box.fill(t);
    await page.keyboard.press('Enter');
    await delay(1500);
    const row = page.locator('.o_list_table tbody tr.o_data_row').first();
    if (await row.isVisible({ timeout: 5000 }).catch(() => false)) return true;
  }
  return false;
}

async function dismissBlockingModals(page, maxPasses = 8) {
  for (let pass = 0; pass < maxPasses; pass++) {
    const modal = page.locator('.modal.o_technical_modal.d-block');
    if (!(await modal.first().isVisible({ timeout: 400 }).catch(() => false))) break;
    const closeBtn = modal.locator('button.btn-close').first();
    if (await closeBtn.isVisible({ timeout: 600 }).catch(() => false)) {
      await closeBtn.click({ timeout: 3000 }).catch(() => {});
      await delay(450);
      continue;
    }
    const secondary = modal
      .getByRole('button', { name: /^(Cancel|Discard|Close)$/i })
      .first();
    if (await secondary.isVisible({ timeout: 600 }).catch(() => false)) {
      await secondary.click({ timeout: 3000 }).catch(() => {});
      await delay(450);
      continue;
    }
    await page.keyboard.press('Escape');
    await delay(450);
  }
}

async function tryConfirmAndAllocate(page) {
  await dismissBlockingModals(page);
  for (let i = 0; i < 5; i++) {
    const confirm = page.getByRole('button', { name: /^Confirm$/i });
    if (await confirm.isVisible({ timeout: 2500 }).catch(() => false)) {
      await dismissBlockingModals(page);
      await confirm.click({ timeout: 60000 });
      await delay(4000);
      continue;
    }
    break;
  }
  for (let i = 0; i < 5; i++) {
    const alloc = page.getByRole('button', { name: /^Allocate$/i });
    if (await alloc.isVisible({ timeout: 2500 }).catch(() => false)) {
      await dismissBlockingModals(page);
      await alloc.click({ timeout: 60000 });
      await delay(8000);
      continue;
    }
    break;
  }
}

/** Prefer a batch already Allocated (has moves); else open first row and Confirm+Allocate. */
async function openBestBatchRow(page) {
  const rows = page.locator('.o_list_table tbody tr.o_data_row');
  if (!(await rows.first().isVisible({ timeout: 25000 }).catch(() => false))) {
    console.warn('No rows in reservation batch list');
    return false;
  }
  const n = await rows.count();
  let openedAllocated = false;
  for (let i = 0; i < n; i++) {
    const txt = await rows.nth(i).innerText().catch(() => '');
    if (/\bAllocated\b/i.test(txt)) {
      await rows.nth(i).dblclick();
      openedAllocated = true;
      break;
    }
  }
  if (!openedAllocated) {
    await rows.first().dblclick();
    await page.waitForSelector('.o_form_view', { timeout: 60000 });
    await delay(800);
    await tryConfirmAndAllocate(page);
    await page
      .locator('button.oe_stat_button[name="action_view_moves"]')
      .waitFor({ state: 'visible', timeout: 120000 })
      .catch(() =>
        console.warn(
          'Stock Moves stat button did not appear (allocation may have no moves)'
        )
      );
    await delay(1500);
    return true;
  }
  await page.waitForSelector('.o_form_view', { timeout: 60000 });
  await delay(1200);
  return true;
}

async function clickStatButton(page, nameAttr) {
  const btn = page.locator(`button.oe_stat_button[name="${nameAttr}"]`).first();
  if (await btn.isVisible({ timeout: 8000 }).catch(() => false)) {
    await btn.click();
    await delay(2500);
    await page.waitForSelector('.o_action_manager', { timeout: 60000 });
    return true;
  }
  console.warn('Stat button not visible:', nameAttr);
  return false;
}

async function closeOptionalDialog(page) {
  await page.keyboard.press('Escape');
  await delay(400);
}

async function main() {
  fs.mkdirSync(OUT_DIR, { recursive: true });
  console.log('Output:', OUT_DIR);

  NEXT_STEP_NUM = getNextStep();
  console.log(
    `Capture steps >= ${NEXT_STEP_NUM} (first missing step; max NN on disk: ${getMaxExistingStep()})`
  );
  if (NEXT_STEP_NUM > 15) {
    console.log('All 15 screenshots already present — exiting.');
    process.exit(0);
  }

  const actionMap = queryActionMap();
  if (Object.keys(actionMap).length === 0) {
    console.error(
      'No action IDs resolved. Check psql, PG* env, and database',
      DB
    );
    process.exit(2);
  }
  console.log('Actions:', Object.keys(actionMap).length);

  const exe =
    process.env.PW_EXECUTABLE_PATH ||
    process.env.CHROMIUM_PATH ||
    undefined;
  const browser = await chromium.launch({
    headless: true,
    executablePath: exe || undefined,
    args: ['--disable-dev-shm-usage'],
  });
  const context = await browser.newContext({
    viewport: { width: 1600, height: 900 },
    locale: 'en-US',
  });
  const page = await context.newPage();

  await login(page);
  await captureAppsSearch(page);

  await gotoAction(
    page,
    actionMap,
    'stock.action_stock_config_settings',
    '04-inventory-configuration-settings.png'
  );

  await gotoAction(
    page,
    actionMap,
    'stock.product_template_action_product',
    '05-inventory-products-list.png'
  );

  await searchProductInList(page, [
    'Demo Product A',
    'Perishable Product X',
    'Demo Product',
  ]);
  await snap(6, page, '06-products-filtered-demo-product.png');

  await gotoAction(
    page,
    actionMap,
    'stock.stock_product_normal_action',
    '07-product-variants-list.png'
  );

  await gotoAction(
    page,
    actionMap,
    'stock.action_production_lot_form',
    '08-lots-serial-numbers.png'
  );

  await gotoAction(
    page,
    actionMap,
    'stock_reservation_engine.action_reservation_dashboard',
    '09-stock-reservations-dashboard.png'
  );

  await gotoAction(
    page,
    actionMap,
    'stock_reservation_engine.action_stock_reservation_batch',
    '10-reservation-batches-list.png'
  );

  if (await openBestBatchRow(page)) {
    await snap(11, page, '11-reservation-batch-form-after-allocate.png');

    const openedMoves = await clickStatButton(page, 'action_view_moves');
    if (openedMoves) {
      await snap(12, page, '12-stock-moves-from-batch.png');
      await closeOptionalDialog(page);
    } else {
      snapPlaceholderStep(12, '12-stock-moves-from-batch.png');
    }
    const openedPickings = await clickStatButton(page, 'action_view_pickings');
    if (openedPickings) {
      await snap(13, page, '13-transfers-from-batch.png');
      await closeOptionalDialog(page);
    } else {
      snapPlaceholderStep(13, '13-transfers-from-batch.png');
    }
  }

  await gotoAction(
    page,
    actionMap,
    'stock_reservation_engine.action_stock_reservation_batch',
    null
  );
  await delay(800);
  const newBtn = page.getByRole('button', { name: /^New$/i }).first();
  if (await newBtn.isVisible({ timeout: 12000 }).catch(() => false)) {
    await newBtn.click();
    await delay(2500);
    await snap(14, page, '14-new-reservation-batch-form.png');
  } else {
    console.warn('New button not found — screenshot skipped');
  }

  await gotoAction(
    page,
    actionMap,
    'stock_reservation_engine.action_reservation_api_token',
    '15-api-tokens-list.png'
  );

  await browser.close();
  console.log('Done.');
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
