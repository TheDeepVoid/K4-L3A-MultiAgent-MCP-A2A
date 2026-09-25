from __future__ import annotations

from decimal import Decimal
from typing import Any

from .state import CaseState

EXPECTED_FIELDS = {
    "schema_version",
    "case_id",
    "assessment",
    "affected_entities",
    "claim_assessments",
    "root_cause_analysis",
    "evidence_refs",
    "data_conflicts",
    "financial_resolution",
    "resolution_actions",
}

RESPONSIBLE_PARTY_BY_ISSUE = {
    "late_delivery_seller": {"seller", "unknown"},
    "late_delivery_logistics": {"logistics_provider", "unknown"},
    "payment_mismatch": {"payment_provider", "unknown"},
    "duplicate_charge": {"payment_provider", "unknown"},
    "refund_pending": {"payment_provider", "unknown"},
    "refund_failed": {"payment_provider", "unknown"},
}


def verification_errors(
    output: dict[str, Any], state: CaseState, case: dict[str, Any]
) -> list[str]:
    errors: list[str] = []
    if set(output) != EXPECTED_FIELDS:
        errors.append("output fields do not match the public contract")
    if output.get("schema_version") != "day09-l3a-output-v2":
        errors.append("invalid output schema version")
    if output.get("case_id") != state.case_id or output.get("case_id") != case.get("case_id"):
        errors.append("case_id does not match the active case")

    evidence_refs = output.get("evidence_refs", [])
    if not isinstance(evidence_refs, list) or len(evidence_refs) != len(set(evidence_refs)):
        errors.append("evidence_refs must be unique")
    elif not set(evidence_refs).issubset(state.evidence):
        errors.append("output cites evidence outside the current case")

    claim_ids = {
        claim.get("claim_id")
        for claim in case.get("customer_request", {}).get("claims", [])
    }
    seen_claim_ids: set[str] = set()
    for assessment in output.get("claim_assessments", []):
        claim_id = assessment.get("claim_id")
        if claim_id not in claim_ids or claim_id in seen_claim_ids:
            errors.append("claim assessments must match unique input claim_ids")
        seen_claim_ids.add(claim_id)
        if not set(assessment.get("evidence_refs", [])).issubset(set(evidence_refs)):
            errors.append(f"claim {claim_id} cites evidence outside output refs")
        confidence = assessment.get("confidence")
        if not isinstance(confidence, (int, float)) or not 0 <= confidence <= 0.95:
            errors.append(f"claim {claim_id} confidence is not calibrated")
    if seen_claim_ids != claim_ids:
        errors.append("every input claim must have one assessment")

    assessment = output.get("assessment", {})
    primary_issue = assessment.get("primary_issue")
    confidence = assessment.get("confidence")
    if not isinstance(confidence, (int, float)) or not 0 <= confidence <= 0.95:
        errors.append("primary confidence is not calibrated")

    parties = output.get("root_cause_analysis", {}).get("responsible_parties", [])
    party_types = {party.get("party_type") for party in parties}
    allowed = RESPONSIBLE_PARTY_BY_ISSUE.get(primary_issue)
    if allowed and party_types and not party_types.issubset(allowed):
        errors.append("responsible parties conflict with primary issue")

    financial = output.get("financial_resolution", {})
    try:
        recommended = Decimal(str(financial.get("recommended_refund_brl")))
        lines = financial.get("refund_lines", [])
        total = sum(Decimal(str(line.get("amount_brl"))) for line in lines)
        if recommended < 0 or total != recommended:
            errors.append("refund total does not equal refund lines")
        if recommended > 0 and assessment.get("case_status") != "action_required":
            errors.append("a positive refund requires action_required status")
        line_keys = [(line.get("reason_code"), line.get("entity_id")) for line in lines]
        if len(line_keys) != len(set(line_keys)):
            errors.append("refund lines contain duplicate charges")
    except (ArithmeticError, TypeError, ValueError):
        errors.append("financial resolution contains invalid numeric values")

    ranked = output.get("root_cause_analysis", {}).get("ranked_causes", [])
    ranks = [cause.get("rank") for cause in ranked]
    if len(ranks) != len(set(ranks)):
        errors.append("ranked causes contain duplicate ranks")
    return errors


def assert_valid(output: dict[str, Any], state: CaseState, case: dict[str, Any]) -> None:
    errors = verification_errors(output, state, case)
    if errors:
        raise ValueError("Verifier rejected output: " + "; ".join(errors))
