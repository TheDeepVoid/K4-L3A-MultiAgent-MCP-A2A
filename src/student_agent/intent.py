"""Intent analysis for the L3A coordinator (supervisor).

The analyzer is a deterministic first pass over the case input: it performs no
MCP calls and uses no LLM. It decides which specialist domains a case needs
and which primary-issue hypotheses the specialists must verify with evidence.

Customer statements are treated as claims to be verified, never as ground
truth. Unknown claim topics never crash the planner: they are reported in
``unknown_topics`` and simply do not contribute hypotheses.
"""

from __future__ import annotations

from dataclasses import dataclass

# Specialist data domains dispatched by the coordinator.
DOMAIN_ORDER = "order"
DOMAIN_PAYMENT = "payment"
DOMAIN_SHIPMENT = "shipment"

# Internal agent roles.
ROLE_COORDINATOR = "coordinator"
ROLE_ORDER = DOMAIN_ORDER
ROLE_PAYMENT = DOMAIN_PAYMENT
ROLE_SHIPMENT = DOMAIN_SHIPMENT
ROLE_POLICY = "policy"
ROLE_VERIFIER = "verifier"

# Claim topic that expresses a requested remedy, not an issue hypothesis.
TOPIC_REQUESTED_FULL_REFUND = "requested_full_refund"

# topic -> set of specialist data domains that must verify evidence for it.
TOPIC_DOMAINS: dict[str, frozenset[str]] = {
    "canceled_order_paid": frozenset({DOMAIN_ORDER, DOMAIN_PAYMENT}),
    "unavailable_order_paid": frozenset({DOMAIN_ORDER, DOMAIN_PAYMENT}),
    "late_delivery_seller": frozenset({DOMAIN_ORDER, DOMAIN_SHIPMENT}),
    "late_delivery_logistics": frozenset({DOMAIN_ORDER, DOMAIN_SHIPMENT}),
    "valid_split_payment": frozenset({DOMAIN_ORDER, DOMAIN_PAYMENT}),
    "payment_mismatch": frozenset({DOMAIN_ORDER, DOMAIN_PAYMENT}),
    "duplicate_charge": frozenset({DOMAIN_ORDER, DOMAIN_PAYMENT}),
    "refund_pending": frozenset({DOMAIN_ORDER, DOMAIN_PAYMENT}),
    "refund_failed": frozenset({DOMAIN_ORDER, DOMAIN_PAYMENT}),
    "unsupported_claim": frozenset({DOMAIN_ORDER}),
    "insufficient_evidence": frozenset({DOMAIN_ORDER}),
    # A refund request always needs payment evidence to quantify the refund.
    TOPIC_REQUESTED_FULL_REFUND: frozenset({DOMAIN_PAYMENT}),
}

# topic -> most plausible primary-issue hypothesis to verify with evidence.
# Remedy requests ("requested_full_refund") map to None: they are not issues.
TOPIC_HYPOTHESIS: dict[str, str | None] = {
    "canceled_order_paid": "canceled_order_paid",
    "unavailable_order_paid": "unavailable_order_paid",
    "late_delivery_seller": "late_delivery_seller",
    "late_delivery_logistics": "late_delivery_logistics",
    "valid_split_payment": "valid_split_payment",
    "payment_mismatch": "payment_mismatch",
    "duplicate_charge": "duplicate_charge",
    "refund_pending": "refund_pending",
    "refund_failed": "refund_failed",
    "unsupported_claim": "unsupported_claim",
    "insufficient_evidence": "insufficient_evidence",
    TOPIC_REQUESTED_FULL_REFUND: None,
}


class IntentError(ValueError):
    """Raised when the case input cannot be turned into a plan."""


@dataclass(frozen=True)
class ClaimSpec:
    claim_id: str
    topic: str


@dataclass(frozen=True)
class CaseAnalysis:
    """Machine-readable plan produced from the case input."""

    case_id: str
    policy_version: str
    claimed_order_id: str
    entity_scope: tuple[str, ...]
    claims: tuple[ClaimSpec, ...]
    hypotheses: tuple[str, ...]
    needed_domains: frozenset[str]
    unknown_topics: tuple[str, ...]

    def needs(self, domain: str) -> bool:
        return domain in self.needed_domains


class IntentAnalyzer:
    """Turn an L3A case manifest into a verification plan."""

    def analyze(self, case: dict) -> CaseAnalysis:
        case_id = case.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            raise IntentError("case input has no case_id")

        request = case.get("customer_request")
        if not isinstance(request, dict):
            raise IntentError(f"{case_id}: customer_request is missing or not an object")

        claimed_order_id = request.get("claimed_order_id")
        if not isinstance(claimed_order_id, str) or not claimed_order_id:
            raise IntentError(f"{case_id}: customer_request has no claimed_order_id")

        policy_version = case.get("policy_version", "")
        if not isinstance(policy_version, str) or not policy_version:
            raise IntentError(
                f"{case_id}: policy_version is missing; do not guess or default to 'latest'"
            )

        claims: list[ClaimSpec] = []
        raw_claims = request.get("claims", [])
        if not isinstance(raw_claims, list):
            raise IntentError(f"{case_id}: customer_request.claims must be an array")
        for index, raw in enumerate(raw_claims):
            if not isinstance(raw, dict):
                raise IntentError(f"{case_id}: claims[{index}] is not an object")
            claim_id = raw.get("claim_id")
            topic = raw.get("topic")
            if not isinstance(claim_id, str) or not claim_id:
                raise IntentError(f"{case_id}: claims[{index}] has no claim_id")
            if not isinstance(topic, str) or not topic:
                raise IntentError(f"{case_id}: claims[{index}] has no topic")
            claims.append(ClaimSpec(claim_id=claim_id, topic=topic))

        topics = tuple(claim.topic for claim in claims)
        unknown = tuple(topic for topic in topics if topic not in TOPIC_DOMAINS)
        hypotheses = tuple(
            dict.fromkeys(
                hypothesis
                for topic in topics
                if (hypothesis := TOPIC_HYPOTHESIS.get(topic)) is not None
            )
        )
        domains = frozenset({DOMAIN_ORDER}).union(
            *(TOPIC_DOMAINS[topic] for topic in topics if topic in TOPIC_DOMAINS)
        )

        return CaseAnalysis(
            case_id=case_id,
            policy_version=policy_version,
            claimed_order_id=claimed_order_id,
            entity_scope=(claimed_order_id,),
            claims=tuple(claims),
            hypotheses=hypotheses,
            needed_domains=domains,
            unknown_topics=unknown,
        )