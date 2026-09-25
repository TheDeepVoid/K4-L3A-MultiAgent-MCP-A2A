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
from .messages import HandoffMessage
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


def build_default_registry() -> AgentRegistry:
    """Registry used by ``solve_case`` until the specialist agents land."""
    return AgentRegistry({role: _NotImplementedAgent(role) for role in ALL_ROLES})