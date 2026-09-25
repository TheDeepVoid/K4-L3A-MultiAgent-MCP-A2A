from __future__ import annotations

from typing import Any

from .agents import build_default_registry
from .coordinator import Coordinator
from .mcp_gateway import EvidenceGateway
from .trace import TraceWriter


async def solve_case(
    case: dict[str, Any], gateway: EvidenceGateway, trace: TraceWriter
) -> dict[str, Any]:
    """Coordinate the L3A multi-agent workflow for a single case.

    The coordinator analyzes the request intent, plans the specialist tasks
    that the case needs, dispatches them through the agent registry (handoff
    coordination), sends the synthesized facts and evidence to the policy
    agent, and runs the verifier before returning the finalized output.

    The specialist agents and the MCP Evidence Gateway integration are the
    next work item on the team board (implemented in ``agents.py``). Until
    they land, the default registry stubs raise ``NotImplementedError`` so the
    workflow never invents answers or evidence references.
    """
    coordinator = Coordinator(
        case=case,
        gateway=gateway,
        trace=trace,
        registry=build_default_registry(),
    )
    return await coordinator.run()