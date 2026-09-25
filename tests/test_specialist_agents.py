from __future__ import annotations

import asyncio
import json
from pathlib import Path

from student_agent.agents import build_default_registry
from student_agent.contracts import Contracts
from student_agent.messages import HandoffMessage, TaskStatus
from student_agent.trace import TraceWriter

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_REF = "ev_" + ("A" * 40)


class FakeGateway:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []

    async def list_tools(self) -> list[str]:
        return ["get_order"]

    async def call(self, tool_name: str, *, case_id: str, order_id: str) -> dict:
        self.calls.append((tool_name, case_id, order_id))
        return {
            "schema_version": "day09-mcp-evidence-v1",
            "evidence_ref": EVIDENCE_REF,
            "result_hash": "sha256:" + ("a" * 64),
            "domain": "order",
            "data": {"order_id": order_id, "order_status": "delivered"},
        }


def test_order_agent_preserves_case_scope_and_audits_evidence(tmp_path: Path) -> None:
    async def run() -> tuple[HandoffMessage, FakeGateway, list[dict]]:
        gateway = FakeGateway()
        trace = TraceWriter(tmp_path / "trace.jsonl", Contracts(ROOT / "contracts" / "schemas"))
        message = HandoffMessage(
            case_id="L3A_CASE_999",
            sender="coordinator",
            recipient="order",
            task="verify_order_and_items",
            entity_scope=("ord_123",),
            status=TaskStatus.PENDING,
        )
        result = await build_default_registry().get("order")(message, gateway, trace)
        events = [
            json.loads(line)
            for line in trace.path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        return result, gateway, events

    result, gateway, events = asyncio.run(run())

    assert gateway.calls == [("get_order", "L3A_CASE_999", "ord_123")]
    assert result.status == TaskStatus.COMPLETED
    assert result.evidence_refs == [EVIDENCE_REF]
    assert result.facts[0].evidence_refs == (EVIDENCE_REF,)
    assert events[0]["event_type"] == "tool_result_consumed"
    assert events[0]["case_id"] == "L3A_CASE_999"
    assert events[0]["evidence_refs"] == [EVIDENCE_REF]
