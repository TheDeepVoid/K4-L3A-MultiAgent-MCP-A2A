"""Internal A2A handoff messages.

These messages implement the handoff protocol described in ARCHITECTURE.md
section 3. They are internal to the workflow: they are never written verbatim
to the public output or to the MCP evidence envelope.

The coordinator (supervisor) creates the task messages and collects the
result messages; specialist agents answer through the same envelope so every
handoff carries the same ``case_id`` and an explicit entity scope.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class TaskStatus:
    """Lifecycle of an internal handoff message."""

    PENDING = "pending"
    COMPLETED = "completed"
    NEEDS_MORE_EVIDENCE = "needs_more_evidence"
    FAILED = "failed"


class DecisionCode:
    """Internal decision codes annotating handoff / verification events.

    These are internal conventions (ARCHITECTURE.md section 5) and are only
    allowed to appear in observable trace events through ``decision_code``;
    they are not part of any public contract.
    """

    HANDOFF_OK = "HANDOFF_OK"
    EVIDENCE_NOT_FOUND = "EVIDENCE_NOT_FOUND"
    MCP_TEMPORARY_RETRY = "MCP_TEMPORARY_RETRY"
    MCP_REQUEST_REJECTED = "MCP_REQUEST_REJECTED"
    INVALID_EVIDENCE_ENVELOPE = "INVALID_EVIDENCE_ENVELOPE"
    SOURCE_CONFLICT = "SOURCE_CONFLICT"
    SPECIALIST_REWORK = "SPECIALIST_REWORK"
    TASK_TIMEOUT = "TASK_TIMEOUT"
    POLICY_DRAFT_READY = "POLICY_DRAFT_READY"
    PASS = "PASS"
    NEEDS_REWORK = "NEEDS_REWORK"


@dataclass(frozen=True)
class Fact:
    """A verified fact produced by a specialist, linked to real evidence."""

    statement: str
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        refs = tuple(dict.fromkeys(self.evidence_refs))
        object.__setattr__(self, "evidence_refs", refs)
        if len(refs) > 20:
            raise ValueError("a single fact may reference at most 20 evidence entries")


@dataclass
class HandoffMessage:
    """Internal handoff message (ARCHITECTURE.md section 3).

    ``output`` carries the l3a output draft produced by the policy agent and
    consumed by the verifier; it is never copied verbatim into the public
    trace. ``policy_version`` is an internal extension used to hand the
    input-provided policy version to the policy agent (never guessed).
    """

    case_id: str
    sender: str
    recipient: str
    task: str
    entity_scope: tuple[str, ...] = ()
    facts: list[Fact] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
    status: str = TaskStatus.PENDING
    decision_code: str | None = None
    notes: str | None = None
    policy_version: str | None = None
    output: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        self.entity_scope = tuple(dict.fromkeys(self.entity_scope))
        self.evidence_refs = list(dict.fromkeys(self.evidence_refs))
        if len(self.evidence_refs) > 30:
            raise ValueError("a handoff message may carry at most 30 evidence references")

    @property
    def is_completed(self) -> bool:
        return self.status == TaskStatus.COMPLETED

    def all_evidence_refs(self) -> list[str]:
        """Unique evidence references from the message and its facts."""
        refs: list[str] = list(self.evidence_refs)
        for fact in self.facts:
            refs.extend(fact.evidence_refs)
        return list(dict.fromkeys(refs))