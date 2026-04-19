import os
import random

from locust import HttpUser, between, task


class OdooReservationUser(HttpUser):
    wait_time = between(1, 3)

    def _headers(self):
        token = os.getenv("ODOO_API_TOKEN", "")
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def _rpc_payload(self, call_id, params):
        # Odoo type='json' routes expect JSON-RPC envelope.
        return {
            "jsonrpc": "2.0",
            "method": "call",
            "params": params,
            "id": call_id,
        }

    @task
    def reservation_flow(self):
        product_id = int(os.getenv("ODOO_PRODUCT_ID", "1"))
        location_id = int(os.getenv("ODOO_LOCATION_ID", "1"))
        qty = float(os.getenv("ODOO_QTY", "1"))
        headers = self._headers()

        create_payload = self._rpc_payload(
            call_id=random.randint(1, 1000000),
            params={
                "lines": [
                    {
                        "product_id": product_id,
                        "qty": qty,
                        "location_id": location_id,
                    }
                ],
                "auto_confirm": True,
            },
        )

        batch_id = None
        with self.client.post(
            "/api/reservation/create",
            json=create_payload,
            headers=headers,
            name="POST /api/reservation/create",
            catch_response=True,
        ) as response:
            try:
                body = response.json()
                result = body.get("result") or {}
                if result.get("status") != "success":
                    response.failure(f"Create failed: {result}")
                else:
                    batch_id = (result.get("data") or {}).get("batch_id")
                    if not batch_id:
                        response.failure(f"Create success without batch_id: {result}")
            except Exception as exc:
                response.failure(f"Create parse error: {exc}")

        if not batch_id:
            return

        allocate_payload = self._rpc_payload(
            call_id=random.randint(1, 1000000),
            params={"batch_id": batch_id},
        )
        with self.client.post(
            "/api/reservation/allocate",
            json=allocate_payload,
            headers=headers,
            name="POST /api/reservation/allocate",
            catch_response=True,
        ) as response:
            try:
                body = response.json()
                result = body.get("result") or {}
                if result.get("status") != "success":
                    response.failure(f"Allocate failed: {result}")
            except Exception as exc:
                response.failure(f"Allocate parse error: {exc}")

        with self.client.get(
            f"/api/reservation/status/{batch_id}",
            headers=headers,
            name="GET /api/reservation/status/<id>",
            catch_response=True,
        ) as response:
            try:
                body = response.json()
                if response.status_code != 200 or body.get("status") != "success":
                    response.failure(f"Status failed: status={response.status_code}, body={body}")
            except Exception as exc:
                response.failure(f"Status parse error: {exc}")
