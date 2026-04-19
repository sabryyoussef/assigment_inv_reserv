# Quick Reference - Load Test Results

## 📊 Performance Summary

| Metric | 50 Users | 100 Users | 200 Users |
|--------|----------|-----------|-----------|
| **Failure Rate** | 0% ✅ | 11.76% ⚠️ | 90.11% ❌ |
| **Avg Response** | 5.2s | 11.6s | 10.7s |
| **Throughput (RPS)** | 8.13 | 6.91 ⬇️ | 12.81* |
| **Status** | STABLE | DEGRADED | FAILED |

*90% of requests failed at 200 users

## 🔴 Critical Issues

1. **Worker Exhaustion** - Throughput decreased from 50→100 users
2. **Database Locks** - Empty responses indicate lock timeouts
3. **High Baseline Latency** - 5s response time even with zero load
4. **No Graceful Degradation** - System fails silently under pressure

## ⚡ Immediate Fixes

```ini
# odoo18.conf - Add these settings:
workers = 9
db_maxconn = 128
limit_time_real = 120
limit_time_cpu = 60
```

## 🎯 Recommended Production Limit

**Current State:**
- Max 40-50 concurrent users
- ~8 requests/second
- p95 response time: 7 seconds

**Do NOT deploy to production without:**
1. Increasing Odoo workers
2. Profiling SQL queries
3. Adding request timeouts
4. Re-testing at 100 users

## 📁 Files Generated

- `LOAD_TEST_REPORT.md` - Full detailed analysis
- `locust/report_50users.html` - Interactive 50-user metrics
- `locust/report_100users.html` - Interactive 100-user metrics
- `locust/report_200users.html` - Interactive 200-user metrics
- `locust/locustfile.py` - Test script (reusable)
- `.env` - Runtime configuration

## 🔄 How to Re-run Tests

```bash
cd D:\odoo\odoo18\odoo-load-test

# Single scenario:
docker compose run --rm locust \
  -f /mnt/locust/locustfile.py \
  --host=http://host.docker.internal:8018 \
  --headless \
  --users 50 \
  --spawn-rate 10 \
  --run-time 60s

# Or use web UI:
docker compose up
# Open http://localhost:8089
```

## 📊 View HTML Reports

```powershell
# Windows
start locust\report_50users.html
start locust\report_100users.html
start locust\report_200users.html
```

---
**Date:** 2026-04-18  
**Test Target:** http://localhost:8018/api/reservation/*  
**Result:** ❌ NOT PRODUCTION READY - Requires optimization
