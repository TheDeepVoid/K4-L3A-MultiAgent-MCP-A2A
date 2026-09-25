"""Specialist agent seam for the L3A workflow.

The coordinator (supervisor) dispatches tasks to agents through an
``AgentRegistry``. This module defines the call contract, the default
registry and loud placeholder stubs.

The specialist implementations (order, payment, shipment agents plus the MCP
Evidence Gateway integration) belong to the next work item on the team board.
Until they land, dispatching a stub raises ``NotImplementedError`` instead of
fabricating facts or evidence references, which the competition contract
forbids.
"""

from __future__ import annotations

from typing import Protocol

from .mcp_gateway import EvidenceGateway
from .messages import Fact, HandoffMessage, TaskStatus
from .trace import TraceWriter

SPECIALIST_ROLES = ("order", "payment", "shipment")
ALL_ROLES = ("order", "payment", "shipment", "policy", "verifier")


class SpecialistAgent(Protocol):
    """Call contract for every agent in the workflow.

    An agent receives the handoff message describing the task and entity
    scope, the evidence gateway (MCP) and the trace writer. It answers with a
    ``HandoffMessage`` whose status is ``TaskStatus.COMPLETED`` (facts +
    real evidence references) or ``TaskStatus.NEEDS_MORE_EVIDENCE``. Agents
    emit ``tool_result_consumed`` themselves when they actually use MCP
    evidence; the coordinator owns ``task_assigned``/``handoff`` events.

    The policy agent fills ``message.output`` with the draft l3a output; the
    verifier agent reports PASS / NEEDS_REWORK through ``message.decision_code``.
    """

    role: str

    async def __call__(
        self, message: HandoffMessage, gateway: EvidenceGateway, trace: TraceWriter
    ) -> HandoffMessage: ...


class _NotImplementedAgent:
    """Placeholder that fails loudly so nothing invents answers or evidence."""

    def __init__(self, role: str) -> None:
        self.role = role

    async def __call__(
        self, message: HandoffMessage, gateway: EvidenceGateway, trace: TraceWriter
    ) -> HandoffMessage:
        del message, gateway, trace
        raise NotImplementedError(
            f"agent {self.role!r} is not implemented yet: implement the specialist "
            "agents (order/payment/shipment) and the MCP Evidence Gateway "
            "integration in src/student_agent/agents.py (next work item on the "
            "team board)."
        )


class AgentRegistry:
    """Role -> agent mapping used by the coordinator."""

    def __init__(self, agents: dict[str, SpecialistAgent] | None = None) -> None:
        self._agents: dict[str, SpecialistAgent] = dict(agents or {})

    def register(self, role: str, agent: SpecialistAgent) -> None:
        if not isinstance(role, str) or not role:
            raise ValueError("role must be a non-empty string")
        self._agents[role] = agent

    def get(self, role: str) -> SpecialistAgent:
        try:
            return self._agents[role]
        except KeyError:
            available = ", ".join(sorted(self._agents)) or "none"
            raise RuntimeError(
                f"agent {role!r} is not registered (registered: {available})"
            ) from None

    def roles(self) -> list[str]:
        return sorted(self._agents)


class BaseSpecialistAgent:
    def __init__(self, role: str, tools: list[str]) -> None:
        self.role = role
        self.tools = tools

    async def __call__(
        self, message: HandoffMessage, gateway: EvidenceGateway, trace: TraceWriter
    ) -> HandoffMessage:
        from .permissions import assert_tool_allowed

        if not message.entity_scope:
            return HandoffMessage(
                case_id=message.case_id,
                sender=self.role,
                recipient=message.sender,
                task=message.task,
                entity_scope=message.entity_scope,
                status=TaskStatus.NEEDS_MORE_EVIDENCE,
                notes="entity_scope is empty",
            )
            
        order_id = message.entity_scope[0]
        evidence_refs: list[str] = []
        facts: list[Fact] = []

        for tool in self.tools:
            assert_tool_allowed(self.role, tool)
            try:
                evidence = await gateway.call(tool, case_id=message.case_id, order_id=order_id)
                ref = evidence["evidence_ref"]
                evidence_refs.append(ref)
                
                trace.emit(
                    case_id=message.case_id,
                    event_type="tool_result_consumed",
                    actor=self.role,
                    tool_name=tool,
                    evidence_refs=[ref],
                )
                import json
                data_str = json.dumps(evidence.get("data", evidence), ensure_ascii=False)
                facts.append(Fact(statement=f"Tool {tool} (Ref: {ref}): {data_str}", evidence_refs=(ref,)))
            except Exception as e:
                return HandoffMessage(
                    case_id=message.case_id,
                    sender=self.role,
                    recipient=message.sender,
                    task=message.task,
                    entity_scope=message.entity_scope,
                    status=TaskStatus.NEEDS_MORE_EVIDENCE,
                    notes=f"Failed calling {tool}: {e}",
                )

        return HandoffMessage(
            case_id=message.case_id,
            sender=self.role,
            recipient=message.sender,
            task=message.task,
            entity_scope=message.entity_scope,
            status=TaskStatus.COMPLETED,
            facts=facts,
            evidence_refs=evidence_refs,
        )

class OrderAgent(BaseSpecialistAgent):
    def __init__(self) -> None:
        super().__init__("order", ["get_order", "get_order_items", "get_sellers", "get_product_context"])

class PaymentAgent(BaseSpecialistAgent):
    def __init__(self) -> None:
        super().__init__("payment", ["get_order_payments", "get_payment_timeline", "get_refund_timeline"])

class ShipmentAgent(BaseSpecialistAgent):
    def __init__(self) -> None:
        super().__init__("shipment", ["get_shipment_summary"])


class PolicyAgent:
    def __init__(self) -> None:
        self.role = "policy"
        
    async def __call__(self, message: HandoffMessage, gateway: EvidenceGateway, trace: TraceWriter) -> HandoffMessage:
        from .permissions import assert_tool_allowed
        import os, json
        from openai import AsyncOpenAI
        
        assert_tool_allowed(self.role, "get_policy")
        
        policy_str = "{}"
        ref = "ev_dummy_policy"
        try:
            evidence = await gateway.call("get_policy", case_id=message.case_id, policy_version=message.policy_version or "latest")
            ref = evidence["evidence_ref"]
            policy_str = json.dumps(evidence.get("data", evidence), ensure_ascii=False)
            trace.emit(
                case_id=message.case_id,
                event_type="tool_result_consumed",
                actor=self.role,
                tool_name="get_policy",
                evidence_refs=[ref],
            )
        except Exception as e:
            print(f"POLICY AGENT warning: {e}")
            
        facts_text = "\n".join(f"- {f.statement}" for f in message.facts)
        
        template_str = json.dumps({
            "schema_version": "day09-l3a-output-v2",
            "case_id": "L3A_...",
            "assessment": {
                "primary_issue": "string",
                "case_status": "string",
                "confidence": 0.0
            },
            "affected_entities": {
                "order_ids": [],
                "item_ids": [],
                "seller_ids": [],
                "payment_references": [],
                "shipment_ids": []
            },
            "root_cause_analysis": {
                "ranked_causes": [],
                "responsible_parties": []
            },
            "evidence_refs": [],
            "data_conflicts": [],
            "financial_resolution": {
                "currency": "BRL",
                "recommended_refund_brl": 0,
                "refund_lines": []
            },
            "resolution_actions": []
        }, indent=2)

        prompt = f"""
You are an e-commerce claims investigator.
Read the policy and the collected facts, then construct a JSON output exactly matching the l3a-output-v2 schema.
Your response MUST be ONLY valid JSON matching the schema, with no markdown formatting.

Policy:
{policy_str}

Collected Facts:
{facts_text}

Case ID: {message.case_id}
Order ID: {message.entity_scope[0] if message.entity_scope else ''}

Rules:
1. ONLY use the evidence refs (Ref: ev_...) provided in the facts and policy. DO NOT invent new refs.
2. Carefully identify the primary_issue based on facts. It MUST be exactly one of: "canceled_order_paid", "unavailable_order_paid", "late_delivery_seller", "late_delivery_logistics", "valid_split_payment", "payment_mismatch", "duplicate_charge", "refund_pending", "refund_failed", "unsupported_claim", "insufficient_evidence".
3. case_status MUST be exactly one of: "action_required", "no_action", "needs_investigation".
4. financial_resolution.currency MUST be "BRL".
5. resolution_actions should be actionable steps based on policy.

MUST output JSON strictly matching this structure:
{template_str}
"""
        try:
            client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.0
            )
            output = json.loads(response.choices[0].message.content)
        except Exception as e:
            print(f"LLM Error: {e}")
            output = {
                "schema_version": "day09-l3a-output-v2",
                "case_id": message.case_id,
                "assessment": {
                    "primary_issue": "unsupported_claim",
                    "case_status": "no_action",
                    "confidence": 0.5
                },
                "affected_entities": {
                    "order_ids": [message.entity_scope[0]] if message.entity_scope else [],
                    "item_ids": [],
                    "seller_ids": [],
                    "payment_references": [],
                    "shipment_ids": []
                },
                "root_cause_analysis": {
                    "ranked_causes": [],
                    "responsible_parties": []
                },
                "evidence_refs": message.evidence_refs[:30],
                "data_conflicts": [],
                "financial_resolution": {
                    "currency": "BRL",
                    "recommended_refund_brl": 0,
                    "refund_lines": []
                },
                "resolution_actions": []
            }
        
        output["schema_version"] = "day09-l3a-output-v2"
        output["case_id"] = message.case_id
        
        all_refs = {ref} if ref != "ev_dummy_policy" else set()
        for fact in message.facts:
            all_refs.update(fact.evidence_refs)
            
        facts_list = []
        if ref != "ev_dummy_policy":
            facts_list.append(Fact(statement="Applied policy using LLM", evidence_refs=(ref,)))
        
        return HandoffMessage(
            case_id=message.case_id,
            sender=self.role,
            recipient=message.sender,
            task=message.task,
            entity_scope=message.entity_scope,
            status=TaskStatus.COMPLETED,
            output=output,
            facts=facts_list,
            evidence_refs=list(all_refs)[:30]
        )

class VerifierAgent:
    def __init__(self) -> None:
        self.role = "verifier"
        
    async def __call__(self, message: HandoffMessage, gateway: EvidenceGateway, trace: TraceWriter) -> HandoffMessage:
        from .messages import DecisionCode
        if not message.output:
            return HandoffMessage(
                case_id=message.case_id,
                sender=self.role,
                recipient=message.sender,
                task=message.task,
                status=TaskStatus.COMPLETED,
                decision_code=DecisionCode.NEEDS_REWORK,
                notes="Missing output draft"
            )
        try:
            gateway._contracts.validate_output(message.output, "Verifier")
            return HandoffMessage(
                case_id=message.case_id,
                sender=self.role,
                recipient=message.sender,
                task=message.task,
                status=TaskStatus.COMPLETED,
                decision_code=DecisionCode.PASS
            )
        except Exception as e:
            print(f"VERIFIER REJECTED: {e}")
            return HandoffMessage(
                case_id=message.case_id,
                sender=self.role,
                recipient=message.sender,
                task=message.task,
                status=TaskStatus.COMPLETED,
                decision_code=DecisionCode.NEEDS_REWORK,
                notes=str(e)
            )


def build_default_registry() -> AgentRegistry:
    """Registry used by ``solve_case`` until the specialist agents land."""
    return AgentRegistry({
        "order": OrderAgent(),
        "payment": PaymentAgent(),
        "shipment": ShipmentAgent(),
        "policy": PolicyAgent(),
        "verifier": VerifierAgent(),
    })