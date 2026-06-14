"""
=============================================================================
 DYNAMIC POLICY ENGINE — Simulated RAG / Vector-Lookup
=============================================================================
 Provides `lookup_company_policy(issue_type)` which dynamically fetches
 business rules (return windows, auto-refund limits, risk thresholds) rather
 than hardcoding constants throughout the agent logic.

 In production, this would query a vector store (Pinecone / Chroma / Weaviate)
 against an indexed corpus of company policy documents. Here we simulate that
 with an in-memory policy registry.
=============================================================================
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("policy_engine")

# ── Policy Registry ──────────────────────────────────────────────────────────
# Each policy mirrors what a RAG retrieval would return: structured metadata
# plus a human-readable summary paragraph.

POLICY_REGISTRY: dict[str, dict] = {
    "delivery_not_received": {
        "policy_name": "Delivery Not Received — Investigation & Refund Policy",
        "issue_type": "delivery_not_received",
        "return_window_days": 30,
        "auto_refund_limit": 75.00,
        "risk_threshold_return_rate": 0.40,
        "escalation_required": True,
        "requires_gps_verification": True,
        "policy_text": (
            "When a customer reports a delivery as not received while tracking "
            "shows 'Delivered', the system MUST open an automated carrier dispute "
            "requesting GPS coordinates and delivery photo proof. If the customer's "
            "lifetime return rate exceeds 40%, the case is flagged for manual review. "
            "Auto-refunds are capped at $75.00 for standard-risk customers. "
            "The investigation window is 30 days from the reported delivery date."
        ),
    },
    "damaged_item": {
        "policy_name": "Damaged Item — Return & Replacement Policy",
        "issue_type": "damaged_item",
        "return_window_days": 15,
        "auto_refund_limit": 50.00,
        "risk_threshold_return_rate": 0.40,
        "escalation_required": False,
        "requires_gps_verification": False,
        "policy_text": (
            "Customers reporting damaged items are eligible for a full refund or "
            "replacement within 15 days of delivery. Photo evidence of damage is "
            "preferred but not mandatory for orders under $50. Customers with a "
            "lifetime return rate exceeding 40% require manager approval before "
            "processing any refund."
        ),
    },
    "wrong_item": {
        "policy_name": "Wrong Item Received — Exchange Priority Policy",
        "issue_type": "wrong_item",
        "return_window_days": 30,
        "auto_refund_limit": 100.00,
        "risk_threshold_return_rate": 0.40,
        "escalation_required": False,
        "requires_gps_verification": False,
        "policy_text": (
            "When a wrong item is delivered, the priority action is an immediate "
            "exchange at no cost. If exchange stock is unavailable, a full refund "
            "is processed. Auto-refunds up to $100 are permitted for standard-risk "
            "customers. High-risk customers (return rate >40%) require HITL approval."
        ),
    },
    "late_delivery": {
        "policy_name": "Late Delivery — Shipping Credit Policy",
        "issue_type": "late_delivery",
        "return_window_days": None,
        "auto_refund_limit": 25.00,
        "risk_threshold_return_rate": None,
        "escalation_required": False,
        "requires_gps_verification": False,
        "policy_text": (
            "For confirmed late deliveries (carrier-verified delay), customers "
            "receive a shipping credit of up to $25.00 applied to their next order. "
            "No full refund is issued for late delivery alone. If the item is also "
            "damaged upon arrival, the Damaged Item policy supersedes."
        ),
    },
    "return_request": {
        "policy_name": "Standard Return — 30-Day Return Window Policy",
        "issue_type": "return_request",
        "return_window_days": 30,
        "auto_refund_limit": 75.00,
        "risk_threshold_return_rate": 0.40,
        "escalation_required": False,
        "requires_gps_verification": False,
        "policy_text": (
            "Customers may request a return within 30 days of delivery for a full "
            "refund. Items must be in original, unopened condition. Customers with "
            "a return rate exceeding 40% are flagged for manual review. Auto-refunds "
            "are capped at $75 for low-risk customers."
        ),
    },
    "general_inquiry": {
        "policy_name": "General Customer Inquiry — Information Response",
        "issue_type": "general_inquiry",
        "return_window_days": None,
        "auto_refund_limit": 0.00,
        "risk_threshold_return_rate": None,
        "escalation_required": False,
        "requires_gps_verification": False,
        "policy_text": (
            "General inquiries about order status, product information, or account "
            "details are handled with informational responses. No financial actions "
            "are taken. The agent provides accurate, helpful information and directs "
            "customers to appropriate resources."
        ),
    },
}

# ── Default / Fallback Policy ────────────────────────────────────────────────

DEFAULT_POLICY: dict = {
    "policy_name": "Fallback — General Handling Policy",
    "issue_type": "unknown",
    "return_window_days": 30,
    "auto_refund_limit": 50.00,
    "risk_threshold_return_rate": 0.40,
    "escalation_required": True,
    "requires_gps_verification": False,
    "policy_text": (
        "No specific policy matched the issue type. Applying default handling: "
        "30-day window, $50 auto-refund cap, and manager escalation required "
        "for all financial actions."
    ),
}


# ── Public API ────────────────────────────────────────────────────────────────

def lookup_company_policy(issue_type: str) -> dict:
    """
    Simulated RAG / vector-lookup for company policy documents.

    In production this would:
      1. Embed the issue_type into a vector
      2. Query a vector store for top-k matching policy documents
      3. Return the most relevant policy with metadata

    Here we do a simple dictionary lookup with fuzzy matching.

    Args:
        issue_type: Classified issue type string

    Returns:
        dict with policy metadata and human-readable policy_text
    """
    # Normalize input
    normalized = issue_type.strip().lower().replace(" ", "_").replace("-", "_")

    # Direct match
    if normalized in POLICY_REGISTRY:
        policy = POLICY_REGISTRY[normalized]
        logger.info(
            f"[PolicyEngine] ✅ Policy found: '{policy['policy_name']}' "
            f"for issue_type='{issue_type}'"
        )
        return {**policy, "lookup_timestamp": datetime.now(tz=timezone.utc).isoformat()}

    # Fuzzy / partial match — check if any key is a substring
    for key, policy in POLICY_REGISTRY.items():
        if key in normalized or normalized in key:
            logger.info(
                f"[PolicyEngine] 🔍 Fuzzy match: '{policy['policy_name']}' "
                f"for issue_type='{issue_type}'"
            )
            return {**policy, "lookup_timestamp": datetime.now(tz=timezone.utc).isoformat()}

    # Fallback
    logger.warning(
        f"[PolicyEngine] ⚠️ No policy match for issue_type='{issue_type}', "
        f"using default policy."
    )
    return {**DEFAULT_POLICY, "lookup_timestamp": datetime.now(tz=timezone.utc).isoformat()}


def get_all_policies() -> list[dict]:
    """Returns all registered policies (for admin/debug views)."""
    return list(POLICY_REGISTRY.values())


# ── Module self-test ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("\n📋 Policy Engine — Self-Test\n" + "=" * 50)
    test_cases = [
        "delivery_not_received",
        "damaged_item",
        "wrong_item",
        "late_delivery",
        "return_request",
        "general_inquiry",
        "some_unknown_thing",
    ]
    for case in test_cases:
        result = lookup_company_policy(case)
        print(f"\n  Issue: {case}")
        print(f"  Policy: {result['policy_name']}")
        print(f"  Auto-Refund Limit: ${result['auto_refund_limit']:.2f}")
        print(f"  Escalation Required: {result['escalation_required']}")
