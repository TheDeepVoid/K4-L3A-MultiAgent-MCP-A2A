"""Tool-permission policy for the coordinator (ARCHITECTURE.md section 2).

Only constants live here. Specialist agents enforce the allowlist before
calling the MCP Evidence Gateway; the coordinator (supervisor) owns the policy
but never calls data tools itself (discovery only). ``get_customer_history``
is intentionally granted to no actor in the current design.
"""

from __future__ import annotations

COORDINATOR_TOOLS: frozenset[str] = frozenset()
ORDER_TOOLS: frozenset[str] = frozenset(
    {"get_order", "get_order_items", "get_sellers", "get_product_context"}
)
PAYMENT_TOOLS: frozenset[str] = frozenset(
    {"get_order_payments", "get_payment_timeline", "get_refund_timeline"}
)
SHIPMENT_TOOLS: frozenset[str] = frozenset({"get_shipment_summary"})
POLICY_TOOLS: frozenset[str] = frozenset({"get_policy"})
VERIFIER_TOOLS: frozenset[str] = frozenset()

ACTOR_ALLOWLIST: dict[str, frozenset[str]] = {
    "coordinator": COORDINATOR_TOOLS,
    "order": ORDER_TOOLS,
    "payment": PAYMENT_TOOLS,
    "shipment": SHIPMENT_TOOLS,
    "policy": POLICY_TOOLS,
    "verifier": VERIFIER_TOOLS,
}


def assert_tool_allowed(actor: str, tool_name: str) -> None:
    """Raise if *actor* is not allowed to call *tool_name*."""
    allowed = ACTOR_ALLOWLIST.get(actor)
    if allowed is None:
        raise ValueError(f"unknown actor {actor!r} in tool allowlist")
    if tool_name not in allowed:
        raise ValueError(f"actor {actor!r} is not allowed to call {tool_name!r}")