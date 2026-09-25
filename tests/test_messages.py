from __future__ import annotations

import pytest

from student_agent.messages import (
    DecisionCode,
    Fact,
    HandoffMessage,
    TaskStatus,
)

EV1 = "ev_" + ("a" * 40)
EV2 = "ev_" + ("b" * 40)


def test_fact_deduplicates_and_caps_evidence_refs() -> None:
    fact = Fact("order paid", (EV1, EV1, EV2))
    assert fact.evidence_refs == (EV1, EV2)
    with pytest.raises(ValueError, match="at most 20"):
        Fact("too many", tuple(f"ev_{'c' * 40}{index}" for index in range(21)))


def test_handoff_message_deduplicates_and_caps_evidence_refs() -> None:
    message = HandoffMessage(
        case_id="L3A_CASE_999",
        sender="coordinator",
        recipient="order",
        task="verify_order_and_items",
        entity_scope=("o1", "o1", "o2"),
        evidence_refs=[EV1, EV2, EV1],
        status=TaskStatus.PENDING,
    )
    assert message.entity_scope == ("o1", "o2")
    assert message.evidence_refs == [EV1, EV2]
    with pytest.raises(ValueError, match="at most 30"):
        HandoffMessage(
            case_id="L3A_CASE_999",
            sender="order",
            recipient="coordinator",
            task="t",
            evidence_refs=[f"ev_{'d' * 40}{index}" for index in range(31)],
        )


def test_all_evidence_refs_includes_facts() -> None:
    fact = Fact("order canceled", (EV1,))
    message = HandoffMessage(
        case_id="L3A_CASE_999",
        sender="order",
        recipient="coordinator",
        task="verify_order_and_items",
        facts=[fact],
        evidence_refs=[EV2],
    )
    assert message.all_evidence_refs() == [EV2, EV1]  # message refs first, then fact refs


def test_status_and_decision_code_helpers() -> None:
    message = HandoffMessage(
        case_id="L3A_CASE_999",
        sender="order",
        recipient="coordinator",
        task="verify_order_and_items",
        status=TaskStatus.COMPLETED,
        decision_code=DecisionCode.HANDOFF_OK,
    )
    assert message.is_completed
    assert not HandoffMessage(
        case_id="L3A_CASE_999",
        sender="order",
        recipient="coordinator",
        task="t",
        status=TaskStatus.NEEDS_MORE_EVIDENCE,
    ).is_completed


def test_internal_fields_never_leak_patterns() -> None:
    # output/policy_version live on internal messages only; they are not part
    # of the public output or trace schemas.
    message = HandoffMessage(
        case_id="L3A_CASE_999",
        sender="policy",
        recipient="verifier",
        task="verify_draft",
        policy_version="EC_POLICY_V1",
        output={"draft": True},
    )
    assert message.policy_version == "EC_POLICY_V1"
    assert message.output == {"draft": True}
    assert set(message.__dataclass_fields__) >= {
        "case_id",
        "sender",
        "recipient",
        "task",
        "entity_scope",
        "facts",
        "evidence_refs",
        "status",
    }