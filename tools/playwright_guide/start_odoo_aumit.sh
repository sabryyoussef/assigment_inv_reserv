#!/usr/bin/env bash
# Start Odoo with database aumit on http_port from odoo.conf (8018).
set -euo pipefail

BASE=/home/sabry3/sabry_backup/odoo_base/base_odoo_18
CONF="$BASE/odoo_conf/odoo.conf"
LOG="$BASE/logs/odoo_aumit_live.log"
PIDFILE="$BASE/logs/odoo_aumit_live.pid"
DB=aumit

echo "--- stop prior Odoo using database $DB ---"
while read -r pid; do
  cmd=$(tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null || true)
  [[ "$cmd" == *odoo-bin* ]] || continue
  [[ "$cmd" =~ (^|[[:space:]])-d[[:space:]]+$DB([[:space:]]|$) ]] || continue
  echo "TERM $pid"
  kill -TERM "$pid" 2>/dev/null || true
done < <(pgrep -f 'odoo-bin' || true)
sleep 2

echo "--- start Odoo ---"
cd "$BASE/odoo18"
nohup ./odoo-bin -c "$CONF" -d "$DB" >>"$LOG" 2>&1 &
echo $! >"$PIDFILE"
echo "PID $(cat "$PIDFILE") log $LOG"

echo "--- wait for :8018 ---"
for i in $(seq 1 120); do
  if ss -tlnp 2>/dev/null | grep -qE ':8018\s'; then
    echo "OK listening on 8018 (${i}s)"
    exit 0
  fi
  sleep 1
done
echo "FAILED see tail $LOG"
tail -50 "$LOG"
exit 1
