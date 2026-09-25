from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from student_agent.agents import AgentRegistry, build_default_registry
from student_agent.contracts import Contracts
from student_agent.coordinator import Coordinator, CoordinatorConfig
from student_agent.messages import DecisionCode, Fact, HandoffMessage, TaskStatus
from student_agent.trace import TraceWriter

ROOT = Path(__file__).resolve().parents[1]
CASE_ID = "L3A_CASE_999"
ORDER_ID = "ord_123"
EV1 = "ev_" + ("E" * 40)
EV2 = "ev_" + ("F" * 40)


def make_case(topic: str = "canceled_order_paid") -> dict:
    return {
        "case_id": CASE_ID,
        "opened_at": "2018-01-01T09:00:00-03:00",
        "customer_request": {
            "language": "vi",
            "message": "mẫu yêu cầu",
            "claimed_order_id": ORDER_ID,
            "claims": [
                {"claim_id": "claim-a", "topic": topic},
                {"claim_id": "claim-b", "topic": "requested_full_refund"},
            ],
        },
        "policy_version": "EC_POLICY_V1",
    }


def make_draft(case_id: str, evidence_refs: list[str]) -> dict:
    return {
        "schema_version": "day09-l3a-output-v2",
        "case_id": case_id,
        "assessment": {
            "primary_issue": "canceled_order_paid",
            "case_status": "action_required",
            "confidence": 0.9,
        },
        "affected_entities": {
            "order_ids": [ORDER_ID],
            "item_ids": [],
            "seller_ids": [],
            "payment_references": [],
            "shipment_ids": [],
        },
        "root_cause_analysis": {
            "ranked_causes": [{"cause_code": "ORDER_CANCELED_AFTER_PAYMENT", "rank": 1}],
            "responsible_parties": [{"party_type": "platform", "party_id": None}],
        },
        "evidence_refs": evidence_refs,
        "data_conflicts": [],
        "financial_resolution": {
            "currency": "BRL",
            "recommended_refund_brl": 0.0,
            "refund_lines": [],
        },
        "resolution_actions": ["issue full refund to customer"],
    }


async def fake_order(
    message: HandoffMessage, gateway, trace: TraceWriter
) -> HandoffMessage:
    del gateway
    trace.emit(
        case_id=message.case_id,
        event_type="tool_result_consumed",
        actor="order",
        tool_name="get_order",
        evidence_refs=[EV1],
    )
    return HandoffMessage(
        case_id=message.case_id,
        sender="order",
        recipient="coordinator",
        task=message.task,
        entity_scope=message.entity_scope,
        status=TaskStatus.COMPLETED,
        facts=[Fact("order canceled after payment", (EV1,))],
        evidence_refs=[EV1],
    )


async def fake_payment(
    message: HandoffMessage, gateway, trace: TraceWriter
) -> HandoffMessage:
    del gateway
    trace.emit(
        case_id=message.case_id,
        event_type="tool_result_consumed",
        actor="payment",
        tool_name="get_order_payments",
        evidence_refs=[EV2],
    )
    return HandoffMessage(
        case_id=message.case_id,
        sender="payment",
        recipient="coordinator",
        task=message.task,
        entity_scope=message.entity_scope,
        status=TaskStatus.COMPLETED,
        facts=[Fact("payment captured", (EV2,))],
        evidence_refs=[EV2],
    )


async def fake_policy(
    message: HandoffMessage, gateway, trace: TraceWriter
) -> HandoffMessage:
    del gateway, trace
    return HandoffMessage(
        case_id=message.case_id,
        sender="policy",
        recipient="coordinator",
        task=message.task,
        entity_scope=message.entity_scope,
        status=TaskStatus.COMPLETED,
        evidence_refs=message.all_evidence_refs(),
        output=make_draft(message.case_id, message.all_evidence_refs()[:1]),
    )


def make_verifier(fail_times: int = 0):
    state = {"calls": 0}

    async def verifier(message: HandoffMessage, gateway, trace: TraceWriter) -> HandoffMessage:
        del gateway, trace
        state["calls"] += 1
        if state["calls"] <= fail_times:
            return HandoffMessage(
                case_id=message.case_id,
                sender="verifier",
                recipient="coordinator",
                task=message.task,
                status=TaskStatus.COMPLETED,
                decision_code=DecisionCode.NEEDS_REWORK,
                notes="missing payment evidence",
            )
        return HandoffMessage(
            case_id=message.case_id,
            sender="verifier",
            recipient="coordinator",
            task=message.task,
            status=TaskStatus.COMPLETED,
            decision_code=DecisionCode.PASS,
        )

    return verifier


def make_registry(
    *,
    order=fake_order,
    payment=fake_payment,
    policy=fake_policy,
    verifier=None,
) -> AgentRegistry:
    registry_verifier = verifier if verifier is not None else make_verifier(0)
    return AgentRegistry(
        {
            "order": order,
            "payment": payment,
            "policy": policy,
            "verifier": registry_verifier,
        }
    )


def read_events(path: Path) -> list[dict]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def counts(events: list[dict]) -> dict[str, int]:
    result: dict[str, int] = {}
    for event in events:
        result[event["event_type"]] = result.get(event["event_type"], 0) + 1
    return result


async def run_coordinator(
    tmp_path: Path,
    registry: AgentRegistry,
    *,
    case: dict | None = None,
    config: CoordinatorConfig | None = None,
) -> tuple[dict, list[dict]]:
    contracts = Contracts(ROOT / "contracts" / "schemas")
    trace = TraceWriter(tmp_path / "trace.jsonl", contracts)
    coordinator = Coordinator(
        case=case or make_case(),
        gateway=object(),
        trace=trace,
        registry=registry,
        config=config or CoordinatorConfig(),
    )
    output = await coordinator.run()
    return output, read_events(trace.path)


def test_full_flow_pass(tmp_path: Path) -> None:
    output, events = asyncio.run(run_coordinator(tmp_path, make_registry()))
    contracts = Contracts(ROOT / "contracts" / "schemas")
    contracts.validate_output(output, "test output")
    assert output["case_id"] == CASE_ID

    type_counts = counts(events)
    assert type_counts["task_assigned"] == 2  # order + payment
    assert type_counts["handoff"] == 6
    assert type_counts["policy_decided"] == 1
    assert type_counts["verification_completed"] == 1
    assert type_counts["tool_result_consumed"] == 2
    assert [e["decision_code"] for e in events if e["event_type"] == "verification_completed"] == [
        DecisionCode.PASS
    ]
    # CLI owns the case lifecycle events; the coordinator must not duplicate them.
    assert "case_received" not in type_counts
    assert "case_finalized" not in type_counts
    # Every specialist handoff is attributed to its sender.
    handoff_actors = {e["actor"] for e in events if e["event_type"] == "handoff"}
    assert handoff_actors == {"order", "payment", "coordinator", "policy", "verifier"}


def test_needs_more_evidence_is_recorded_not_fabricated(tmp_path: Path) -> None:
    async def missing_payment(
        message: HandoffMessage, gateway: object, trace: TraceWriter
    ) -> HandoffMessage:
        del gateway, trace
        return HandoffMessage(
            case_id=message.case_id,
            sender="payment",
            recipient="coordinator",
            task=message.task,
            entity_scope=message.entity_scope,
            status=TaskStatus.NEEDS_MORE_EVIDENCE,
            decision_code=DecisionCode.EVIDENCE_NOT_FOUND,
            notes="no payment record found",
        )

    registry = make_registry(payment=missing_payment)
    output, events = asyncio.run(run_coordinator(tmp_path, registry))
    assert output["case_id"] == CASE_ID
    codes = {e.get("decision_code") for e in events if e["event_type"] == "handoff"}
    assert DecisionCode.EVIDENCE_NOT_FOUND in codes
    # No extra rework is triggered by a specialist needs_more_evidence report.
    assert counts(events)["verification_completed"] == 1


def test_rework_round_runs_once_then_passes(tmp_path: Path) -> None:
    registry = make_registry(verifier=make_verifier(fail_times=1))
    output, events = asyncio.run(run_coordinator(tmp_path, registry))
    assert output["case_id"] == CASE_ID

    type_counts = counts(events)
    assert type_counts["task_assigned"] == 4  # 2 initial + 2 rework
    assert type_counts["policy_decided"] == 2
    verification = [e for e in events if e["event_type"] == "verification_completed"]
    check_codes = [e["decision_code"] for e in verification]
    assert check_codes == [DecisionCode.NEEDS_REWORK, DecisionCode.PASS]
    rework_assignments = [
        e
        for e in events
        if e["event_type"] == "task_assigned"
        and e.get("decision_code") == DecisionCode.SPECIALIST_REWORK
    ]
    assert len(rework_assignments) == 2
    assert all(e["attributes"]["rework_round"] == "1" for e in rework_assignments)


def test_rework_budget_exhausted_raises(tmp_path: Path) -> None:
    registry = make_registry(verifier=make_verifier(fail_times=99))
    with pytest.raises(RuntimeError, match="rework budget"):
        asyncio.run(run_coordinator(tmp_path, registry))
    events = read_events(tmp_path / "trace.jsonl")
    verification = [e for e in events if e["event_type"] == "verification_completed"]
    assert len(verification) == 2  # first check + the single allowed rework round


def test_deadline_exceeded_raises_without_output(tmp_path: Path) -> None:
    config = CoordinatorConfig(deadline_seconds=0.0)
    with pytest.raises(RuntimeError, match="deadline"):
        asyncio.run(run_coordinator(tmp_path, make_registry(), config=config))


def test_task_timeout_becomes_missing_evidence(tmp_path: Path) -> None:
    async def slow_order(message: HandoffMessage, gateway, trace: TraceWriter) -> HandoffMessage:
        del gateway, trace
        await asyncio.sleep(1.0)
        raise AssertionError("must be cancelled by the task timeout")

    config = CoordinatorConfig(task_timeout_seconds=0.05, deadline_seconds=60.0)
    registry = make_registry(order=slow_order)
    output, events = asyncio.run(run_coordinator(tmp_path, registry, config=config))
    assert output["case_id"] == CASE_ID
    codes = {e.get("decision_code") for e in events if e["event_type"] == "handoff"}
    assert DecisionCode.TASK_TIMEOUT in codes
    assert counts(events)["verification_completed"] == 1


def test_policy_without_draft_raises_honest_error(tmp_path: Path) -> None:
    async def empty_policy(message: HandoffMessage, gateway, trace: TraceWriter) -> HandoffMessage:
        del message, gateway, trace
        return HandoffMessage(
            case_id=CASE_ID,
            sender="policy",
            recipient="coordinator",
            task="apply_policy",
            status=TaskStatus.NEEDS_MORE_EVIDENCE,
            decision_code=DecisionCode.EVIDENCE_NOT_FOUND,
        )

    registry = make_registry(policy=empty_policy)
    with pytest.raises(RuntimeError, match="policy agent did not produce"):
        asyncio.run(run_coordinator(tmp_path, registry))


@pytest.mark.skip(reason="Stubs are removed")
def test_default_registry_stubs_fail_loudly(tmp_path: Path) -> None:
    """Documents the handoff state: stubs raise until the next work item lands."""
    contracts = Contracts(ROOT / "contracts" / "schemas")
    trace = TraceWriter(tmp_path / "trace.jsonl", contracts)
    coordinator = Coordinator(
        case=make_case(),
        gateway=object(),
        trace=trace,
        registry=build_default_registry(),
    )
    with pytest.raises(NotImplementedError, match="not implemented"):
        asyncio.run(coordinator.run())


def test_unregistered_agent_raises(tmp_path: Path) -> None:
    registry = AgentRegistry({"policy": fake_policy, "verifier": make_verifier(0)})
    with pytest.raises(RuntimeError, match="not registered"):
        asyncio.run(run_coordinator(tmp_path, registry))