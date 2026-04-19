# Stock Reservation Engine — REST API Documentation

## Overview

The Stock Reservation Engine exposes a REST API that allows external systems to create, allocate, and query inventory reservation batches in Odoo.

All endpoints are available under both versioned (`/api/v1/`) and unversioned (`/api/`) base paths.

---

## Authentication

Every request must include a Bearer token in the `Authorization` header.

```
Authorization: Bearer <your-api-token>
```

Tokens are managed in Odoo under **Stock Reservation → API Tokens**. The raw token value is stored as a SHA-256 hash server-side; only active tokens are accepted.

---

## Error Codes

| Code | Meaning |
|---|---|
| `ERR_UNAUTHORIZED` | Missing or invalid token |
| `ERR_FORBIDDEN` | Authenticated but not permitted to perform the action |
| `ERR_VALIDATION` | Invalid or missing request parameters |
| `ERR_NOT_FOUND` | Requested resource does not exist |
| `ERR_INTERNAL` | Unexpected server-side error |

---

## Endpoints

### 1. Create Reservation

Creates a new reservation batch, optionally confirming it immediately.

**Routes**
```
POST /api/reservation/create
POST /api/v1/reservation/create
```

**Request Type:** JSON-RPC (`Content-Type: application/json`)

**Request Body**

| Field | Type | Required | Description |
|---|---|---|---|
| `lines` | array | Yes | One or more reservation line objects (see below) |
| `priority` | string | No | `"0"` Low, `"1"` Normal (default), `"2"` High, `"3"` Urgent |
| `scheduled_date` | string | No | ISO 8601 datetime, e.g. `"2026-04-20T08:00:00"` |
| `auto_confirm` | boolean | No | Confirm the batch immediately (default: `true`) |

**Line Object**

| Field | Type | Required | Description |
|---|---|---|---|
| `product_id` | integer | Yes | Odoo product ID |
| `qty` | float | Yes | Quantity to reserve (must be > 0). Also accepted as `requested_qty` |
| `location_id` | integer | Yes | Odoo stock location ID |
| `lot_id` | integer | No | Serial/lot number ID |

**Example Request**
```json
{
  "jsonrpc": "2.0",
  "method": "call",
  "params": {
    "lines": [
      {
        "product_id": 42,
        "qty": 10.0,
        "location_id": 8,
        "lot_id": null
      }
    ],
    "priority": "2",
    "scheduled_date": "2026-04-25T09:00:00",
    "auto_confirm": true
  }
}
```

**Success Response**
```json
{
  "jsonrpc": "2.0",
  "result": {
    "status": "success",
    "data": {
      "batch_id": 17,
      "name": "RES/2026/0017",
      "state": "confirmed"
    }
  }
}
```

**Error Response**
```json
{
  "jsonrpc": "2.0",
  "result": {
    "status": "error",
    "message": "At least one line is required.",
    "code": "ERR_VALIDATION"
  }
}
```

---

### 2. Allocate Reservation

Triggers stock allocation for an existing confirmed reservation batch.

**Routes**
```
POST /api/reservation/allocate
POST /api/v1/reservation/allocate
```

**Request Type:** JSON-RPC (`Content-Type: application/json`)

**Request Body**

| Field | Type | Required | Description |
|---|---|---|---|
| `batch_id` | integer | Yes | ID of the reservation batch to allocate |

**Example Request**
```json
{
  "jsonrpc": "2.0",
  "method": "call",
  "params": {
    "batch_id": 17
  }
}
```

**Success Response**
```json
{
  "jsonrpc": "2.0",
  "result": {
    "status": "success",
    "data": {
      "batch_id": 17,
      "name": "RES/2026/0017",
      "state": "allocated"
    }
  }
}
```

**Access Rules**
- The authenticated user must be either the batch owner (`request_user_id`) or a member of the **Stock Reservation Manager** group.

---

### 3. Get Reservation Status

Retrieves the current status and line details of a reservation batch.

**Routes**
```
GET /api/reservation/status/{batch_id}
GET /api/v1/reservation/status/{batch_id}
```

**Request Type:** HTTP GET

**Path Parameters**

| Parameter | Type | Description |
|---|---|---|
| `batch_id` | integer | ID of the reservation batch |

**Example Request**
```
GET /api/v1/reservation/status/17
Authorization: Bearer <token>
```

**Success Response** (`200 OK`)
```json
{
  "status": "success",
  "data": {
    "batch_id": 17,
    "name": "RES/2026/0017",
    "state": "allocated",
    "priority": "2",
    "scheduled_date": "2026-04-25T09:00:00",
    "lines": [
      {
        "line_id": 34,
        "product_id": 42,
        "product_name": "[PROD-001] Widget A",
        "requested_qty": 10.0,
        "allocated_qty": 10.0,
        "location_id": 8,
        "location_name": "WH/Stock",
        "lot_id": false,
        "lot_name": false,
        "state": "allocated",
        "move_id": 91
      }
    ]
  }
}
```

**Error Responses**

| HTTP Status | code | Condition |
|---|---|---|
| `401` | `ERR_UNAUTHORIZED` | Missing or invalid token |
| `403` | `ERR_FORBIDDEN` | User is not the batch owner or a manager |
| `404` | `ERR_NOT_FOUND` | Batch does not exist |

**Access Rules**
- Same as Allocate: batch owner or **Stock Reservation Manager** group required.

---

## Batch States

| State | Description |
|---|---|
| `draft` | Batch created but not yet confirmed |
| `confirmed` | Confirmed and waiting for allocation |
| `partial` | Some lines allocated, others pending |
| `allocated` | All lines fully allocated |
| `done` | Reservation marked as complete |
| `cancelled` | Reservation cancelled; associated transfers also cancelled |

---

## Priority Values

| Value | Label |
|---|---|
| `"0"` | Low |
| `"1"` | Normal (default) |
| `"2"` | High |
| `"3"` | Urgent |
