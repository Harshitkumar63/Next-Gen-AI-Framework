"""
=============================================================================
 LANGGRAPH MULTI-AGENT ENGINE — Autonomous D2C Resolution System
=============================================================================
 Stateful, cyclic agent graph with 4 specialized nodes + HITL gate:
   1. Triage & Intent Orchestrator
   2. Logistics Investigator
   3. Fraud & Risk Agent
   4. Financial Adjuster & Communication Engine
   + Human-in-the-Loop Approval Gate

 Uses LangGraph's interrupt() / Command() for HITL pause/resume.
 Uses Annotated[list, operator.add] reducers for accumulating trace logs.
=============================================================================
"""

from __future__ import annotations

import logging
import operator
import re
from datetime import datetime, timezone
from typing import Annotated, TypedDict, Literal, Optional

import httpx
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt, Command

from policy_engine import lookup_company_policy

# ── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(name)-18s │ %(levelname)-5s │ %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("agents")

# ── Configuration ────────────────────────────────────────────────────────────

BACKEND_BASE_URL = "http://localhost:8000"

# =============================================================================
#  AGENT STATE DEFINITION
# =============================================================================


class AgentState(TypedDict):
    """
    Central state object shared across all agent nodes.
    Uses Annotated reducers for list fields to accumulate rather than overwrite.
    """

    # ── Customer / Order Identity ─────────────────────────────────────────
    customer_id: str
    order_id: str
    tracking_id: str
    customer_email: str
    channel: str  # "Email" | "WhatsApp" | "Web"

    # ── Complaint & Classification ────────────────────────────────────────
    original_complaint: str
    customer_sentiment: str  # "angry" | "frustrated" | "neutral" | "polite"
    issue_type: str  # classified issue category

    # ── Risk Assessment ───────────────────────────────────────────────────
    risk_score: str  # "LOW" | "MEDIUM" | "HIGH"
    risk_reasons: list[str]

    # ── HITL Control ──────────────────────────────────────────────────────
    approval_required: bool
    approval_status: str  # "not_required" | "pending" | "approved" | "rejected"

    # ── Fetched Data ──────────────────────────────────────────────────────
    order_details: dict
    tracking_details: dict
    policy: dict

    # ── Financial ─────────────────────────────────────────────────────────
    refund_amount: float
    dispute_filed: bool

    # ── Trace / Audit Logs (ACCUMULATING — uses operator.add reducer) ─────
    steps_taken: Annotated[list[str], operator.add]
    internal_notes: Annotated[list[str], operator.add]

    # ── Output ────────────────────────────────────────────────────────────
    final_draft_response: str
    error: str


# =============================================================================
#  HELPER UTILITIES
# =============================================================================


def _api_get(path: str) -> dict:
    """Synchronous GET to the mock backend."""
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(f"{BACKEND_BASE_URL}{path}")
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as e:
        logger.error(f"[API] HTTP {e.response.status_code} for {path}")
        return {"success": False, "error": str(e)}
    except httpx.ConnectError:
        logger.error(f"[API] Connection refused — is backend.py running on {BACKEND_BASE_URL}?")
        return {"success": False, "error": "Backend connection refused"}


def _api_post(path: str, data: dict) -> dict:
    """Synchronous POST to the mock backend."""
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(f"{BACKEND_BASE_URL}{path}", json=data)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as e:
        logger.error(f"[API] HTTP {e.response.status_code} for {path}")
        return {"success": False, "error": str(e)}
    except httpx.ConnectError:
        logger.error(f"[API] Connection refused — is backend.py running on {BACKEND_BASE_URL}?")
        return {"success": False, "error": "Backend connection refused"}


def _timestamp() -> str:
    """ISO timestamp for trace log entries."""
    return datetime.now(tz=timezone.utc).strftime("%H:%M:%S")


# =============================================================================
#  NODE 1: TRIAGE & INTENT ORCHESTRATOR
# =============================================================================


def triage_node(state: AgentState) -> dict:
    """
    Omnichannel ingestion node. Parses raw customer complaint, extracts entities
    (order ID, tracking ID), classifies sentiment and issue type, fetches company
    policy, and determines which agent should handle next.

    Thought Process:
      1. Extract order/tracking IDs via regex
      2. Classify sentiment from keyword analysis
      3. Determine issue category
      4. Fetch applicable company policy
      5. Pull order details from Shopify API
      6. Route to appropriate downstream agent
    """
    complaint = state.get("original_complaint", "")
    channel = state.get("channel", "Web")

    logger.info(f"[Triage] 🎯 Processing new ticket via {channel}")
    logger.info(f"[Triage] 📝 Complaint: {complaint[:100]}...")

    # ── Step 1: Entity Extraction ─────────────────────────────────────────
    # Extract order ID (e.g., #1004, order 1004, order #1004)
    order_match = re.search(r"#?(\d{4,})", complaint)
    order_id = order_match.group(1) if order_match else state.get("order_id", "")

    # Derive tracking ID from order ID
    tracking_id = f"TRK-{order_id}" if order_id else state.get("tracking_id", "")

    # ── Step 2: Sentiment Classification ──────────────────────────────────
    complaint_lower = complaint.lower()

    angry_keywords = [
        "furious", "angry", "unacceptable", "terrible", "worst",
        "scam", "fraud", "sue", "lawyer", "disgusting", "immediately",
        "demand", "ridiculous", "outrageous", "incompetent", "!!",
        "money back", "refund now", "never again",
    ]
    frustrated_keywords = [
        "frustrated", "disappointed", "annoyed", "upset", "unhappy",
        "waited", "still waiting", "not happy", "let down", "again",
    ]

    angry_count = sum(1 for kw in angry_keywords if kw in complaint_lower)
    frustrated_count = sum(1 for kw in frustrated_keywords if kw in complaint_lower)

    if angry_count >= 2 or "!" in complaint and angry_count >= 1:
        sentiment = "angry"
    elif frustrated_count >= 1 or angry_count == 1:
        sentiment = "frustrated"
    elif any(w in complaint_lower for w in ["please", "thank", "appreciate", "kindly"]):
        sentiment = "polite"
    else:
        sentiment = "neutral"

    # ── Step 3: Issue Classification ──────────────────────────────────────
    delivery_keywords = [
        "not received", "never received", "didn't receive", "haven't received",
        "where is", "missing", "lost", "delivered but", "says delivered",
        "not delivered", "no delivery",
    ]
    delay_keywords = ["delayed", "late", "stuck", "waiting", "slow", "taking too long"]
    refund_keywords = ["refund", "money back", "reimburse", "return", "cancel"]
    damage_keywords = ["damaged", "broken", "defective", "not working", "cracked"]
    wrong_keywords = ["wrong item", "wrong product", "not what I ordered", "different"]

    if any(kw in complaint_lower for kw in delivery_keywords):
        issue_type = "delivery_not_received"
    elif any(kw in complaint_lower for kw in delay_keywords):
        issue_type = "late_delivery"
    elif any(kw in complaint_lower for kw in damage_keywords):
        issue_type = "damaged_item"
    elif any(kw in complaint_lower for kw in wrong_keywords):
        issue_type = "wrong_item"
    elif any(kw in complaint_lower for kw in refund_keywords):
        issue_type = "return_request"
    else:
        issue_type = "general_inquiry"

    # ── Step 4: Policy Lookup ─────────────────────────────────────────────
    policy = lookup_company_policy(issue_type)

    # ── Step 5: Fetch Order Details ───────────────────────────────────────
    order_details = {}
    customer_id = ""
    customer_email = ""

    if order_id:
        api_result = _api_get(f"/api/shopify/order/{order_id}")
        if api_result.get("success"):
            order_details = api_result["order"]
            customer_id = order_details.get("customer_id", "")
            customer_email = order_details.get("customer_email", "")
            logger.info(f"[Triage] ✅ Order {order_id} fetched — customer={customer_id}")
        else:
            logger.warning(f"[Triage] ⚠️ Could not fetch order {order_id}")

    # ── Build trace log ───────────────────────────────────────────────────
    steps = [
        f"[{_timestamp()}] 🎯 TRIAGE: New ticket received via {channel}",
        f"[{_timestamp()}] 🔍 TRIAGE: Extracted order_id={order_id}, tracking_id={tracking_id}",
        f"[{_timestamp()}] 😤 TRIAGE: Sentiment classified as '{sentiment}' (angry_kw={angry_count}, frustrated_kw={frustrated_count})",
        f"[{_timestamp()}] 📋 TRIAGE: Issue classified as '{issue_type}'",
        f"[{_timestamp()}] 📖 TRIAGE: Policy loaded — '{policy.get('policy_name', 'N/A')}'",
    ]

    if order_details:
        meta = order_details.get("customer_metadata", {})
        steps.append(
            f"[{_timestamp()}] 📦 TRIAGE: Order fetched — ${order_details.get('total_amount', 0):.2f}, "
            f"return_rate={meta.get('lifetime_return_rate', 0):.0%}, "
            f"total_orders={meta.get('total_orders', 0)}"
        )

    notes = [
        f"Triage completed. Issue='{issue_type}', Sentiment='{sentiment}'. "
        f"Routing to {'logistics' if issue_type in ('delivery_not_received', 'late_delivery') else 'fraud_risk' if issue_type in ('return_request', 'damaged_item', 'wrong_item') else 'financial_adjuster'}."
    ]

    logger.info(f"[Triage] ✅ Classification complete — issue={issue_type}, sentiment={sentiment}")

    return {
        "customer_id": customer_id or state.get("customer_id", "UNKNOWN"),
        "order_id": order_id,
        "tracking_id": tracking_id,
        "customer_email": customer_email or state.get("customer_email", ""),
        "channel": channel,
        "customer_sentiment": sentiment,
        "issue_type": issue_type,
        "order_details": order_details,
        "policy": policy,
        "steps_taken": steps,
        "internal_notes": notes,
    }


# =============================================================================
#  NODE 2: LOGISTICS INVESTIGATOR
# =============================================================================


def logistics_node(state: AgentState) -> dict:
    """
    Courier escalation agent. Queries carrier tracking APIs, detects delivery
    anomalies, and automatically files carrier disputes when warranted.

    Thought Process:
      1. Fetch tracking data from carrier API
      2. Compare tracking status against customer claim
      3. If anomaly detected (delivered vs. not received) → auto-file dispute
      4. Log investigation findings
    """
    tracking_id = state.get("tracking_id", "")
    order_id = state.get("order_id", "")
    issue_type = state.get("issue_type", "")
    complaint = state.get("original_complaint", "")

    logger.info(f"[Logistics] 🚚 Investigating tracking {tracking_id}")

    steps = [f"[{_timestamp()}] 🚚 LOGISTICS: Starting carrier investigation for {tracking_id}"]
    notes = []
    tracking_details = {}
    dispute_filed = False

    # ── Fetch Tracking Data ───────────────────────────────────────────────
    if tracking_id:
        api_result = _api_get(f"/api/logistics/track/{tracking_id}")
        if api_result.get("success"):
            tracking_details = api_result["tracking"]
            carrier_status = tracking_details.get("status", "Unknown")
            carrier = tracking_details.get("carrier", "Unknown")
            last_location = tracking_details.get("last_location", "Unknown")

            steps.append(
                f"[{_timestamp()}] 📡 LOGISTICS: Carrier={carrier}, Status='{carrier_status}', "
                f"Last Location='{last_location}'"
            )

            # ── Anomaly Detection ─────────────────────────────────────────
            # CASE 1: Delivered but customer says not received
            if carrier_status == "Delivered" and issue_type == "delivery_not_received":
                logger.warning(
                    f"[Logistics] ⚠️ ANOMALY: Tracking says Delivered but customer "
                    f"reports not received — filing carrier dispute!"
                )
                steps.append(
                    f"[{_timestamp()}] 🚨 LOGISTICS: ANOMALY DETECTED — Tracking shows "
                    f"'Delivered' but customer claims NOT received!"
                )
                steps.append(
                    f"[{_timestamp()}] 📋 LOGISTICS: Auto-filing carrier dispute "
                    f"demanding GPS coordinates and delivery proof..."
                )

                # Auto-file dispute
                dispute_result = _api_post("/api/logistics/dispute", {
                    "order_id": order_id,
                    "tracking_id": tracking_id,
                    "reason": "Delivery anomaly — customer reports not received, tracking shows Delivered",
                    "customer_complaint_summary": complaint[:200],
                    "priority": "HIGH",
                })

                if dispute_result.get("success"):
                    dispute_id = dispute_result["dispute"]["dispute_id"]
                    steps.append(
                        f"[{_timestamp()}] ✅ LOGISTICS: Dispute {dispute_id} filed successfully! "
                        f"GPS coordinates requested from {carrier}."
                    )
                    notes.append(
                        f"Carrier dispute {dispute_id} auto-filed. Demanding GPS proof from {carrier}. "
                        f"Response deadline: 48 hours."
                    )
                    dispute_filed = True
                else:
                    steps.append(
                        f"[{_timestamp()}] ❌ LOGISTICS: Failed to file dispute — "
                        f"{dispute_result.get('error', 'Unknown error')}"
                    )

            # CASE 2: Stuck/Delayed
            elif carrier_status == "Stuck-Delayed":
                logger.info(f"[Logistics] ⏳ Package stuck in transit")
                steps.append(
                    f"[{_timestamp()}] ⏳ LOGISTICS: Package STUCK at '{last_location}'. "
                    f"Delay confirmed by carrier {carrier}."
                )
                notes.append(
                    f"Package stuck at {last_location}. Carrier {carrier} confirms delay. "
                    f"Recommend shipping credit per late_delivery policy."
                )

            # CASE 3: RTO (Return to Origin)
            elif carrier_status == "RTO":
                logger.info(f"[Logistics] 🔄 Package RTO — returning to warehouse")
                steps.append(
                    f"[{_timestamp()}] 🔄 LOGISTICS: Package has been RETURNED TO ORIGIN. "
                    f"Currently at '{last_location}'."
                )
                notes.append(
                    f"Package RTO'd. Currently at {last_location}. Customer needs reship or refund."
                )

            # CASE 4: In-Transit (normal)
            elif carrier_status == "In-Transit":
                est = tracking_details.get("estimated_delivery", "Unknown")
                steps.append(
                    f"[{_timestamp()}] 📦 LOGISTICS: Package in transit. "
                    f"ETA: {est}. No anomaly detected."
                )
                notes.append(f"Package in transit normally. ETA: {est}.")

            # CASE 5: Already delivered, no complaint mismatch
            else:
                steps.append(
                    f"[{_timestamp()}] ✅ LOGISTICS: Status='{carrier_status}'. "
                    f"No anomaly detected."
                )

        else:
            steps.append(
                f"[{_timestamp()}] ❌ LOGISTICS: Could not retrieve tracking data for {tracking_id}"
            )
            notes.append(f"Tracking lookup failed for {tracking_id}.")
    else:
        steps.append(f"[{_timestamp()}] ⚠️ LOGISTICS: No tracking ID available — skipping investigation")

    steps.append(f"[{_timestamp()}] ✅ LOGISTICS: Investigation complete. Proceeding to risk assessment.")

    return {
        "tracking_details": tracking_details,
        "dispute_filed": dispute_filed,
        "steps_taken": steps,
        "internal_notes": notes,
    }


# =============================================================================
#  NODE 3: FRAUD & RISK AGENT
# =============================================================================


def fraud_risk_node(state: AgentState) -> dict:
    """
    Predictive risk engine. Evaluates historical customer data against company
    policy thresholds to determine fraud/abuse risk level.

    Risk Logic:
      - lifetime_return_rate > 40% → HIGH RISK
      - order total_amount > policy auto_refund_limit → HIGH RISK
      - Both conditions → HIGH RISK (multiple flags)
      - Neither → LOW RISK

    If HIGH RISK → sets approval_required=True to trigger HITL gate.
    """
    order_details = state.get("order_details", {})
    policy = state.get("policy", {})
    issue_type = state.get("issue_type", "")

    logger.info(f"[FraudRisk] 🔍 Evaluating risk for order {state.get('order_id', '?')}")

    steps = [f"[{_timestamp()}] 🛡️ FRAUD: Starting risk assessment"]
    notes = []
    risk_reasons: list[str] = []

    # Extract customer metrics
    customer_meta = order_details.get("customer_metadata", {})
    return_rate = customer_meta.get("lifetime_return_rate", 0.0)
    total_orders = customer_meta.get("total_orders", 0)
    risk_tags = customer_meta.get("risk_history_tags", [])
    order_amount = order_details.get("total_amount", 0.0)

    # Extract policy thresholds
    risk_threshold = policy.get("risk_threshold_return_rate", 0.40)
    auto_refund_limit = policy.get("auto_refund_limit", 75.00)

    steps.append(
        f"[{_timestamp()}] 📊 FRAUD: Customer metrics — return_rate={return_rate:.0%}, "
        f"total_orders={total_orders}, order_amount=${order_amount:.2f}, "
        f"history_tags={risk_tags}"
    )
    steps.append(
        f"[{_timestamp()}] 📖 FRAUD: Policy thresholds — risk_threshold={risk_threshold:.0%}, "
        f"auto_refund_limit=${auto_refund_limit:.2f}"
    )

    # ── Risk Evaluation ───────────────────────────────────────────────────

    # Check 1: High return rate
    if risk_threshold and return_rate > risk_threshold:
        risk_reasons.append(
            f"Lifetime return rate ({return_rate:.0%}) exceeds threshold ({risk_threshold:.0%})"
        )
        steps.append(
            f"[{_timestamp()}] 🚩 FRAUD: FLAG — Return rate {return_rate:.0%} > {risk_threshold:.0%} threshold"
        )

    # Check 2: Order amount exceeds auto-refund limit
    if order_amount > auto_refund_limit:
        risk_reasons.append(
            f"Order amount (${order_amount:.2f}) exceeds auto-refund limit (${auto_refund_limit:.2f})"
        )
        steps.append(
            f"[{_timestamp()}] 🚩 FRAUD: FLAG — Order ${order_amount:.2f} > ${auto_refund_limit:.2f} auto-refund cap"
        )

    # Check 3: Historical risk tags
    if risk_tags:
        risk_reasons.append(f"Historical risk tags: {', '.join(risk_tags)}")
        steps.append(
            f"[{_timestamp()}] 🚩 FRAUD: FLAG — Risk history tags found: {risk_tags}"
        )

    # ── Determine Risk Level ──────────────────────────────────────────────
    if len(risk_reasons) >= 2:
        risk_score = "HIGH"
    elif len(risk_reasons) == 1:
        risk_score = "HIGH"
    else:
        risk_score = "LOW"

    approval_required = risk_score == "HIGH"

    if approval_required:
        approval_status = "pending"
        steps.append(
            f"[{_timestamp()}] 🔴 FRAUD: RISK SCORE = {risk_score} — "
            f"HITL approval REQUIRED. Auto-refund BLOCKED."
        )
        notes.append(
            f"HIGH RISK flagged. Reasons: {'; '.join(risk_reasons)}. "
            f"Routing to human approval gate."
        )
    else:
        approval_status = "not_required"
        steps.append(
            f"[{_timestamp()}] 🟢 FRAUD: RISK SCORE = {risk_score} — "
            f"No risk flags. Auto-processing permitted."
        )
        notes.append("Low risk. No approval needed. Proceeding to financial adjustment.")

    logger.info(
        f"[FraudRisk] {'🔴' if approval_required else '🟢'} "
        f"Risk={risk_score}, Reasons={len(risk_reasons)}, HITL={'YES' if approval_required else 'NO'}"
    )

    return {
        "risk_score": risk_score,
        "risk_reasons": risk_reasons,
        "approval_required": approval_required,
        "approval_status": approval_status,
        "steps_taken": steps,
        "internal_notes": notes,
    }


# =============================================================================
#  NODE 4: HITL APPROVAL GATE
# =============================================================================


def hitl_approval_node(state: AgentState) -> dict:
    """
    Human-in-the-Loop guardrail. Pauses graph execution using LangGraph's
    interrupt() mechanism. The Streamlit ops panel provides approve/reject.

    When this node executes:
      1. Surfaces a summary of the case for the human reviewer
      2. Calls interrupt() to PAUSE the graph
      3. Resumes when Command(resume=...) is called from the frontend
      4. Returns the human's decision as approval_status
    """
    order_id = state.get("order_id", "?")
    risk_score = state.get("risk_score", "?")
    risk_reasons = state.get("risk_reasons", [])

    logger.info(f"[HITL] ⏸️ Pausing graph — awaiting human approval for order {order_id}")

    steps = [
        f"[{_timestamp()}] ⏸️ HITL: Execution PAUSED — awaiting manager approval",
        f"[{_timestamp()}] 📋 HITL: Risk={risk_score}, Reasons: {'; '.join(risk_reasons)}",
    ]

    # Build the approval request payload surfaced to the human
    approval_request = {
        "order_id": order_id,
        "customer_id": state.get("customer_id", "?"),
        "risk_score": risk_score,
        "risk_reasons": risk_reasons,
        "order_amount": state.get("order_details", {}).get("total_amount", 0),
        "issue_type": state.get("issue_type", "?"),
        "dispute_filed": state.get("dispute_filed", False),
        "recommended_action": "refund" if state.get("issue_type") != "general_inquiry" else "info_only",
    }

    # ── INTERRUPT: Graph pauses here ──────────────────────────────────────
    # The `interrupt()` call halts execution. The value passed is surfaced
    # to the calling application. When Command(resume=...) is called, the
    # interrupt returns that resume value.
    human_decision = interrupt(approval_request)

    # ── Graph resumes here after human input ──────────────────────────────
    decision = human_decision if isinstance(human_decision, str) else "rejected"

    logger.info(f"[HITL] ▶️ Graph resumed — decision: {decision}")

    resume_steps = [
        f"[{_timestamp()}] ▶️ HITL: Manager decision received: '{decision.upper()}'",
    ]

    if decision == "approved":
        resume_steps.append(
            f"[{_timestamp()}] ✅ HITL: Action APPROVED — proceeding to financial processing"
        )
    else:
        resume_steps.append(
            f"[{_timestamp()}] ❌ HITL: Action REJECTED — generating rejection notice"
        )

    return {
        "approval_status": decision,
        "steps_taken": steps + resume_steps,
        "internal_notes": [f"HITL decision: {decision} for order {order_id}"],
    }


# =============================================================================
#  NODE 5: FINANCIAL ADJUSTER & COMMUNICATION ENGINE
# =============================================================================


def financial_adjuster_node(state: AgentState) -> dict:
    """
    Handles conditional refund processing, inventory hooks, and generates
    empathetic, dynamic, context-aware customer responses.

    Thought Process:
      1. Check approval status — if rejected, draft rejection response
      2. Calculate refund amount based on policy limits
      3. Process refund via payment API
      4. Generate customer response tailored to sentiment + channel
    """
    order_id = state.get("order_id", "")
    issue_type = state.get("issue_type", "")
    sentiment = state.get("customer_sentiment", "neutral")
    channel = state.get("channel", "Email")
    approval_status = state.get("approval_status", "not_required")
    risk_score = state.get("risk_score", "LOW")
    policy = state.get("policy", {})
    order_details = state.get("order_details", {})
    dispute_filed = state.get("dispute_filed", False)

    order_amount = order_details.get("total_amount", 0.0)
    customer_id = state.get("customer_id", "")
    auto_refund_limit = policy.get("auto_refund_limit", 75.00)
    items = order_details.get("items", [])
    item_names = ", ".join(i.get("name", "item") for i in items) if items else "your order"

    logger.info(f"[Financial] 💰 Processing order {order_id} (approval={approval_status})")

    steps = [f"[{_timestamp()}] 💰 FINANCIAL: Starting financial processing for order {order_id}"]
    notes = []
    refund_amount = 0.0

    # ── Handle Rejection ──────────────────────────────────────────────────
    if approval_status == "rejected":
        steps.append(f"[{_timestamp()}] ❌ FINANCIAL: Refund REJECTED by manager — drafting rejection notice")
        response = _generate_response(
            template="rejection",
            sentiment=sentiment,
            channel=channel,
            order_id=order_id,
            item_names=item_names,
            issue_type=issue_type,
        )
        steps.append(f"[{_timestamp()}] 📧 FINANCIAL: Rejection response drafted for {channel}")
        notes.append("Refund rejected by manager. Rejection notice sent to customer.")

        return {
            "refund_amount": 0.0,
            "final_draft_response": response,
            "steps_taken": steps,
            "internal_notes": notes,
        }

    # ── Calculate Refund ──────────────────────────────────────────────────
    should_refund = issue_type in (
        "delivery_not_received", "damaged_item", "wrong_item", "return_request"
    )

    if should_refund:
        if risk_score == "LOW":
            # Auto-refund within policy limits
            refund_amount = min(order_amount, auto_refund_limit)
            steps.append(
                f"[{_timestamp()}] 💳 FINANCIAL: Auto-refund calculated — "
                f"${refund_amount:.2f} (capped at policy limit ${auto_refund_limit:.2f})"
            )
        else:
            # Approved by manager — full refund allowed
            refund_amount = order_amount
            steps.append(
                f"[{_timestamp()}] 💳 FINANCIAL: Manager-approved refund — "
                f"${refund_amount:.2f} (full order amount)"
            )

        # Process refund via API
        refund_result = _api_post("/api/shopify/refund", {
            "order_id": order_id,
            "customer_id": customer_id,
            "amount": refund_amount,
            "reason": f"Agent resolution: {issue_type}",
            "approved_by": "manager" if approval_status == "approved" else "auto_agent",
        })

        if refund_result.get("success"):
            refund_id = refund_result["refund"]["refund_id"]
            steps.append(
                f"[{_timestamp()}] ✅ FINANCIAL: Refund {refund_id} processed — "
                f"${refund_amount:.2f} returned to customer"
            )
            steps.append(f"[{_timestamp()}] 📦 FINANCIAL: Inventory restored for {item_names}")
            notes.append(f"Refund {refund_id} processed: ${refund_amount:.2f}. Inventory restored.")
        else:
            steps.append(
                f"[{_timestamp()}] ❌ FINANCIAL: Refund processing failed — "
                f"{refund_result.get('error', 'Unknown error')}"
            )
            notes.append("Refund processing failed. Manual intervention needed.")

    elif issue_type == "late_delivery":
        # Shipping credit instead of refund
        refund_amount = min(25.00, auto_refund_limit)
        steps.append(
            f"[{_timestamp()}] 🎁 FINANCIAL: Shipping credit of ${refund_amount:.2f} applied per policy"
        )
        notes.append(f"Shipping credit of ${refund_amount:.2f} applied for late delivery.")

    else:
        steps.append(f"[{_timestamp()}] ℹ️ FINANCIAL: No financial action needed for '{issue_type}'")

    # ── Generate Customer Response ────────────────────────────────────────
    if should_refund and refund_amount > 0:
        template = "refund"
    elif issue_type == "late_delivery":
        template = "delay"
    elif dispute_filed:
        template = "investigation"
    else:
        template = "general"

    response = _generate_response(
        template=template,
        sentiment=sentiment,
        channel=channel,
        order_id=order_id,
        item_names=item_names,
        issue_type=issue_type,
        refund_amount=refund_amount,
        dispute_filed=dispute_filed,
    )

    steps.append(f"[{_timestamp()}] 📧 FINANCIAL: Customer response drafted ({channel} format)")
    steps.append(f"[{_timestamp()}] ✅ RESOLUTION COMPLETE — ticket closed")

    return {
        "refund_amount": refund_amount,
        "final_draft_response": response,
        "steps_taken": steps,
        "internal_notes": notes,
    }


# =============================================================================
#  RESPONSE GENERATION ENGINE (Template-Based)
# =============================================================================


def _generate_response(
    template: str,
    sentiment: str,
    channel: str,
    order_id: str,
    item_names: str,
    issue_type: str,
    refund_amount: float = 0.0,
    dispute_filed: bool = False,
) -> str:
    """
    Generates empathetic, context-aware customer responses adapting to:
      - Customer sentiment (angry → extra empathy, polite → warm tone)
      - Channel (WhatsApp → short/direct, Email → formal/detailed)
      - Issue type and resolution outcome
    """

    # ── Empathy openers based on sentiment ────────────────────────────────
    empathy = {
        "angry": (
            "I completely understand your frustration, and I sincerely apologize for "
            "this experience. This is absolutely not the level of service we strive for, "
            "and I take your concern very seriously."
        ),
        "frustrated": (
            "I'm truly sorry for the inconvenience you've experienced. "
            "I understand how frustrating this must be, and I want to make this right for you."
        ),
        "neutral": (
            "Thank you for reaching out to us regarding your order. "
            "I've looked into this for you and here's what I've found."
        ),
        "polite": (
            "Thank you so much for your patience and for bringing this to our attention. "
            "I really appreciate your understanding as we work to resolve this."
        ),
    }

    opener = empathy.get(sentiment, empathy["neutral"])

    # ── Template bodies ───────────────────────────────────────────────────
    if template == "refund":
        body = (
            f"I've processed a refund of **${refund_amount:.2f}** for your order "
            f"#{order_id} ({item_names}). The refund will be reflected in your "
            f"original payment method within 5–7 business days."
        )
        if dispute_filed:
            body += (
                f"\n\nAdditionally, I've opened an investigation with our delivery "
                f"partner to determine what happened with your package. We've requested "
                f"GPS delivery coordinates and photo proof."
            )

    elif template == "investigation":
        body = (
            f"I've launched a priority investigation into the delivery of your "
            f"order #{order_id} ({item_names}). Our team has contacted the carrier "
            f"directly, requesting GPS coordinates and delivery photo evidence. "
            f"We'll have an update for you within 48 hours."
        )
        if refund_amount > 0:
            body += f"\n\nIn the meantime, I've processed a refund of **${refund_amount:.2f}** to your account."

    elif template == "delay":
        body = (
            f"I can confirm that your order #{order_id} ({item_names}) has "
            f"experienced a shipping delay. I've applied a **${refund_amount:.2f} "
            f"shipping credit** to your account as compensation. "
            f"We're actively working with the carrier to expedite your delivery."
        )

    elif template == "rejection":
        body = (
            f"After a thorough review of your order #{order_id}, our team has "
            f"determined that we're unable to process a refund at this time. "
            f"This decision was made after careful consideration of our "
            f"return policy guidelines."
            f"\n\nIf you believe this decision should be reconsidered, please "
            f"don't hesitate to reach out, and we'll be happy to discuss "
            f"further options with you."
        )

    else:  # general
        body = (
            f"I've reviewed your order #{order_id} ({item_names}) and "
            f"here's the current status information. If you have any additional "
            f"questions, I'm here to help!"
        )

    # ── Channel formatting ────────────────────────────────────────────────
    if channel == "WhatsApp":
        # WhatsApp: shorter, use emojis, less formal
        response = f"Hi there! 👋\n\n{opener}\n\n{body}\n\nNeed anything else? Just reply here! 💬"
    elif channel == "Email":
        # Email: formal, structured
        response = (
            f"Dear Valued Customer,\n\n{opener}\n\n{body}\n\n"
            f"If you have any further questions, please don't hesitate to reply "
            f"to this email. We're here to help.\n\n"
            f"Best regards,\nCustomer Resolution Team\nOrder Reference: #{order_id}"
        )
    else:  # Web Chat
        response = f"{opener}\n\n{body}\n\nIs there anything else I can help you with?"

    return response


# =============================================================================
#  ROUTING FUNCTIONS
# =============================================================================


def route_after_triage(state: AgentState) -> str:
    """
    Routes from Triage to the appropriate next agent based on issue classification.

    Routing Logic:
      - delivery_not_received, late_delivery → logistics (investigate carrier)
      - damaged_item, wrong_item, return_request → fraud_risk (check customer risk)
      - general_inquiry → financial_adjuster (draft informational response)
    """
    issue_type = state.get("issue_type", "general_inquiry")

    if issue_type in ("delivery_not_received", "late_delivery"):
        logger.info(f"[Router] 🚚 Triage → Logistics (issue={issue_type})")
        return "logistics"
    elif issue_type in ("damaged_item", "wrong_item", "return_request"):
        logger.info(f"[Router] 🛡️ Triage → Fraud/Risk (issue={issue_type})")
        return "fraud_risk"
    else:
        logger.info(f"[Router] 💰 Triage → Financial (issue={issue_type})")
        return "financial_adjuster"


def route_after_fraud(state: AgentState) -> str:
    """
    Routes from Fraud/Risk to HITL gate or directly to Financial Adjuster.

    Routing Logic:
      - approval_required == True → hitl_approval (pause for human)
      - approval_required == False → financial_adjuster (auto-proceed)
    """
    if state.get("approval_required", False):
        logger.info("[Router] ⏸️ Fraud → HITL (HIGH RISK, approval required)")
        return "hitl_approval"
    else:
        logger.info("[Router] 💰 Fraud → Financial (LOW RISK, auto-proceed)")
        return "financial_adjuster"


# =============================================================================
#  GRAPH ASSEMBLY & COMPILATION
# =============================================================================


def build_graph() -> tuple:
    """
    Assembles the complete LangGraph state graph with all nodes, edges,
    conditional routing, and HITL checkpointing.

    Returns:
        tuple: (compiled_graph, checkpointer)
    """
    logger.info("[Graph] 🔧 Building agent graph...")

    builder = StateGraph(AgentState)

    # ── Add Nodes ─────────────────────────────────────────────────────────
    builder.add_node("triage", triage_node)
    builder.add_node("logistics", logistics_node)
    builder.add_node("fraud_risk", fraud_risk_node)
    builder.add_node("hitl_approval", hitl_approval_node)
    builder.add_node("financial_adjuster", financial_adjuster_node)

    # ── Entry Point ───────────────────────────────────────────────────────
    builder.add_edge(START, "triage")

    # ── Triage → conditional routing based on issue type ──────────────────
    builder.add_conditional_edges(
        "triage",
        route_after_triage,
        {
            "logistics": "logistics",
            "fraud_risk": "fraud_risk",
            "financial_adjuster": "financial_adjuster",
        },
    )

    # ── Logistics → always proceeds to risk check ─────────────────────────
    builder.add_edge("logistics", "fraud_risk")

    # ── Fraud Risk → conditional: HITL or auto-proceed ────────────────────
    builder.add_conditional_edges(
        "fraud_risk",
        route_after_fraud,
        {
            "hitl_approval": "hitl_approval",
            "financial_adjuster": "financial_adjuster",
        },
    )

    # ── HITL → Financial Adjuster ─────────────────────────────────────────
    builder.add_edge("hitl_approval", "financial_adjuster")

    # ── Financial Adjuster → END ──────────────────────────────────────────
    builder.add_edge("financial_adjuster", END)

    # ── Compile with checkpointer for HITL support ────────────────────────
    checkpointer = MemorySaver()
    graph = builder.compile(checkpointer=checkpointer)

    logger.info("[Graph] ✅ Agent graph compiled successfully")
    logger.info("[Graph]    Nodes: triage → logistics → fraud_risk → hitl_approval → financial_adjuster")
    logger.info("[Graph]    HITL: Enabled via interrupt()/Command(resume=...)")

    return graph, checkpointer


# =============================================================================
#  CONVENIENCE: Create default graph instance
# =============================================================================

# Built on import — ready for use by app.py
graph, checkpointer = build_graph()


# =============================================================================
#  MODULE SELF-TEST
# =============================================================================

if __name__ == "__main__":
    """
    Quick smoke test: runs a LOW-RISK delivery complaint through the graph.
    Does NOT test HITL (that requires interactive resume).
    Requires backend.py to be running on port 8000.
    """
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    print("\n" + "=" * 60)
    print("  [TEST] Agent Graph -- Self-Test (Low-Risk Delivery Complaint)")
    print("=" * 60 + "\n")

    test_input = {
        "original_complaint": (
            "My order #1004 says delivered but I haven't received it! "
            "I've checked everywhere. Please help!"
        ),
        "channel": "Web",
        "customer_id": "",
        "order_id": "",
        "tracking_id": "",
        "customer_email": "",
        "customer_sentiment": "",
        "issue_type": "",
        "risk_score": "",
        "risk_reasons": [],
        "approval_required": False,
        "approval_status": "not_required",
        "order_details": {},
        "tracking_details": {},
        "policy": {},
        "refund_amount": 0.0,
        "dispute_filed": False,
        "steps_taken": [],
        "internal_notes": [],
        "final_draft_response": "",
        "error": "",
    }

    config = {"configurable": {"thread_id": "test-thread-1"}}

    try:
        result = graph.invoke(test_input, config=config)
        print("\n📋 Steps Taken:")
        for step in result.get("steps_taken", []):
            print(f"  {step}")
        print(f"\n📧 Final Response:\n{result.get('final_draft_response', 'N/A')}")
        print(f"\n💰 Refund Amount: ${result.get('refund_amount', 0):.2f}")
        print(f"🛡️ Risk Score: {result.get('risk_score', 'N/A')}")
        print(f"📋 Dispute Filed: {result.get('dispute_filed', False)}")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("   Make sure backend.py is running: python backend.py")
