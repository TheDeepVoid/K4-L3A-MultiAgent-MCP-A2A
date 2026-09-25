from __future__ import annotations

import pytest

from student_agent.permissions import ACTOR_ALLOWLIST, assert_tool_allowed


@pytest.mark.parametrize(
    ("actor", "tool"),
    [
        ("order", "get_order"),
        ("order", "get_order_items"),
        ("order", "get_sellers"),
        ("order", "get_product_context"),
        ("payment", "get_order_payments"),
        ("payment", "get_payment_timeline"),
        ("payment", "get_refund_timeline"),
        ("shipment", "get_shipment_summary"),
        ("policy", "get_policy"),
    ],
)
def test_allowed_tools(actor: str, tool: str) -> None:
    assert tool in ACTOR_ALLOWLIST[actor]
    assert_tool_allowed(actor, tool)  # no raise


@pytest.mark.parametrize(
    ("actor", "tool"),
    [
        ("order", "get_order_payments"),
        ("order", "get_shipment_summary"),
        ("payment", "get_shipment_summary"),
        ("shipment", "get_order"),
        ("coordinator", "get_order"),
        ("verifier", "get_policy"),
        # never granted to anyone in the current design
        ("order", "get_customer_history"),
        ("policy", "get_customer_history"),
    ],
)
def test_forbidden_tools_raise(actor: str, tool: str) -> None:
    with pytest.raises(ValueError, match="not allowed"):
        assert_tool_allowed(actor, tool)


def test_unknown_actor_raises() -> None:
    with pytest.raises(ValueError, match="unknown actor"):
        assert_tool_allowed("mystery", "get_order")