from __future__ import annotations

from copy import deepcopy
from decimal import Decimal, InvalidOperation
from typing import Any

from .a2a import AgentMessage, VerifiedFact
from .evidence import EvidenceCollector
from .observability import record_evidence_consumed
from .state import CaseState
from .trace import TraceWriter

PRIMARY_ISSUES = {
    "canceled_order_paid", "unavailable_order_paid", "late_delivery_seller",
    "late_delivery_logistics", "valid_split_payment", "payment_mismatch",
    "duplicate_charge", "refund_pending", "refund_failed", "unsupported_claim",
    "insufficient_evidence",
}


def _state_facts(state: CaseState) -> dict[str, Any]:
    facts: dict[str, Any] = {}
    for message in state.messages:
        for fact in message.facts:
            facts[fact.name] = fact.value
    return facts


def _confidence(state: CaseState, has_rule: bool) -> float:
    if not has_rule:
        return 0.2
    specialist_refs = {
        ref
        for message in state.messages
        if message.sender != "policy-agent"
        for ref in message.evidence_refs
    }
    return min(0.95, 0.65 + 0.1 * min(len(specialist_refs), 3))


def build_policy_output(case: dict[str, Any], state: CaseState) -> dict[str, Any]:
    """Apply validated policy rules to the case claims and verified facts."""
    facts = _state_facts(state)
    policy = facts.get("policy_rules", {})
    rules = policy.get("rules", {}) if isinstance(policy, dict) else {}
    claims = case["customer_request"]["claims"]
    evidence_refs = list(state.evidence)
    selected_issue = "insufficient_evidence"
    selected_rule: dict[str, Any] | None = None
    assessments: list[dict[str, Any]] = []

    for claim in claims:
        topic = claim["topic"]
        rule = rules.get(topic) if isinstance(rules.get(topic), dict) else None
        supported = rule is not None and topic in PRIMARY_ISSUES
        if supported and selected_rule is None:
            selected_issue = topic
            selected_rule = rule
        assessments.append({
            "claim_id": claim["claim_id"],
            "verdict": "supported" if supported else "insufficient_evidence",
            "confidence": _confidence(state, supported),
            "evidence_refs": evidence_refs,
        })

    if selected_rule is None:
        selected_rule = {
            "case_status": "needs_investigation",
            "recommended_action": "Collect additional evidence",
            "refund_brl": 0,
            "responsible_parties": [],
        }

    refund = Decimal(str(selected_rule.get("refund_brl", 0)))
    order_id = state.entity_scope["order_ids"][0]
    return {
        "schema_version": "day09-l3a-output-v2",
        "case_id": state.case_id,
        "assessment": {
            "primary_issue": selected_issue,
            "case_status": selected_rule["case_status"],
            "confidence": _confidence(state, selected_issue != "insufficient_evidence"),
        },
        "affected_entities": {
            "order_ids": [order_id],
            "item_ids": [],
            "seller_ids": [],
            "payment_references": [],
            "shipment_ids": [],
        },
        "claim_assessments": assessments,
        "root_cause_analysis": {
            "ranked_causes": ([{"cause_code": selected_issue.upper(), "rank": 1}]
                              if selected_issue != "insufficient_evidence" else []),
            "responsible_parties": selected_rule.get("responsible_parties", []),
        },
        "evidence_refs": evidence_refs,
        "data_conflicts": [],
        "financial_resolution": {
            "currency": "BRL",
            "recommended_refund_brl": float(refund),
            "refund_lines": ([{
                "reason_code": selected_issue,
                "amount_brl": float(refund),
                "entity_id": order_id,
            }] if refund > 0 else []),
        },
        "resolution_actions": [selected_rule["recommended_action"]],
    }


async def inspect_policy(
    state: CaseState,
    collector: EvidenceCollector,
    trace: TraceWriter,
) -> AgentMessage:
    """Đọc policy đã xác minh; chưa quyết định kết quả case."""

    if collector.state is not state:
        raise ValueError("Collector and agent must share case state")

    evidence = await collector.collect(
        "policy-agent",
        "get_policy",
        policy_version=state.policy_version,
    )

    if evidence["domain"] != "policy":
        raise ValueError("Expected policy evidence")

    data = evidence["data"]
    if not isinstance(data, dict):
        raise ValueError("Policy data must be an object")

    if data.get("policy_version") != state.policy_version:
        raise ValueError("Policy version does not match case")

    if data.get("currency") != "BRL":
        raise ValueError("Unsupported policy currency")

    rules = data.get("rules")
    if not isinstance(rules, dict) or not rules:
        raise ValueError("Policy rules must be a non-empty object")

    party_types = {
        "seller",
        "platform",
        "logistics_provider",
        "payment_provider",
        "customer",
        "unknown",
    }

    for issue, rule in rules.items():
        if not isinstance(issue, str) or not issue.strip():
            raise ValueError("Invalid policy issue name")
        if not isinstance(rule, dict):
            raise ValueError("Policy rule must be an object")

        if rule.get("case_status") not in {
            "action_required", "no_action", "needs_investigation"
        }:
            raise ValueError("Invalid policy case_status")

        action = rule.get("recommended_action")
        if not isinstance(action, str) or not action.strip():
            raise ValueError("Invalid recommended_action")

        try:
            amount = Decimal(str(rule.get("refund_brl")))
        except InvalidOperation as exc:
            raise ValueError("Invalid policy refund amount") from exc

        if not amount.is_finite() or amount < 0:
            raise ValueError("Policy refund must be finite and nonnegative")

        parties = rule.get("responsible_parties")
        if not isinstance(parties, list):
            raise ValueError("responsible_parties must be an array")

        for party in parties:
            if not isinstance(party, dict):
                raise ValueError("Responsible party must be an object")
            if party.get("party_type") not in party_types:
                raise ValueError("Invalid party_type")
            if "party_id" not in party:
                raise ValueError("Missing party_id")
            if party["party_id"] is not None and not isinstance(
                party["party_id"], str
            ):
                raise ValueError("party_id must be a string or null")

    evidence_ref = evidence["evidence_ref"]

    record_evidence_consumed(
        state, trace, "policy-agent", [evidence_ref]
    )

    return AgentMessage(
        case_id=state.case_id,
        sender="policy-agent",
        recipient="coordinator",
        task="Report validated policy rules",
        facts=[
            VerifiedFact(
                name="policy_rules",
                value=deepcopy(data),
                evidence_refs=[evidence_ref],
            )
        ],
        evidence_refs=[evidence_ref],
        status="completed",
    )