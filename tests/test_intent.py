from __future__ import annotations

import pytest

from student_agent.intent import (
    DOMAIN_ORDER,
    DOMAIN_PAYMENT,
    DOMAIN_SHIPMENT,
    TOPIC_REQUESTED_FULL_REFUND,
    IntentAnalyzer,
    IntentError,
)

ANALYZER = IntentAnalyzer()


def make_case(topic: str, *, with_refund: bool = True) -> dict:
    claims = [{"claim_id": "claim-a", "topic": topic}]
    if with_refund:
        claims.append({"claim_id": "claim-b", "topic": TOPIC_REQUESTED_FULL_REFUND})
    return {
        "case_id": "L3A_CASE_999",
        "opened_at": "2018-01-01T09:00:00-03:00",
        "customer_request": {
            "language": "vi",
            "message": "mẫu yêu cầu",
            "claimed_order_id": "ord_123",
            "claims": claims,
        },
        "policy_version": "EC_POLICY_V1",
    }


def test_extracts_entities_claims_and_policy_version() -> None:
    analysis = ANALYZER.analyze(make_case("canceled_order_paid"))
    assert analysis.case_id == "L3A_CASE_999"
    assert analysis.claimed_order_id == "ord_123"
    assert analysis.entity_scope == ("ord_123",)
    assert analysis.policy_version == "EC_POLICY_V1"
    assert [(claim.claim_id, claim.topic) for claim in analysis.claims] == [
        ("claim-a", "canceled_order_paid"),
        ("claim-b", TOPIC_REQUESTED_FULL_REFUND),
    ]


@pytest.mark.parametrize(
    ("topic", "expected_hypothesis", "expected_domains"),
    [
        ("canceled_order_paid", "canceled_order_paid", {DOMAIN_ORDER, DOMAIN_PAYMENT}),
        ("unavailable_order_paid", "unavailable_order_paid", {DOMAIN_ORDER, DOMAIN_PAYMENT}),
        ("late_delivery_seller", "late_delivery_seller", {DOMAIN_ORDER, DOMAIN_SHIPMENT}),
        (
            "late_delivery_logistics",
            "late_delivery_logistics",
            {DOMAIN_ORDER, DOMAIN_SHIPMENT},
        ),
        ("valid_split_payment", "valid_split_payment", {DOMAIN_ORDER, DOMAIN_PAYMENT}),
        ("payment_mismatch", "payment_mismatch", {DOMAIN_ORDER, DOMAIN_PAYMENT}),
        ("duplicate_charge", "duplicate_charge", {DOMAIN_ORDER, DOMAIN_PAYMENT}),
        ("refund_pending", "refund_pending", {DOMAIN_ORDER, DOMAIN_PAYMENT}),
        ("refund_failed", "refund_failed", {DOMAIN_ORDER, DOMAIN_PAYMENT}),
        ("unsupported_claim", "unsupported_claim", {DOMAIN_ORDER}),
        ("insufficient_evidence", "insufficient_evidence", {DOMAIN_ORDER}),
    ],
)
def test_maps_topic_to_hypothesis_and_domains(
    topic: str, expected_hypothesis: str, expected_domains: set[str]
) -> None:
    # Single-claim case so the domain mapping is exact (no refund claim).
    analysis = ANALYZER.analyze(make_case(topic, with_refund=False))
    assert analysis.hypotheses == (expected_hypothesis,)
    assert analysis.needed_domains == frozenset(expected_domains)


def test_refund_request_adds_payment_domain() -> None:
    analysis = ANALYZER.analyze(make_case("late_delivery_seller"))
    assert analysis.needs(DOMAIN_PAYMENT)  # requested_full_refund claim
    assert analysis.needs(DOMAIN_SHIPMENT)


def test_unknown_topic_is_reported_not_crashed() -> None:
    case = make_case("mystery_topic")
    analysis = ANALYZER.analyze(case)
    assert analysis.unknown_topics == ("mystery_topic",)
    assert analysis.hypotheses == ()
    assert analysis.needs(DOMAIN_ORDER)  # grounding domain always planned


def test_empty_claims_still_plan_order() -> None:
    case = make_case("canceled_order_paid")
    case["customer_request"]["claims"] = []
    analysis = ANALYZER.analyze(case)
    assert analysis.claims == ()
    assert analysis.hypotheses == ()
    assert analysis.needs(DOMAIN_ORDER)


@pytest.mark.parametrize(
    "case",
    [
        {},
        {"case_id": "L3A_CASE_999"},
        {"case_id": "L3A_CASE_999", "customer_request": {"message": "x"}},
        {
            "case_id": "L3A_CASE_999",
            "customer_request": {
                "claimed_order_id": "ord_123",
                "claims": [{"claim_id": "a", "topic": "canceled_order_paid"}],
            },
        },
    ],
)
def test_malformed_case_raises(case: dict) -> None:
    with pytest.raises(IntentError):
        ANALYZER.analyze(case)


def test_missing_policy_version_raises() -> None:
    case = make_case("canceled_order_paid")
    del case["policy_version"]
    with pytest.raises(IntentError, match="policy_version"):
        ANALYZER.analyze(case)