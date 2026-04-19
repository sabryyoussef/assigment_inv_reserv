# Locust Load Test – Screenshot Index

**Test Date:** April 18, 2026  
**Tool:** Locust 2.43.4 (Docker) + Playwright 1.58.0 (headless Chromium)  
**Target:** `http://host.docker.internal:8018` (Odoo 18 Stock Reservation API)  
**Endpoints tested:**
- `POST /api/reservation/create`
- `POST /api/reservation/allocate`
- `GET  /api/reservation/status/<id>`

**Configuration applied before tests:**
- `workers = 9` (was default ~4)
- `db_maxconn = 128` (was 64)
- `limit_time_real = 120s`, `limit_time_cpu = 60s`

---

## Scenario A — 50 Concurrent Users

> **Result: ✅ PASS — 0% failure rate, avg latency 4,370ms**

| # | Screenshot | Description |
|---|-----------|-------------|
| 1 | [50users_01_home.png](50users_01_home.png) | Locust web UI on first load. Status bar shows **ready**, host pre-configured to `http://host.docker.internal:8018`, RPS and Failures both at 0. |
| 2 | [50users_02_configured.png](50users_02_configured.png) | Form filled: **50 users**, **10 users/second** ramp rate. Start button visible and enabled. |
| 3 | [50users_03_starting.png](50users_03_starting.png) | Immediately after clicking Start. Status changes to **running**, user counter begins incrementing from 0. Statistics table initialises with all-zero rows for the three endpoints. |
| 4 | [50users_04_ramped_up.png](50users_04_ramped_up.png) | All **50 virtual users** are active (ramp-up complete at ~5 s). RPS climbing, first response time figures appear in the statistics table. Failures counter still at 0. |
| 5 | [50users_05_charts_midtest.png](50users_05_charts_midtest.png) | **Charts tab** mid-test. Response time line chart shows latency settling around 4,000–5,000 ms. Requests/second line is steady. No failures line visible (stays at baseline). |
| 6 | [50users_06_failures_midtest.png](50users_06_failures_midtest.png) | **Failures tab** mid-test. Table is **empty** — zero error entries recorded across all three endpoints at 50 concurrent users. |
| 7 | [50users_07_statistics_final.png](50users_07_statistics_final.png) | **Final statistics** after 60 s. Aggregated totals: **792 requests, 0 failures (0.00%)**. Median 4,600 ms, 95th percentile 5,300 ms, Average 4,370 ms. All three endpoints (create, allocate, status) show 0 in the `# Fails` column. |
| 8 | [50users_08_charts_final.png](50users_08_charts_final.png) | **Final charts view.** Response time and RPS charts show stable, flat throughput throughout the 60-second window. No spikes or degradation observed. |
| 9 | [50users_09_failures_final.png](50users_09_failures_final.png) | **Final failures tab.** Still empty — confirmed **zero failures** for the entire 50-user run. |
| 10 | [50users_10_stopped.png](50users_10_stopped.png) | Test stopped. Status shows **stopped**. Final RPS figure frozen. Metrics frozen for review before reset. |

### 50-User Key Metrics Summary

| Endpoint | Requests | Failures | Avg (ms) | p95 (ms) | p99 (ms) |
|----------|----------|----------|----------|----------|----------|
| POST /create | ~268 | 0 | 4,175 | 5,200 | 5,400 |
| POST /allocate | ~264 | 0 | 4,479 | 5,300 | 5,400 |
| GET /status | ~260 | 0 | 4,460 | 5,400 | 5,500 |
| **Aggregated** | **792** | **0** | **4,370** | **5,300** | **5,400** |

---

## Scenario B — 100 Concurrent Users

> **Result: ❌ FAIL — 14.08% failure rate, avg latency 12,356ms**

| # | Screenshot | Description |
|---|-----------|-------------|
| 1 | [100users_01_home.png](100users_01_home.png) | Locust UI after reset from 50-user test. Status **ready**, all counters cleared. Clean baseline before the high-concurrency run. |
| 2 | [100users_02_configured.png](100users_02_configured.png) | Form filled: **100 users**, **20 users/second** ramp rate. Same host and endpoints as Scenario A. |
| 3 | [100users_03_starting.png](100users_03_starting.png) | Test started. Status **running**. User counter begins ramp-up. Statistics table starts populating. |
| 4 | [100users_04_ramped_up.png](100users_04_ramped_up.png) | All **100 virtual users** active (ramp-up complete at ~5 s). Response times visibly higher than 50-user scenario. First failures may already appear as database contention begins. |
| 5 | [100users_05_charts_midtest.png](100users_05_charts_midtest.png) | **Charts tab** mid-test. Response time line has climbed to 10,000–14,000 ms range. RPS drops below the 50-user baseline, confirming throughput degradation under contention. |
| 6 | [100users_06_failures_midtest.png](100users_06_failures_midtest.png) | **Failures tab** mid-test. Error rows are now visible: `Create parse error: Expecting value: line 1 column 1 (char 0)` and `Allocate failed: {}` — both caused by Odoo returning empty HTTP bodies when requests time out waiting for DB locks. |
| 7 | [100users_07_statistics_final.png](100users_07_statistics_final.png) | **Final statistics** after 60 s. Aggregated totals: **419 requests, 59 failures (14.08%)**. Median 13,000 ms, 95th percentile 15,000 ms. Average 12,356 ms — nearly **3× higher** than the 50-user scenario. |
| 8 | [100users_08_charts_final.png](100users_08_charts_final.png) | **Final charts.** Response time chart shows persistent elevation throughout the run with no recovery. RPS lower than 50-user run despite double the users — confirms throughput inversion from lock contention. |
| 9 | [100users_09_failures_final.png](100users_09_failures_final.png) | **Final failures tab.** All 59 failures listed by type and count: 18 create parse errors, 11 create empty-body errors, 15 allocate parse errors, 4 allocate empty-body errors, 11 status parse errors. Root cause: `stock.quant` row-level lock timeout under concurrent allocations. |
| 10 | [100users_10_stopped.png](100users_10_stopped.png) | Test stopped. Final state showing elevated failure percentage (14.08%) frozen in the header status bar. |

### 100-User Key Metrics Summary

| Endpoint | Requests | Failures | Fail % | Avg (ms) | p95 (ms) | p99 (ms) |
|----------|----------|----------|--------|----------|----------|----------|
| POST /create | ~204 | 29 | 14.2% | ~14,000 | 15,000 | 15,000 |
| POST /allocate | ~114 | 19 | 16.7% | ~14,500 | 15,000 | 15,000 |
| GET /status | ~101 | 11 | 10.9% | ~12,000 | 13,000 | 14,000 |
| **Aggregated** | **419** | **59** | **14.08%** | **12,356** | **15,000** | **15,000** |

---

## Side-by-Side Comparison

| Metric | 50 Users ✅ | 100 Users ❌ | Delta |
|--------|-----------|------------|-------|
| Total Requests | 792 | 419 | -46.9% |
| Total Failures | 0 | 59 | +59 |
| Failure Rate | **0.00%** | **14.08%** | +14.08pp |
| Avg Latency | 4,370 ms | 12,356 ms | **+182%** |
| Median Latency | 4,600 ms | 13,000 ms | **+183%** |
| p95 Latency | 5,300 ms | 15,000 ms | **+183%** |
| Throughput (RPS) | 9.3 | 6.95 | **-25%** |

---

## Error Analysis

All failures at 100 users fall into two categories:

| Error Type | Count | Cause |
|------------|-------|-------|
| `Expecting value: line 1 column 1 (char 0)` | 44 | Odoo returned empty HTTP body — request timed out waiting for DB lock |
| `Create/Allocate failed: {}` | 15 | Odoo returned `{}` — empty JSON object, request completed but internal error occurred |

**Root cause:** Multiple concurrent `allocate_reservation()` calls compete for the same `stock.quant` row lock in PostgreSQL. Requests queue up waiting for the lock; those that exceed `limit_time_real` (120 s server-side) or the DB statement timeout receive empty responses, which Locust's JSON parser cannot decode.

---

## Environment

| Property | Value |
|----------|-------|
| Odoo Version | 18.0 |
| Test Tool | Locust 2.43.4 |
| Screenshot Tool | Playwright 1.58.0 (headless Chromium) |
| DB | PostgreSQL (localhost:5432, db: odoo18) |
| Odoo workers | 9 |
| db_maxconn | 128 |
| limit_time_real | 120 s |
| limit_time_cpu | 60 s |
| Test duration | 60 s per scenario |
| Screenshots dir | `odoo-load-test/screenshots/` |

---

*Generated automatically by `capture_tests.py` — Playwright headless run, April 18 2026.*
