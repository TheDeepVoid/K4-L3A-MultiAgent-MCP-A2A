"""Coordinator (supervisor) for the L3A workflow.

Owns intent analysis, task planning, handoff coordination, the rework-round
budget, deadline enforcement and the observable handoff trace events.

Responsibilities implemented here (team task: coordinator / supervisor):

- Intent analysis: deterministic plan from the case input (no MCP, no LLM).
- Task planning: which specialist domains a case needs and with which entity
  scope (ARCHITECTURE.md sections 1-3).
- Handoff coordination: dispatch through the ``AgentRegistry``, bounded
  concurrency (default 2), per-task timeout (default 30s) inside the whole-case
  deadline (default 180s), synthesis of facts/evidence for the policy agent.
- Rework budget: at most one supplementary round after the first verification
  (ARCHITECTURE.md section 3), driven by the verifier's NEEDS_REWORK.
- Honesty: never fabricates facts or evidence references. If a draft cannot be
  produced or verified within the budget, a processing error is raised instead
  of inventing an answer.

Trace ownership: CLI emits ``case_received``/``case_finalized``; agents emit
``tool_result_consumed``; the coordinator emits ``task_assigned``,
``handoff``, ``policy_decided`` and ``verification_completed``.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

from .agents import AgentRegistry
from .intent import (
    DOMAIN_ORDER,
    DOMAIN_PAYMENT,
    DOMAIN_SHIPMENT,
    ROLE_COORDINATOR,
    ROLE_POLICY,
    ROLE_VERIFIER,
    CaseAnalysis,
    IntentAnalyzer,
)
from .mcp_gateway import EvidenceGateway
from .messages import DecisionCode, Fact, HandoffMessage, TaskStatus
from .trace import TraceWriter


@dataclass
class CoordinatorConfig:
    # Configuration targets from ARCHITECTURE.md section 7.
    deadline_seconds: float = 180.0
    task_timeout_seconds: float = 30.0
    max_concurrency: int = 2
    max_rework_rounds: int = 1


@dataclass
class _Synthesis:
    facts: list[Fact] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)


class Coordinator:
    def __init__(
        self,
        case: dict[str, Any],
        gateway: EvidenceGateway,
        trace: TraceWriter,
        *,
        registry: AgentRegistry,
        intent: IntentAnalyzer | None = None,
        config: CoordinatorConfig | None = None,
    ) -> None:
        self.case = case
        self.gateway = gateway
        self.trace = trace
        self.registry = registry
        self.intent = intent or IntentAnalyzer()
        self.config = config or CoordinatorConfig()
        self.analysis: CaseAnalysis | None = None
        self._started = time.monotonic()
        self._rework_rounds = 0

    async def run(self) -> dict[str, Any]:
        """Run the supervised workflow for one case and return the output."""
        analysis = self.intent.analyze(self.case)
        self.analysis = analysis
        if self._remaining() <= 0:
            raise RuntimeError("case deadline exceeded before task planning")

        draft = await self._run_specialists_and_policy(self._plan_tasks(analysis))
        while True:
            code = await self._verify(draft)
            if code == DecisionCode.PASS:
                return draft
            if self._rework_rounds >= self.config.max_rework_rounds:
                raise RuntimeError(
                    "verification failed after exhausting the rework budget "
                    f"({self.config.max_rework_rounds} round(s))"
                )
            if self._remaining() <= 0:
                raise RuntimeError("case deadline exceeded during rework")
            self._rework_rounds += 1
            draft = await self._run_specialists_and_policy(
                self._plan_tasks(analysis, rework=True)
            )

    # ------------------------------------------------------------------ time

    def _remaining(self) -> float:
        return self.config.deadline_seconds - (time.monotonic() - self._started)

    # ------------------------------------------------------------- planning

    _DOMAIN_TASKS: dict[str, str] = {
        DOMAIN_ORDER: "verify_order_and_items",
        DOMAIN_PAYMENT: "verify_payment",
        DOMAIN_SHIPMENT: "verify_shipment",
    }

    def _plan_tasks(
        self, analysis: CaseAnalysis, *, rework: bool = False
    ) -> list[HandoffMessage]:
        """Create one pending task per needed specialist domain."""
        plan: list[HandoffMessage] = []
        for domain, task in self._DOMAIN_TASKS.items():
            if not analysis.needs(domain):
                continue
            plan.append(
                HandoffMessage(
                    case_id=analysis.case_id,
                    sender=ROLE_COORDINATOR,
                    recipient=domain,
                    task=task,
                    entity_scope=analysis.entity_scope,
                    policy_version=analysis.policy_version,
                    status=TaskStatus.PENDING,
                )
            )
            attributes: dict[str, str] = {"task": task}
            if rework:
                attributes["rework_round"] = str(self._rework_rounds)
            self.trace.emit(
                case_id=analysis.case_id,
                event_type="task_assigned",
                actor=ROLE_COORDINATOR,
                target=domain,
                decision_code=DecisionCode.SPECIALIST_REWORK if rework else None,
                attributes=attributes,
            )
        return plan

    # -------------------------------------------------------------- dispatch

    async def _run_tasks(self, plan: list[HandoffMessage]) -> list[HandoffMessage]:
        semaphore = asyncio.Semaphore(self.config.max_concurrency)

        async def guarded(task: HandoffMessage) -> HandoffMessage:
            async with semaphore:
                return await self._run_one(task.recipient, task, forward_handoff=False)

        return list(await asyncio.gather(*(guarded(task) for task in plan)))

    async def _run_one(
        self, role: str, message: HandoffMessage, *, forward_handoff: bool
    ) -> HandoffMessage:
        """Run one agent, enforce the task timeout and trace the handoff back."""
        agent = self.registry.get(role)
        remaining = self._remaining()
        if remaining <= 0:
            raise RuntimeError(f"case deadline exceeded before dispatching {role!r}")
        if forward_handoff:
            self.trace.emit(
                case_id=message.case_id,
                event_type="handoff",
                actor=message.sender,
                target=message.recipient,
                decision_code=DecisionCode.HANDOFF_OK,
                attributes={"task": message.task},
            )
        timeout = min(self.config.task_timeout_seconds, remaining)
        try:
            result = await asyncio.wait_for(
                agent(message, self.gateway, self.trace), timeout=timeout
            )
        except TimeoutError:
            result = HandoffMessage(
                case_id=message.case_id,
                sender=role,
                recipient=ROLE_COORDINATOR,
                task=message.task,
                entity_scope=message.entity_scope,
                status=TaskStatus.NEEDS_MORE_EVIDENCE,
                decision_code=DecisionCode.TASK_TIMEOUT,
                notes=f"task {message.task!r} did not finish within {timeout:.1f}s",
            )
        self.trace.emit(
            case_id=result.case_id,
            event_type="handoff",
            actor=result.sender,
            target=result.recipient,
            decision_code=result.decision_code or DecisionCode.HANDOFF_OK,
            attributes={"status": result.status, "task": result.task},
        )
        return result

    # ------------------------------------------------- specialists -> policy

    async def _run_specialists_and_policy(self, plan: list[HandoffMessage]) -> dict[str, Any]:
        assert self.analysis is not None
        analysis = self.analysis
        results = await self._run_tasks(plan)
        synthesis = self._synthesize(results)

        policy_message = HandoffMessage(
            case_id=analysis.case_id,
            sender=ROLE_COORDINATOR,
            recipient=ROLE_POLICY,
            task="apply_policy",
            entity_scope=analysis.entity_scope,
            facts=synthesis.facts,
            evidence_refs=synthesis.evidence_refs,
            policy_version=analysis.policy_version,
            status=TaskStatus.PENDING,
            notes="; ".join(synthesis.missing) if synthesis.missing else None,
        )
        policy_result = await self._run_one(ROLE_POLICY, policy_message, forward_handoff=True)
        if not policy_result.is_completed or not policy_result.output:
            raise RuntimeError(
                "policy agent did not produce a draft output "
                f"({policy_result.decision_code or 'no output'})"
            )
        self.trace.emit(
            case_id=analysis.case_id,
            event_type="policy_decided",
            actor=ROLE_POLICY,
            decision_code=DecisionCode.POLICY_DRAFT_READY,
        )
        return policy_result.output

    @staticmethod
    def _synthesize(results: list[HandoffMessage]) -> _Synthesis:
        synthesis = _Synthesis()
        for result in results:
            if result.is_completed:
                synthesis.facts.extend(result.facts)
                synthesis.evidence_refs.extend(result.all_evidence_refs())
            else:
                note = result.notes or result.decision_code or TaskStatus.NEEDS_MORE_EVIDENCE
                synthesis.missing.append(f"{result.sender}:{result.task} -> {note}")
        synthesis.evidence_refs = list(dict.fromkeys(synthesis.evidence_refs))
        return synthesis

    # ------------------------------------------------------------- verifier

    async def _verify(self, draft: dict[str, Any]) -> str:
        assert self.analysis is not None
        analysis = self.analysis
        message = HandoffMessage(
            case_id=analysis.case_id,
            sender=ROLE_POLICY,
            recipient=ROLE_VERIFIER,
            task="verify_draft",
            entity_scope=analysis.entity_scope,
            policy_version=analysis.policy_version,
            status=TaskStatus.PENDING,
            output=draft,
        )
        result = await self._run_one(ROLE_VERIFIER, message, forward_handoff=True)
        code = result.decision_code or DecisionCode.NEEDS_REWORK
        if code == DecisionCode.PASS:
            self.trace.emit(
                case_id=analysis.case_id,
                event_type="verification_completed",
                actor=ROLE_VERIFIER,
                decision_code=DecisionCode.PASS,
            )
            return code
        errors = (result.notes or "").strip()
        self.trace.emit(
            case_id=analysis.case_id,
            event_type="verification_completed",
            actor=ROLE_VERIFIER,
            decision_code=DecisionCode.NEEDS_REWORK,
            attributes={"errors": errors[:160]} if errors else None,
        )
        return code


async def investigate_order(
    case: dict[str, Any],
    gateway: EvidenceGateway,
    trace: TraceWriter,
):
    """Compatibility path for the evidence-backed specialist implementation."""
    from .a2a import AgentMessage
    from .evidence import EvidenceCollector
    from .observability import record_message
    from .order_agent import inspect_order
    from .payment_agent import inspect_payment
    from .shipment_agent import inspect_shipment
    from .state import create_case_state

    state = create_case_state(case)
    topics = {claim["topic"] for claim in case["customer_request"]["claims"]}
    needs_shipment = bool(
        topics & {"late_delivery_logistics", "late_delivery_seller"}
    )
    collector = EvidenceCollector(gateway, state)
    async with asyncio.timeout_at(state.deadline):
        async with asyncio.timeout(
            min(30.0, state.deadline - asyncio.get_running_loop().time())
        ):
            available_tools = set(await gateway.list_tools())
        required_tools = {"get_order", "get_payment_timeline"}
        if needs_shipment:
            required_tools.add("get_shipment_summary")
        missing_tools = required_tools - available_tools
        if missing_tools:
            raise RuntimeError(f"Required MCP tools unavailable: {sorted(missing_tools)}")

        scope = {"order_ids": list(state.entity_scope["order_ids"])}
        assignments = [
            ("order-item-agent", "Verify order identity and status", inspect_order),
            ("payment-agent", "Verify payment timeline for the scoped order", inspect_payment),
        ]
        if needs_shipment:
            assignments.append(
                ("shipment-agent", "Verify shipment timeline and shipping limits", inspect_shipment)
            )
        for recipient, task, agent in assignments:
            record_message(
                state,
                trace,
                AgentMessage(
                    case_id=state.case_id,
                    sender="coordinator",
                    recipient=recipient,
                    task=task,
                    entity_scope=scope,
                    status="pending",
                ),
            )
            record_message(state, trace, await agent(state, collector, trace))
    return state
