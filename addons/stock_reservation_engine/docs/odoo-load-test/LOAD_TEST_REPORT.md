# Odoo Stock Reservation API - Load Test Report

**Test Date:** April 18, 2026  
**Test Tool:** Locust 2.43.4 (Docker)  
**Target System:** Odoo 18 Stock Reservation Engine  
**API Endpoints Tested:**
- `POST /api/reservation/create` (JSON-RPC)
- `POST /api/reservation/allocate` (JSON-RPC)
- `GET /api/reservation/status/<batch_id>` (HTTP)

**Base URL:** http://localhost:8018  
**Authentication:** Bearer token (`demo-reservation-api-token-change-me`)

---

## Executive Summary

The Stock Reservation API was tested under three concurrency scenarios (50, 100, and 200 concurrent users) to evaluate performance, stability, and breaking points under load.

### Key Findings

| Scenario | Users | Duration | Total Reqs | Failures | Avg Response | RPS  | Status |
|----------|-------|----------|------------|----------|--------------|------|--------|
| **1**    | 50    | 60s      | 473        | 0 (0%)   | 5179ms       | 8.13 | ✅ PASS |
| **2**    | 100   | 60s      | 425        | 50 (11.76%) | 11593ms   | 6.91 | ⚠️ DEGRADED |
| **3**    | 200   | 60s      | 789        | 711 (90.11%) | 10676ms  | 12.81 | ❌ FAIL |

### Critical Issues Identified

1. **Response Timeout Under Load** - At 100+ concurrent users, API returns empty responses (`Expecting value: line 1 column 1`)
2. **Throughput Degradation** - RPS *decreased* from 8.13 (50 users) to 6.91 (100 users) despite double the concurrency
3. **Latency Spike** - Average response time increased from ~5s to ~12s (140% increase) at 100 users
4. **System Breaking Point** - 200 concurrent users caused 90% failure rate; system effectively unusable

---

## Detailed Results

### Scenario 1: Baseline Load (50 Users)

**Configuration:**
- Concurrent Users: 50
- Spawn Rate: 10 users/second
- Duration: 60 seconds

**Results:**
```
Total Requests:     473
Failures:           0 (0.00%)
Average Response:   5179ms
Median Response:    5700ms
95th Percentile:    6700ms
99th Percentile:    7100ms
Max Response:       7617ms
Requests/Second:    8.13
```

**Per-Endpoint Breakdown:**

| Endpoint | Requests | Failures | Avg (ms) | Min (ms) | Max (ms) |
|----------|----------|----------|----------|----------|----------|
| POST /api/reservation/create | 158 | 0 | 5220 | 121 | 7021 |
| POST /api/reservation/allocate | 158 | 0 | 5539 | 112 | 7617 |
| GET /api/reservation/status/<id> | 157 | 0 | 4774 | 102 | 7055 |

**Assessment:** ✅ **STABLE**  
System handles 50 concurrent users with zero failures. Response times are acceptable but already averaging ~5 seconds, indicating potential database or ORM bottlenecks even at baseline load.

---

### Scenario 2: Medium Load (100 Users)

**Configuration:**
- Concurrent Users: 100
- Spawn Rate: 20 users/second
- Duration: 60 seconds

**Results:**
```
Total Requests:     425
Failures:           50 (11.76%)
Average Response:   11593ms
Median Response:    12000ms
95th Percentile:    15000ms
99th Percentile:    15000ms
Max Response:       15616ms
Requests/Second:    6.91
```

**Per-Endpoint Breakdown:**

| Endpoint | Requests | Failures | Fail % | Avg (ms) | Min (ms) | Max (ms) |
|----------|----------|----------|--------|----------|----------|----------|
| POST /api/reservation/create | 211 | 28 | 13.27% | 12145 | 3636 | 15616 |
| POST /api/reservation/allocate | 115 | 20 | 17.39% | 12218 | 1457 | 14978 |
| GET /api/reservation/status/<id> | 99 | 2 | 2.02% | 9691 | 5717 | 13447 |

**Error Distribution:**
```
15 errors: POST create - Parse error (empty response)
13 errors: POST create - Empty result payload
15 errors: POST allocate - Parse error (empty response)
5  errors: POST allocate - Empty result payload
2  errors: GET status - Parse error (empty response)
```

**Assessment:** ⚠️ **DEGRADED**  
- Response time **doubled** (5.2s → 11.6s)
- Throughput **decreased** by 15% despite double the users
- 11.76% of requests failed with parse errors (server timeout/empty response)
- Allocate endpoint most affected (17.39% failure rate)

---

### Scenario 3: High Load Stress Test (200 Users)

**Configuration:**
- Concurrent Users: 200
- Spawn Rate: 40 users/second
- Duration: 60 seconds

**Results:**
```
Total Requests:     789
Failures:           711 (90.11%)
Average Response:   10676ms
Median Response:    6100ms
95th Percentile:    24000ms
99th Percentile:    28000ms
Max Response:       28847ms
Requests/Second:    12.81 (90% failed)
```

**Per-Endpoint Breakdown:**

| Endpoint | Requests | Failures | Fail % | Avg (ms) | Min (ms) | Max (ms) |
|----------|----------|----------|--------|----------|----------|----------|
| POST /api/reservation/create | 704 | 630 | 89.49% | 10410 | 3462 | 28847 |
| POST /api/reservation/allocate | 52 | 48 | 92.31% | 14905 | 4421 | 28644 |
| GET /api/reservation/status/<id> | 33 | 33 | 100.00% | 9700 | 4394 | 22901 |

**Error Distribution:**
```
574 errors: POST create - Parse error (empty response)
56  errors: POST create - Empty result payload
43  errors: POST allocate - Parse error (empty response)
33  errors: GET status - Parse error (empty response)
5   errors: POST allocate - Empty result payload
```

**Assessment:** ❌ **SYSTEM FAILURE**  
- **90% failure rate** - system effectively non-functional
- Status endpoint had **100% failure** - complete unavailability
- Parse errors indicate server unable to send valid responses (timeouts/crashes)
- High variance in response times (median 6s, 99th percentile 28s)

---

## Root Cause Analysis

### 1. Database Locking / Contention
**Evidence:**
- Create and allocate operations write to `stock.reservation.batch`, `stock.reservation.line`, and `stock.move` tables
- Under concurrent load, database row-level locks likely cause serialization
- PostgreSQL lock wait timeouts result in empty responses

**Recommendation:**
- Monitor PostgreSQL logs for `could not obtain lock on row` messages
- Review `stock.reservation.batch` allocation logic for transaction isolation
- Consider optimistic locking or row-level versioning

### 2. Odoo Worker Pool Exhaustion
**Evidence:**
- Throughput *decreased* from 50→100 users (8.13 → 6.91 RPS)
- Indicates worker saturation rather than scaling
- Empty responses suggest request queue overflow or worker timeout

**Recommendation:**
- Check Odoo `--workers` configuration in odoo18.conf
- Increase worker count based on CPU cores (formula: `2 * cores + 1`)
- Monitor worker utilization during load tests

### 3. ORM Overhead & N+1 Queries
**Evidence:**
- 5-second baseline latency with zero load (Scenario 1)
- Status endpoint reads related `line_ids`, `product_id`, `location_id` per batch
- Likely executing multiple queries per reservation line

**Recommendation:**
- Profile SQL queries with `--log-sql` during load test
- Add `.prefetch()` or eager loading for related fields
- Consider caching frequently accessed product/location data

### 4. Missing Request Timeout Handling
**Evidence:**
- "Expecting value: line 1 column 1" = client received HTTP 200 with empty body
- Indicates Odoo returned malformed response or timed out mid-request

**Recommendation:**
- Wrap controller logic in try/except with explicit timeout handling
- Return proper HTTP 503 (Service Unavailable) when overloaded
- Implement request queuing or circuit breaker pattern

---

## Performance Bottlenecks Summary

| Issue | Severity | Impact | Observed At |
|-------|----------|--------|-------------|
| Database row locking | 🔴 Critical | 90% failure @ 200 users | 100+ users |
| Worker pool saturation | 🔴 Critical | Throughput decrease | 100+ users |
| High baseline latency (5s) | 🟡 Medium | Poor UX even at low load | All scenarios |
| ORM N+1 queries | 🟡 Medium | Contributes to latency | All scenarios |
| No graceful degradation | 🔴 Critical | Silent failures | 100+ users |

---

## Recommendations

### Immediate Actions (Before Production)

1. **Increase Odoo Workers**
   ```ini
   # odoo18.conf
   workers = 9  # For 4-core system: (2*4)+1
   max_cron_threads = 2
   ```

2. **Add Database Connection Pooling**
   ```ini
   db_maxconn = 128  # Increase from default 64
   ```

3. **Enable PostgreSQL Query Logging**
   ```bash
   # Monitor for slow queries and locks
   log_min_duration_statement = 1000
   log_lock_waits = on
   ```

4. **Add Controller-Level Timeouts**
   ```python
   # In api.py controllers
   from odoo import http
   from odoo.http import request
   
   @http.route('/api/reservation/create', ...)
   def create_reservation(self, **payload):
       try:
           with request.env.cr.savepoint():
               # Existing logic
               pass
       except Exception as exc:
           return self._json_fail(
               'Request timeout or server overload',
               code='ERR_TIMEOUT'
           )
   ```

### Performance Optimizations

5. **Optimize Status Endpoint Queries**
   ```python
   # Use read() with specific fields instead of browse() + attribute access
   batch_data = batch.read([
       'id', 'name', 'state', 'priority', 'scheduled_date'
   ])[0]
   
   # Batch-fetch line data with single query
   line_data = batch.line_ids.read([
       'product_id', 'requested_qty', 'allocated_qty',
       'location_id', 'lot_id', 'state', 'move_id'
   ])
   ```

6. **Add Response Caching for Status Endpoint**
   ```python
   # Cache GET /api/reservation/status/<id> for 5 seconds
   # Reduces load on frequently polled batches
   ```

7. **Implement Batch Allocation Queue**
   - Move allocation to background job queue (using `queue_job` module)
   - Create endpoint returns `state: 'queued'` immediately
   - Allocate asynchronously with job workers

### Infrastructure

8. **Add Load Balancer with Multiple Odoo Instances**
   - Deploy 2-3 Odoo instances behind Nginx/HAProxy
   - Distribute API load across instances
   - Use sticky sessions for stateful operations

9. **Separate Database for Reservations**
   - Consider dedicated PostgreSQL instance for reservation tables
   - Isolate lock contention from main Odoo database

10. **Add Monitoring & Alerting**
    - Prometheus + Grafana for real-time metrics
    - Alert when response time > 3s or failure rate > 5%
    - Track database connection pool utilization

---

## Load Test Artifacts

The following HTML reports were generated with detailed metrics, charts, and response time distributions:

- [report_50users.html](locust/report_50users.html) - 911 KB
- [report_100users.html](locust/report_100users.html) - 912 KB  
- [report_200users.html](locust/report_200users.html) - 912 KB

**To view reports:**
```bash
# Open in browser from odoo-load-test directory
start locust\report_50users.html
```

---

## Test Environment Details

### System Configuration
- **Odoo Version:** 18.0
- **Python Environment:** .venv (virtualenv)
- **PostgreSQL:** localhost:5432 (user: odoo18, db: odoo18)
- **HTTP Port:** 8018 (configured via odoo18.conf)

### Test Configuration
- **Locust Version:** 2.43.4
- **Docker Image:** locustio/locust:latest
- **Network:** Docker Desktop with host.docker.internal
- **Wait Time:** 1-3 seconds between requests per user

### API Parameters Used
```python
ODOO_API_TOKEN = "demo-reservation-api-token-change-me"
ODOO_PRODUCT_ID = 1  # Storable product variant
ODOO_LOCATION_ID = 8  # Stock location (WH/Stock)
ODOO_QTY = 1.0
```

---

## Conclusion

The Stock Reservation API is **not production-ready** at current scale. While it handles 50 concurrent users acceptably, it degrades significantly at 100 users and becomes unusable at 200 users.

### Recommended Production Limits (Current State)
- **Max Concurrent Users:** 40-50
- **Expected Throughput:** ~8 req/s
- **Response Time SLA:** p95 < 7 seconds

### Target After Optimization
- **Max Concurrent Users:** 200+
- **Expected Throughput:** 30+ req/s
- **Response Time SLA:** p95 < 2 seconds, p99 < 5 seconds

**Next Steps:**
1. Implement immediate recommendations (workers, pooling, timeouts)
2. Re-run load tests to validate improvements
3. Profile SQL queries during 100-user test
4. Consider architectural changes (async allocation queue)
5. Set up continuous performance monitoring

---

**Report Generated:** 2026-04-18 21:52:00  
**Test Engineer:** Sabry Youssef 
**Contact:** Review with development team before production deployment
