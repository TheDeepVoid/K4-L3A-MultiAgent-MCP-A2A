"""Specialist agents backed by the authoritative MCP Evidence Gateway."""

from __future__ import annotations

import json
from typing import Protocol

from .mcp_gateway import EvidenceGateway
from .messages import DecisionCode, Fact, HandoffMessage, TaskStatus
from .permissions import assert_tool_allowed
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


class _McpSpecialistAgent:
    """Call permitted read-only MCP tools and return evidence-linked facts."""

    def __init__(self, role: str, tools: tuple[str, ...]) -> None:
        self.role = role
        self.tools = tools

    async def __call__(
        self, message: HandoffMessage, gateway: EvidenceGateway, trace: TraceWriter
    ) -> HandoffMessage:
        if not message.entity_scope:
            return self._needs_evidence(message, DecisionCode.MCP_REQUEST_REJECTED,
                                        "no order in entity scope")
        if not hasattr(gateway, "call"):
            raise NotImplementedError(
                f"agent {self.role!r} is not implemented for a gateway without call()"
            )

        order_id = message.entity_scope[0]
        available = (
            set(await gateway.list_tools())
            if hasattr(gateway, "list_tools")
            else set(self.tools)
        )
        selected = [tool for tool in self.tools if tool in available]
        if not selected:
            return self._needs_evidence(
                message, DecisionCode.EVIDENCE_NOT_FOUND, "no permitted MCP tool is available"
            )

        facts: list[Fact] = []
        evidence_refs: list[str] = []
        for tool_name in selected:
            assert_tool_allowed(self.role, tool_name)
            try:
                evidence = await gateway.call(
                    tool_name,
                    case_id=message.case_id,
                    order_id=order_id,
                )
            except (TimeoutError, RuntimeError, ValueError) as exc:
                if evidence_refs:
                    break
                return self._needs_evidence(
                    message, DecisionCode.EVIDENCE_NOT_FOUND, f"{tool_name}: {exc}"
                )

            evidence_ref = evidence["evidence_ref"]
            evidence_refs.append(evidence_ref)
            trace.emit(
                case_id=message.case_id,
                event_type="tool_result_consumed",
                actor=self.role,
                tool_name=tool_name,
                evidence_refs=[evidence_ref],
            )
            facts.append(
                Fact(
                    statement=f"{tool_name}: {json.dumps(evidence['data'], sort_keys=True)}",
                    evidence_refs=(evidence_ref,),
                )
            )

        if not evidence_refs:
            return self._needs_evidence(
                message, DecisionCode.EVIDENCE_NOT_FOUND, "MCP returned no usable evidence"
            )
        return HandoffMessage(
            case_id=message.case_id,
            sender=self.role,
            recipient="coordinator",
            task=message.task,
            entity_scope=message.entity_scope,
            facts=facts,
            evidence_refs=evidence_refs,
            status=TaskStatus.COMPLETED,
        )

    def _needs_evidence(
        self, message: HandoffMessage, code: str, notes: str
    ) -> HandoffMessage:
        return HandoffMessage(
            case_id=message.case_id,
            sender=self.role,
            recipient="coordinator",
            task=message.task,
            entity_scope=message.entity_scope,
            status=TaskStatus.NEEDS_MORE_EVIDENCE,
            decision_code=code,
            notes=notes[:160],
        )


class _NotImplementedAgent:
    """Policy/verifier placeholder; they are implemented in the next phase."""

    def __init__(self, role: str) -> None:
        self.role = role

    async def __call__(
        self, message: HandoffMessage, gateway: EvidenceGateway, trace: TraceWriter
    ) -> HandoffMessage:
        del message, gateway, trace
        raise NotImplementedError(f"agent {self.role!r} is not implemented yet")


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


def build_default_registry() -> AgentRegistry:
    """Build the registry with MCP specialists and explicit policy stubs."""
    return AgentRegistry({
        "order": _McpSpecialistAgent(
            "order", ("get_order", "get_order_items", "get_sellers", "get_product_context")
        ),
        "payment": _McpSpecialistAgent(
            "payment", ("get_order_payments", "get_payment_timeline", "get_refund_timeline")
        ),
        "shipment": _McpSpecialistAgent("shipment", ("get_shipment_summary",)),
        "policy": _NotImplementedAgent("policy"),
        "verifier": _NotImplementedAgent("verifier"),
    })