from __future__ import annotations

from copy import deepcopy

import pytest

from student_agent.a2a import AgentMessage, VerifiedFact
from student_agent.policy_agent import build_policy_output
from student_agent.state import CaseState, EvidenceRecord
from student_agent.verifier import assert_valid

CASE = {
    "case_id": "L3A_CASE_999",
    "customer_request": {
        "claimed_order_id": "ord_123",
        "claims": [{"claim_id": "claim-a", "topic": "late_delivery_seller"}],
    },
    "policy_version": "EC_POLICY_V1",
}
ORDER_REF = "ev_" + ("O" * 40)
POLICY_REF = "ev_" + ("P" * 40)


def make_state() -> CaseState:
    state = CaseState("L3A_CASE_999", {"order_ids": ["ord_123"]}, "EC_POLICY_V1", 10**12)
    state.evidence[ORDER_REF] = EvidenceRecord(
        state.case_id,
        "order-item-agent",
        "get_order",
        {"order_id": "ord_123"},
        {"evidence_ref": ORDER_REF},
    )
    state.evidence[POLICY_REF] = EvidenceRecord(
        state.case_id,
        "policy-agent",
        "get_policy",
        {"policy_version": "EC_POLICY_V1"},
        {"evidence_ref": POLICY_REF},
    )
    state.messages.extend([
        AgentMessage(
            state.case_id,
            "order-item-agent",
            "coordinator",
            "order",
            facts=[VerifiedFact("order", {"order_status": "delivered"}, [ORDER_REF])],
            evidence_refs=[ORDER_REF],
            status="completed",
        ),
        AgentMessage(
            state.case_id,
            "policy-agent",
            "coordinator",
            "policy",
            facts=[VerifiedFact("policy_rules", {
                "rules": {
                    "late_delivery_seller": {
                        "case_status": "action_required",
                        "recommended_action": "Refund shipping",
                        "refund_brl": 10,
                        "responsible_parties": [
                            {"party_type": "seller", "party_id": "seller-1"}
                        ],
                    }
                }
            }, [POLICY_REF])],
            evidence_refs=[POLICY_REF],
            status="completed",
        ),
    ])
    return state


def test_policy_output_is_calibrated_and_verifiable() -> None:
    state = make_state()
    output = build_policy_output(CASE, state)

    assert output["assessment"]["confidence"] <= 0.95
    assert output["financial_resolution"]["recommended_refund_brl"] == 10.0
    assert_valid(output, state, CASE)


def test_verifier_rejects_inconsistent_party_and_refund() -> None:
    state = make_state()
    output = build_policy_output(CASE, state)
    invalid = deepcopy(output)
    invalid["root_cause_analysis"]["responsible_parties"] = [
        {"party_type": "logistics_provider", "party_id": "carrier-1"}
    ]
    invalid["financial_resolution"]["refund_lines"][0]["amount_brl"] = 5.0

    with pytest.raises(ValueError, match="Verifier rejected output"):
        assert_valid(invalid, state, CASE)
