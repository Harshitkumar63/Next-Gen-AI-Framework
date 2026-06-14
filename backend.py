"""
=============================================================================
 FASTAPI MOCK BACKEND — Enterprise E-Commerce Simulation
=============================================================================
 Stateful mock API simulating Shopify order management, logistics tracking,
 carrier dispute filing, and payment refund processing.

 Run:  python backend.py
 Docs: http://localhost:8000/docs  (Swagger UI)
=============================================================================
"""

from __future__ import annotations

import logging
import sys
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# ── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(name)-18s │ %(levelname)-5s │ %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("backend")

# ── FastAPI App ──────────────────────────────────────────────────────────────

app = FastAPI(
    title="D2C Operations — Mock Backend",
    description="Simulated enterprise e-commerce APIs for the Autonomous Agent system.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =============================================================================
#  IN-MEMORY DATA STORES
# =============================================================================

# ── Orders Database ──────────────────────────────────────────────────────────
# 6 orders designed to exercise every agent pathway.

ORDERS_DB: dict[str, dict] = {
    "1001": {
        "order_id": "1001",
        "customer_id": "CUST-201",
        "customer_email": "alice.johnson@email.com",
        "items": [
            {"sku": "SKU-A100", "name": "Wireless Earbuds Pro", "qty": 1, "price": 49.99},
        ],
        "total_amount": 49.99,
        "payment_status": "paid",
        "order_date": (datetime.now(tz=timezone.utc) - timedelta(days=5)).isoformat(),
        "shipping_address": "123 Oak Street, Austin, TX 78701",
        "customer_metadata": {
            "total_orders": 12,
            "lifetime_return_rate": 0.05,
            "risk_history_tags": [],
            "account_age_days": 730,
        },
    },
    "1002": {
        "order_id": "1002",
        "customer_id": "CUST-302",
        "customer_email": "bob.serial.returner@email.com",
        "items": [
            {"sku": "SKU-B200", "name": "Smart Watch Ultra", "qty": 1, "price": 89.99},
        ],
        "total_amount": 89.99,
        "payment_status": "paid",
        "order_date": (datetime.now(tz=timezone.utc) - timedelta(days=10)).isoformat(),
        "shipping_address": "456 Elm Ave, Portland, OR 97201",
        "customer_metadata": {
            "total_orders": 25,
            "lifetime_return_rate": 0.45,  # 45% → triggers fraud flag
            "risk_history_tags": ["frequent_returner", "chargeback_2024"],
            "account_age_days": 365,
        },
    },
    "1003": {
        "order_id": "1003",
        "customer_id": "CUST-403",
        "customer_email": "carol.bigspender@email.com",
        "items": [
            {"sku": "SKU-C300", "name": "Noise Cancelling Headphones", "qty": 1, "price": 199.99},
            {"sku": "SKU-C301", "name": "Premium Carrying Case", "qty": 1, "price": 49.99},
        ],
        "total_amount": 249.99,
        "payment_status": "paid",
        "order_date": (datetime.now(tz=timezone.utc) - timedelta(days=3)).isoformat(),
        "shipping_address": "789 Pine Blvd, Seattle, WA 98101",
        "customer_metadata": {
            "total_orders": 8,
            "lifetime_return_rate": 0.12,
            "risk_history_tags": [],
            "account_age_days": 540,
        },
    },
    "1004": {
        "order_id": "1004",
        "customer_id": "CUST-504",
        "customer_email": "dave.missing.delivery@email.com",
        "items": [
            {"sku": "SKU-D400", "name": "Portable Bluetooth Speaker", "qty": 1, "price": 69.99},
        ],
        "total_amount": 69.99,
        "payment_status": "paid",
        "order_date": (datetime.now(tz=timezone.utc) - timedelta(days=7)).isoformat(),
        "shipping_address": "321 Maple Dr, Denver, CO 80201",
        "customer_metadata": {
            "total_orders": 15,
            "lifetime_return_rate": 0.08,
            "risk_history_tags": [],
            "account_age_days": 900,
        },
    },
    "1005": {
        "order_id": "1005",
        "customer_id": "CUST-605",
        "customer_email": "eve.waiting@email.com",
        "items": [
            {"sku": "SKU-E500", "name": "USB-C Hub Adapter", "qty": 2, "price": 34.99},
        ],
        "total_amount": 69.98,
        "payment_status": "paid",
        "order_date": (datetime.now(tz=timezone.utc) - timedelta(days=14)).isoformat(),
        "shipping_address": "654 Cedar Ln, Chicago, IL 60601",
        "customer_metadata": {
            "total_orders": 5,
            "lifetime_return_rate": 0.20,
            "risk_history_tags": [],
            "account_age_days": 180,
        },
    },
    "1006": {
        "order_id": "1006",
        "customer_id": "CUST-706",
        "customer_email": "frank.rto@email.com",
        "items": [
            {"sku": "SKU-F600", "name": "Mechanical Keyboard RGB", "qty": 1, "price": 129.99},
        ],
        "total_amount": 129.99,
        "payment_status": "paid",
        "order_date": (datetime.now(tz=timezone.utc) - timedelta(days=12)).isoformat(),
        "shipping_address": "987 Birch Ct, Miami, FL 33101",
        "customer_metadata": {
            "total_orders": 3,
            "lifetime_return_rate": 0.33,
            "risk_history_tags": ["address_mismatch"],
            "account_age_days": 90,
        },
    },
}

# ── Tracking Database ────────────────────────────────────────────────────────

TRACKING_DB: dict[str, dict] = {
    "TRK-1001": {
        "tracking_id": "TRK-1001",
        "order_id": "1001",
        "carrier": "FedEx",
        "status": "Delivered",
        "estimated_delivery": (datetime.now(tz=timezone.utc) - timedelta(days=2)).isoformat(),
        "actual_delivery": (datetime.now(tz=timezone.utc) - timedelta(days=2)).isoformat(),
        "last_location": "Austin, TX — Front Door",
        "gps_coordinates": "30.2672° N, 97.7431° W",
        "status_history": [
            {"status": "Shipped", "timestamp": (datetime.now(tz=timezone.utc) - timedelta(days=5)).isoformat()},
            {"status": "In-Transit", "timestamp": (datetime.now(tz=timezone.utc) - timedelta(days=3)).isoformat()},
            {"status": "Out for Delivery", "timestamp": (datetime.now(tz=timezone.utc) - timedelta(days=2)).isoformat()},
            {"status": "Delivered", "timestamp": (datetime.now(tz=timezone.utc) - timedelta(days=2)).isoformat()},
        ],
    },
    "TRK-1002": {
        "tracking_id": "TRK-1002",
        "order_id": "1002",
        "carrier": "UPS",
        "status": "Delivered",
        "estimated_delivery": (datetime.now(tz=timezone.utc) - timedelta(days=7)).isoformat(),
        "actual_delivery": (datetime.now(tz=timezone.utc) - timedelta(days=7)).isoformat(),
        "last_location": "Portland, OR — Mailroom",
        "gps_coordinates": "45.5152° N, 122.6784° W",
        "status_history": [
            {"status": "Shipped", "timestamp": (datetime.now(tz=timezone.utc) - timedelta(days=10)).isoformat()},
            {"status": "Delivered", "timestamp": (datetime.now(tz=timezone.utc) - timedelta(days=7)).isoformat()},
        ],
    },
    "TRK-1003": {
        "tracking_id": "TRK-1003",
        "order_id": "1003",
        "carrier": "USPS",
        "status": "In-Transit",
        "estimated_delivery": (datetime.now(tz=timezone.utc) + timedelta(days=2)).isoformat(),
        "actual_delivery": None,
        "last_location": "Distribution Center — Reno, NV",
        "gps_coordinates": None,
        "status_history": [
            {"status": "Shipped", "timestamp": (datetime.now(tz=timezone.utc) - timedelta(days=3)).isoformat()},
            {"status": "In-Transit", "timestamp": (datetime.now(tz=timezone.utc) - timedelta(days=1)).isoformat()},
        ],
    },
    "TRK-1004": {
        "tracking_id": "TRK-1004",
        "order_id": "1004",
        "carrier": "DHL",
        "status": "Delivered",
        "estimated_delivery": (datetime.now(tz=timezone.utc) - timedelta(days=4)).isoformat(),
        "actual_delivery": (datetime.now(tz=timezone.utc) - timedelta(days=4)).isoformat(),
        "last_location": "Denver, CO — Porch",
        "gps_coordinates": "39.7392° N, 104.9903° W",
        "status_history": [
            {"status": "Shipped", "timestamp": (datetime.now(tz=timezone.utc) - timedelta(days=7)).isoformat()},
            {"status": "Delivered", "timestamp": (datetime.now(tz=timezone.utc) - timedelta(days=4)).isoformat()},
        ],
    },
    "TRK-1005": {
        "tracking_id": "TRK-1005",
        "order_id": "1005",
        "carrier": "FedEx",
        "status": "Stuck-Delayed",
        "estimated_delivery": (datetime.now(tz=timezone.utc) - timedelta(days=3)).isoformat(),
        "actual_delivery": None,
        "last_location": "Sorting Facility — Memphis, TN (STUCK)",
        "gps_coordinates": None,
        "status_history": [
            {"status": "Shipped", "timestamp": (datetime.now(tz=timezone.utc) - timedelta(days=14)).isoformat()},
            {"status": "In-Transit", "timestamp": (datetime.now(tz=timezone.utc) - timedelta(days=10)).isoformat()},
            {"status": "Stuck-Delayed", "timestamp": (datetime.now(tz=timezone.utc) - timedelta(days=5)).isoformat()},
        ],
    },
    "TRK-1006": {
        "tracking_id": "TRK-1006",
        "order_id": "1006",
        "carrier": "UPS",
        "status": "RTO",
        "estimated_delivery": (datetime.now(tz=timezone.utc) - timedelta(days=5)).isoformat(),
        "actual_delivery": None,
        "last_location": "Return Facility — Atlanta, GA",
        "gps_coordinates": None,
        "status_history": [
            {"status": "Shipped", "timestamp": (datetime.now(tz=timezone.utc) - timedelta(days=12)).isoformat()},
            {"status": "Out for Delivery", "timestamp": (datetime.now(tz=timezone.utc) - timedelta(days=8)).isoformat()},
            {"status": "Delivery Failed", "timestamp": (datetime.now(tz=timezone.utc) - timedelta(days=8)).isoformat()},
            {"status": "RTO", "timestamp": (datetime.now(tz=timezone.utc) - timedelta(days=5)).isoformat()},
        ],
    },
}

# ── Mutable Logs ─────────────────────────────────────────────────────────────

DISPUTES_LOG: list[dict] = []
REFUNDS_LOG: list[dict] = []


# =============================================================================
#  REQUEST / RESPONSE MODELS
# =============================================================================

class DisputeRequest(BaseModel):
    order_id: str
    tracking_id: str
    reason: str
    customer_complaint_summary: str
    priority: str = "HIGH"


class RefundRequest(BaseModel):
    order_id: str
    customer_id: str
    amount: float
    reason: str
    approved_by: str = "auto_agent"


# =============================================================================
#  API ENDPOINTS
# =============================================================================

@app.get("/health")
async def health_check():
    """Service health check."""
    return {
        "status": "healthy",
        "service": "D2C Mock Backend",
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "data_stats": {
            "orders": len(ORDERS_DB),
            "tracking_entries": len(TRACKING_DB),
            "disputes_filed": len(DISPUTES_LOG),
            "refunds_processed": len(REFUNDS_LOG),
        },
    }


# ── Shopify Order API ────────────────────────────────────────────────────────

@app.get("/api/shopify/order/{order_id}")
async def get_order(order_id: str):
    """
    Returns full order details including customer metadata for risk assessment.
    Simulates Shopify Admin API GET /orders/{id}.json
    """
    order = ORDERS_DB.get(order_id)
    if not order:
        logger.warning(f"[OrderAPI] ❌ Order not found: {order_id}")
        raise HTTPException(status_code=404, detail=f"Order {order_id} not found")

    logger.info(
        f"[OrderAPI] 📦 Fetched order {order_id} "
        f"(customer={order['customer_id']}, amount=${order['total_amount']:.2f})"
    )
    return {"success": True, "order": order}


# ── Logistics Tracking API ───────────────────────────────────────────────────

@app.get("/api/logistics/track/{tracking_id}")
async def track_shipment(tracking_id: str):
    """
    Returns carrier tracking status and delivery history.
    Simulates integration with FedEx/UPS/DHL tracking APIs.
    """
    tracking = TRACKING_DB.get(tracking_id)
    if not tracking:
        # Try matching by order ID → tracking ID format
        alt_id = f"TRK-{tracking_id}"
        tracking = TRACKING_DB.get(alt_id)

    if not tracking:
        logger.warning(f"[TrackingAPI] ❌ Tracking not found: {tracking_id}")
        raise HTTPException(status_code=404, detail=f"Tracking {tracking_id} not found")

    logger.info(
        f"[TrackingAPI] 🚚 Fetched tracking {tracking['tracking_id']} "
        f"(status={tracking['status']}, carrier={tracking['carrier']})"
    )
    return {"success": True, "tracking": tracking}


# ── Carrier Dispute API ──────────────────────────────────────────────────────

@app.post("/api/logistics/dispute")
async def file_dispute(request: DisputeRequest):
    """
    Logs a high-priority carrier dispute requesting GPS coordinates and
    delivery proof. Simulates automated escalation to carrier partners.
    """
    dispute_record = {
        "dispute_id": f"DSP-{uuid.uuid4().hex[:8].upper()}",
        "order_id": request.order_id,
        "tracking_id": request.tracking_id,
        "reason": request.reason,
        "customer_complaint_summary": request.customer_complaint_summary,
        "priority": request.priority,
        "status": "OPENED",
        "gps_requested": True,
        "delivery_photo_requested": True,
        "filed_at": datetime.now(tz=timezone.utc).isoformat(),
        "carrier_response_deadline": (datetime.now(tz=timezone.utc) + timedelta(hours=48)).isoformat(),
    }

    DISPUTES_LOG.append(dispute_record)

    logger.info(
        f"[DisputeAPI] 🚨 Dispute filed: {dispute_record['dispute_id']} "
        f"for order {request.order_id} (priority={request.priority})"
    )
    return {
        "success": True,
        "message": "Carrier dispute filed successfully. GPS coordinates demanded.",
        "dispute": dispute_record,
    }


# ── Refund Processing API ────────────────────────────────────────────────────

@app.post("/api/shopify/refund")
async def process_refund(request: RefundRequest):
    """
    Executes mock payment reversal and updates inventory counts.
    Simulates Shopify Payments refund + inventory adjustment.
    """
    # Validate order exists
    order = ORDERS_DB.get(request.order_id)
    if not order:
        raise HTTPException(status_code=404, detail=f"Order {request.order_id} not found")

    # Validate refund amount
    if request.amount > order["total_amount"]:
        raise HTTPException(
            status_code=400,
            detail=f"Refund amount ${request.amount:.2f} exceeds order total ${order['total_amount']:.2f}",
        )

    refund_record = {
        "refund_id": f"RFN-{uuid.uuid4().hex[:8].upper()}",
        "order_id": request.order_id,
        "customer_id": request.customer_id,
        "amount": request.amount,
        "original_order_total": order["total_amount"],
        "reason": request.reason,
        "approved_by": request.approved_by,
        "payment_reversal_status": "COMPLETED",
        "inventory_restored": True,
        "items_restocked": [item["sku"] for item in order["items"]],
        "processed_at": datetime.now(tz=timezone.utc).isoformat(),
    }

    REFUNDS_LOG.append(refund_record)

    # Update order payment status
    order["payment_status"] = "refunded"

    logger.info(
        f"[RefundAPI] 💰 Refund processed: {refund_record['refund_id']} "
        f"${request.amount:.2f} for order {request.order_id} "
        f"(approved_by={request.approved_by})"
    )
    return {
        "success": True,
        "message": "Refund processed and inventory restored.",
        "refund": refund_record,
    }


# ── Admin / Debug Endpoints ──────────────────────────────────────────────────

@app.get("/api/admin/disputes")
async def get_all_disputes():
    """Returns all filed carrier disputes (for ops dashboard)."""
    return {"success": True, "total": len(DISPUTES_LOG), "disputes": DISPUTES_LOG}


@app.get("/api/admin/refunds")
async def get_all_refunds():
    """Returns all processed refunds (for ops dashboard)."""
    return {"success": True, "total": len(REFUNDS_LOG), "refunds": REFUNDS_LOG}


@app.get("/api/admin/orders")
async def get_all_orders():
    """Returns all orders (for debug)."""
    return {"success": True, "total": len(ORDERS_DB), "orders": list(ORDERS_DB.values())}


# =============================================================================
#  SERVER ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    # Use sys.stdout with UTF-8 to handle emoji on Windows
    sys.stdout.reconfigure(encoding="utf-8")
    print("\n" + "=" * 60)
    print("  [>>] D2C Mock Backend -- Starting on http://localhost:8000")
    print("  [>>] API Docs: http://localhost:8000/docs")
    print("=" * 60 + "\n")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
