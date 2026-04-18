#!/usr/bin/env bash
# Start Odoo on DB aumit (user sometimes types "aumet"; this is the DB we created) and run Playwright capture (PRESENTATION_SCRIPT_EN.md flow).
set -euo pipefail

BASE=/home/sabry3/sabry_backup/odoo_base/base_odoo_18
CONF="$BASE/odoo_conf/odoo.conf"
ODOO_BIN="$BASE/odoo18/odoo-bin"
LOG="$BASE/logs/odoo_aumit_live.log"
DB=aumit
TOOLS="$(cd "$(dirname "$0")" && pwd)"

echo "--- stop existing Odoo bound to DB $DB (odoo-bin only) ---"
while read -r pid; do
  cmd=$(tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null || true)
  [[ "$cmd" == *odoo-bin* ]] || continue
  [[ "$cmd" =~ (^|[[:space:]])-d[[:space:]]+$DB([[:space:]]|$) ]] || continue
  echo "TERM $pid"
  kill -TERM "$pid" 2>/dev/null || true
done < <(pgrep -f 'odoo-bin' || true)
sleep 3

echo "--- start Odoo $ODOO_BIN -d $DB ---"
cd "$BASE/odoo18"
nohup ./odoo-bin -c "$CONF" -d "$DB" >>"$LOG" 2>&1 &
echo $! >"$BASE/logs/odoo_aumit_live.pid"

echo "--- wait for :8018 ---"
for i in $(seq 1 90); do
  if ss -tlnp 2>/dev/null | grep -qE ':8018\s'; then
    echo "listening on 8018 (after ${i}s)"
    sleep 4
    break
  fi
  sleep 1
  if [[ $i -eq 90 ]]; then
    echo "TIMEOUT: Odoo did not open 8018 — see $LOG"
    tail -40 "$LOG" || true
    exit 1
  fi
done

export ODOO_URL="${ODOO_URL:-http://127.0.0.1:8018}"
export ODOO_DB="$DB"
export ODOO_LOGIN="${ODOO_LOGIN:-admin}"
export ODOO_PASSWORD="${ODOO_PASSWORD:-admin}"
# Playwright browser install on ext4 (FUSE project path can break ms-playwright executables)
export PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH:-$HOME/.cache/ms-playwright}"
mkdir -p "$PLAYWRIGHT_BROWSERS_PATH"

cd "$TOOLS"
# npm cache on FUSE/sabry_backup breaks with ENOENT; keep cache on local home
export NPM_CONFIG_CACHE="${NPM_CONFIG_CACHE:-$HOME/.npm}"
mkdir -p "$NPM_CONFIG_CACHE"
if [[ ! -d "$TOOLS/node_modules/playwright" ]]; then
  npm install --no-audit --no-fund
else
  echo "node_modules already present; skip npm install"
fi

echo "--- playwright install chromium (browsers: $PLAYWRIGHT_BROWSERS_PATH) ---"
# Headless shell is separate from chromium.executablePath(); smoke-test real launch (not path guess)
npx playwright install chromium --with-deps || npx playwright install chromium --force || npx playwright install chromium

echo "--- playwright smoke launch ---"
node --input-type=module <<'EOSMOKE'
import { chromium } from 'playwright';
let b;
try {
  b = await chromium.launch({ headless: true });
  await b.close();
  console.log('Playwright chromium launch OK');
} catch (e) {
  console.error(e);
  process.exit(1);
}
EOSMOKE
if [[ $? -ne 0 ]]; then
  echo "FATAL: playwright cannot launch chromium — try: sudo npx playwright install-deps (Linux deps)"
  exit 1
fi

unset PW_EXECUTABLE_PATH CHROMIUM_PATH

echo "--- playwright capture ---"
set -o pipefail
node capture-guide.mjs 2>&1 | tee run.log
CAPTURE_EC="${PIPESTATUS[0]}"
set +o pipefail
if [[ "${CAPTURE_EC:-1}" -ne 0 ]]; then
  echo "capture-guide.mjs failed with exit $CAPTURE_EC"
  exit "$CAPTURE_EC"
fi

echo "--- done ---"
