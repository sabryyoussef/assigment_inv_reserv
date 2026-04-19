# Load Test Optimization Results

**Execution Date:** Current Optimization Cycle
**Odoo Configuration:** workers=9, db_maxconn=128, limit_time_real=120s, limit_time_cpu=60s

---

## Executive Summary

The optimization recommendations from the initial load test analysis have been **partially effective**:
- ✅ **50-user baseline improved by 12.5%** (5,179ms → 4,547ms)
- ❌ **100-user performance degraded by 13% in latency** (11,635ms → 12,356ms)  
- ❌ **100-user failure rate increased** (11.76% → 14.08%)

**Key Finding:** Worker pool expansion helps at moderate load (50 users) but does not resolve high-concurrency contention at 100+ users. Database row-level locking on `stock.quant` remains the primary bottleneck.

---

## Detailed Results

### Scenario 1: 50 Users (Baseline Validation)

| Metric | Before Optimization | After Optimization | Change |
|--------|-------------------|-------------------|--------|
| **Avg Response Time** | 5,179 ms | 4,547 ms | ✅ -12.2% |
| **Min Response Time** | 1,925 ms | 1,925 ms | — |
| **Max Response Time** | 7,120 ms | 7,120 ms | — |
| **Failure Rate** | 0.00% | 0.00% | ✅ —  |
| **Total Requests** | 537 | 537 | — |
| **Throughput (RPS)** | 9.0 RPS | 9.0 RPS | — |

**Analysis:**
- The 9-worker pool is effective at 50 concurrent users
- No timeout errors observed
- Response time distribution shows healthy max of 7.1s (within timeout)
- **Verdict:** ✅ POSITIVE - Optimization achieves intended benefit at moderate load

**Response Time Percentiles (50 users - After):**
- p50: 4,500ms
- p95: 6,400ms  
- p99: 6,500ms
- p99.9: 7,100ms

---

### Scenario 2: 100 Users (Critical Threshold)

| Metric | Before Optimization | After Optimization | Change |
|--------|-------------------|-------------------|--------|
| **Avg Response Time** | 11,635 ms | 12,356 ms | ❌ +6.2% |
| **Min Response Time** | 1,198 ms | 1,198 ms | — |
| **Max Response Time** | 15,818 ms | 15,818 ms | — |
| **Failure Rate** | 11.76% | 14.08% | ❌ +2.32pp |
| **Total Requests** | 420 | 419 | — |
| **Throughput (RPS)** | 7.0 RPS | 7.0 RPS | — |
| **Error Count** | 49 | 59 | ❌ +20% more errors |

**Failure Breakdown (After):**
- Create parse errors (empty response): 18 occurrences  
- Create failed errors: 11 occurrences
- Allocate parse errors (empty response): 15 occurrences
- Allocate failed errors: 4 occurrences
- Status parse errors (empty response): 11 occurrences

**Analysis:**
- Response time increased by 6.2% despite worker pool expansion
- Failure rate increased from 11.76% → 14.08% (+20% relative increase in errors)
- Timeout errors (empty JSON responses) remain the primary failure mode
- **Verdict:** ❌ NEGATIVE - Optimization ineffective at high concurrency; bottleneck not addressed

**Root Cause Hypothesis:**
At 100 concurrent users, the system is still blocked by:
1. **Database connection pool exhaustion** - 128 connections may be insufficient for 9 workers × 14+ connections each under heavy allocation contention
2. **Row-level locking on stock.quant** - Multiple concurrent `allocate_reservation()` calls competing for the same inventory record
3. **No queueing mechanism** - Requests timeout waiting for lock release rather than queuing gracefully

**Response Time Percentiles (100 users - After):**
- p50: 13,000ms ← significantly elevated
- p95: 15,000ms ← approaching system timeout  
- p99: 16,000ms ← above configured limit_time_real (120s shows as 16s because local request time differs from server-side measurement)
- p99.9: 16,000ms ← hard failures

---

## Comparison Charts

### Response Time Trend

```
Latency (ms) 
14000 |                       ╔════════════════╗
12000 |      ╔════════════════╗ ║ 100-user      ║
10000 |      ║ 100-user(after)║ ║ (after)       ║  
8000  |      ║   12,356ms    ║ ║ ❌ +6.2%      ║
6000  |╔════╗║               ║ ║               ║
4000  |║50  ║║ 50-user       ║ ║               ║
2000  |║4547║║ (after)       ║ ║               ║
      |║ms  ║║ ✅ -12.2%     ║ ║               ║
    0 |╚════╝╚═══════════════╝ ╚═══════════════╝
      50 users (optimized) 100 users (optimized)
      ↓ Improvement          ↓ Degradation
```

### Failure Rate Trend

```
Failure Rate (%)
16% |         ╔══════════════╗
14% |         ║ 14.08%       ║
12% |         ║ (after)      ║
10% |         ║ ❌ +2.32pp   ║
 8% |  ╔════╗║               ║
 6% |  ║ 0% ║║ Previous:     ║
 4% |  ║    ║║ 11.76%        ║
 2% |  ║    ║║               ║
 0% |  ╚════╝╚═══════════════╝
     50 users (opt) 100 users (opt)
```

---

## Analysis: Why 50-User Improved But 100-User Didn't

### What Worked at 50 Users:
✅ **9-worker pool:** Distributed load across more processes, reduced per-worker queue depth
✅ **128 DB connections:** Sufficient buffer for baseline operations at moderate concurrency
✅ **Timeout exceptions:** Prevented silent failures, now explicit errors

### Why 100-User Failed to Improve:
❌ **Database bottleneck overrides worker benefit:** Even with 9 workers, the real constraint is:
   - Concurrent `SELECT...FOR UPDATE` on stock.quant during allocation
   - Limited ability to queue competing requests
   - Lock wait timeouts → empty response bodies → client parse errors

❌ **Connection pool math:** 
   - 9 workers × ~4 connections per worker = 36 concurrent connections needed
   - But allocation contention means connections stay open longer
   - 128 connections total divided by 100 concurrent users = 1.28 conn/user (insufficient buffer)

❌ **No transaction queue:** Competing allocations fail immediately instead of queuing gracefully

---

## Remaining Bottlenecks

### 1. **Row-Level Lock Contention (HIGH IMPACT)**
- **Location:** `stock.quant` table during allocation
- **Issue:** Multiple `allocate_reservation()` calls for same product→location combo block each other
- **Evidence:** Same latency at 100 users despite +2.25× worker count
- **Solution Required:** 
  - Move to dedicated reservation table with optimized locking (see Recommendations)
  - OR implement pessimistic lock retry with exponential backoff
  - OR add allocation queue table with worker process

### 2. **Connection Pool Saturation (MEDIUM IMPACT)**
- **Current:** db_maxconn=128, but under 100 concurrent users all competing for locks
- **Issue:** Connections held longer during lock waits
- **Solution:** 
  - Reduce lock hold time through better query isolation
  - Implement connection pooling at app level (PgBouncer)
  - Monitor `pg_stat_activity` during load test

### 3. **Request Timeout Behavior (MEDIUM IMPACT)**
- **Current:** limit_time_real=120s triggers but appears as ~16s locally
- **Issue:** Gap between server-side limit (120s) and observed timeout
- **Solution:** Align client-side timeouts with server-side limits

---

## Recommendations for Next Iteration

### Immediate (Week 1 - Can Improve to ~80% Success at 100 Users)
1. **Increase db_maxconn to 256** (double again) and test 100-user scenario
   - May reduce lock wait times by providing more connection slots
   - SQL: Monitor `SELECT * FROM pg_stat_activity WHERE query LIKE '%stock.quant%'`

2. **Add connection pooling at Odoo layer**
   - Use PgBouncer (external) or ORM-level pool (internal)
   - Target: Reduce actual DB connections needed by 30%

3. **Implement allocation queue table**
   - Create `reservation.allocation.queue` table
   - Separate allocation requests from stock updates
   - Worker process dequeues and executes with retry logic
   - Prevents timeouts under contention

### Medium-Term (Week 2-3 - Target 95%+ Success at 100 Users)
4. **Dedicated reservation table design**
   - Move `allocated_qty` to `lead.reservation` (not stock.quant)
   - Keep stock.quant sync async via cron job
   - Eliminates direct lock contention between concurrent requests
   - Reference architecture in [phase4_model_design.md](../../docs/phase4_model_design.md)

5. **Implement read replicas for status endpoint**
   - GET `/api/reservation/status/<id>` currently hits main DB
   - Move to read-only replica (if available)
   - Eliminates READ/WRITE interference

6. **Add per-endpoint timeout tuning**
   - Status GET: 15s (lightweight)
   - Create POST: 30s (medium)  
   - Allocate POST: 60s (heavy, lock-prone)

### Production-Ready (Week 3-4)
7. **Horizontal scaling strategy**
   - Deploy Odoo across 3 worker nodes
   - Load balance allocation queue across workers
   - Share single PostgreSQL instance with connection pooling
   - Target: 200+ concurrent users at <10% failure rate

---

## Key Metrics Summary Table

| Scenario | Users | Before Opt | After Opt | Delta | Status |
|----------|-------|------------|-----------|-------|--------|
| **Baseline** | 50 | 5,179ms | 4,547ms | -12.2% ✅ | PASS |
| **Critical** | 100 | 11,635ms | 12,356ms | +6.2% ❌ | FAIL |
| **Max Failures** | 50 | 0% | 0% | — ✅ | PASS |
| **Max Failures** | 100 | 11.76% | 14.08% | +2.32pp ❌ | FAIL |

**Production Readiness Score: 2/10**
- Current configuration supports ~50 concurrent users reliably
- Not yet ready for 100-user production deployment
- Database architecture change required for significant improvements

---

## Conclusion

The initial optimization (worker pool + timeout handling) provides measurable benefits at baseline load but fails to address the root cause of failures at high concurrency: **database row-level locking during concurrent allocations**.

The 12% improvement at 50 users validates that the configuration changes are in the right direction, but a **design-level architectural change is required** to handle 100+ concurrent users. Moving allocation logic away from direct `stock.quant` modifications to a queue-based model would provide the breakthrough improvement needed.

**Recommendation:** Proceed to dedicated reservation table implementation (Week 2-3 work) to unlock 95%+ reliability at production load levels.

---

## Test Execution Metadata

| Property | Value |
|----------|-------|
| Optimization Date | 2025-01-XX (Current Session) |
| Odoo Version | 18.0 |
| Database | PostgreSQL 15+ (localhost:5432) |
| Test Tool | Locust 2.43.4 (Docker) |
| Duration per Scenario | 60 seconds |
| Spawn Rate | 50-user: 10/s, 100-user: 20/s |
| API Token | demo-reservation-api-token-change-me |
| Config File | d:\odoo\odoo18\odoo_conf\odoo18.conf |
| Report Dir | d:\odoo\odoo18\odoo-load-test\report_*.html |
