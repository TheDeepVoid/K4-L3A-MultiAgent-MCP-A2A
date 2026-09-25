"""Invariants between the intent analyzer and the released public contracts.

These tests keep the coordinator's intent mapping from silently drifting if a
public schema is re-released: every hypothesis must be a legal ``primary_issue``
and every legal ``primary_issue`` must be covered by the topic tables.
"""

from __future__ import annotations

import json
from pathlib import Path

from student_agent.agents import SPECIALIST_ROLES
from student_agent.intent import (
    TOPIC_DOMAINS,
    TOPIC_HYPOTHESIS,
    TOPIC_REQUESTED_FULL_REFUND,
)

ROOT = Path(__file__).resolve().parents[1]


def _primary_issue_enum() -> set[str]:
    schema = json.loads(
        (ROOT / "contracts" / "schemas" / "l3a-output-v2.schema.json").read_text(encoding="utf-8")
    )
    return set(schema["$defs"]["primaryIssue"]["enum"])


def test_hypotheses_are_legal_primary_issues() -> None:
    enum = _primary_issue_enum()
    hypotheses = {value for value in TOPIC_HYPOTHESIS.values() if value is not None}
    assert hypotheses <= enum
    assert hypotheses == enum  # full coverage, no drift


def test_topic_tables_cover_the_same_topics() -> None:
    assert set(TOPIC_DOMAINS) == set(TOPIC_HYPOTHESIS)
    assert TOPIC_REQUESTED_FULL_REFUND in TOPIC_DOMAINS
    assert TOPIC_HYPOTHESIS[TOPIC_REQUESTED_FULL_REFUND] is None


def test_every_issue_topic_maps_to_itself() -> None:
    for topic in TOPIC_DOMAINS:
        if topic == TOPIC_REQUESTED_FULL_REFUND:
            continue
        assert TOPIC_HYPOTHESIS[topic] == topic


def test_domains_are_implemented_specialist_roles() -> None:
    domains = set().union(*TOPIC_DOMAINS.values())
    assert domains <= set(SPECIALIST_ROLES)
    assert "order" in domains  # grounding domain is always needed