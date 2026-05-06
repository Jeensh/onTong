"""Authoring agent_tool_adapter — end-to-end persistence tests.

Verifies:
- AuthoringToolCallRow is created at bootstrap
- AuthoringToolLogger writes one row per tool call
- AuthoringOperationalSession records observations as decision rows
- list_tool_calls_for_session round-trips the trace
- A registered tool runs against the live DB and persists the call
"""

from __future__ import annotations

import uuid

import pytest

from backend.application.agent_tools import RunTracker, register_tools
from backend.application.authoring import session as session_mod
from backend.application.authoring.agent_tool_adapter import (
    AuthoringOperationalSession,
    AuthoringToolLogger,
    build_operational_session,
    build_run_tracker,
    list_tool_calls_for_session,
)
from backend.application.authoring.orm import (
    AuthoringDecisionRow,
    AuthoringToolCallRow,
)
from backend.modeling.persistence.database import bootstrap_database, session_scope


@pytest.fixture(scope="module", autouse=True)
def _bootstrap_db() -> None:
    bootstrap_database()


@pytest.fixture
def auth_session_id() -> str:
    sid = session_mod.create_session(operator_id="agent_tools_test", repo_id="dummy")
    return sid


def test_tool_call_table_persists_one_row(auth_session_id: str) -> None:
    logger_obj = AuthoringToolLogger(
        session_id=auth_session_id, turn_no=1, capability="test_cap"
    )
    from backend.application.agent_tools.tracking import ToolCallRecord

    rec = ToolCallRecord(
        tool_name="code_lookup",
        args={"fqn": "com.x.Y"},
        result_summary="dict(fqn,kind)",
        duration_ms=42,
        cached=False,
        error=None,
    )
    logger_obj(rec)

    with session_scope() as s:
        from sqlalchemy import select

        rows = list(
            s.execute(
                select(AuthoringToolCallRow).where(
                    AuthoringToolCallRow.session_id == auth_session_id
                )
            ).scalars()
        )
    assert len(rows) == 1
    assert rows[0].tool_name == "code_lookup"
    assert rows[0].duration_ms == 42
    assert rows[0].capability == "test_cap"


def test_operational_session_writes_observation_decision(
    auth_session_id: str,
) -> None:
    op = AuthoringOperationalSession(
        session_id=auth_session_id, turn_no=1, capability="cap5"
    )
    op.add_observation(
        text="HrPlantConstraint shares PK with HrPlant — likely lookup table",
    )

    with session_scope() as s:
        from sqlalchemy import select

        rows = list(
            s.execute(
                select(AuthoringDecisionRow).where(
                    AuthoringDecisionRow.session_id == auth_session_id
                )
            ).scalars()
        )
    assert any(
        r.step_label == "cap5:observation" and "HrPlantConstraint" in r.payload_json
        for r in rows
    )


def test_user_input_request_marks_needs_user_answer(auth_session_id: str) -> None:
    op = AuthoringOperationalSession(
        session_id=auth_session_id, turn_no=1, capability="cap6"
    )
    op.request_user_input(
        question="What is the meaning of constraintTypeCd values?",
        context="HrPlantConstraint",
    )
    with session_scope() as s:
        from sqlalchemy import select

        rows = list(
            s.execute(
                select(AuthoringDecisionRow).where(
                    AuthoringDecisionRow.session_id == auth_session_id
                )
            ).scalars()
        )
    matching = [r for r in rows if r.step_label == "cap6:user_question"]
    assert matching
    assert "needs_user_answer" in matching[0].payload_json


def test_register_then_run_tool_persists_trace(auth_session_id: str) -> None:
    """End-to-end: register a tool with the authoring logger, invoke it, see DB row."""
    from pydantic_ai import Agent

    agent = Agent("test:test", output_type=str, defer_model_check=True)

    tracker = build_run_tracker(
        session_id=auth_session_id, turn_no=2, capability="hypothesis", max_calls=5
    )
    op_session = build_operational_session(
        session_id=auth_session_id, turn_no=2, capability="hypothesis"
    )
    register_tools(
        agent,
        allowed={"code_lookup"},
        tracker=tracker,
        operational_session=op_session,
    )

    # Manually invoke the wrapped tool through the tracker
    # (we can't make a live LLM call in unit tests). Instead we look up
    # the wrapper via the agent's toolset and call it directly.
    toolset = agent._function_toolset  # type: ignore[attr-defined]
    tool = next(t for t in toolset.tools.values() if t.name == "code_lookup")
    # tool.function is the make_tracked wrapper
    tool.function(fqn="com.does.not.exist")  # graceful None expected

    trace = list_tool_calls_for_session(auth_session_id)
    assert any(
        rec["tool_name"] == "code_lookup" and rec["capability"] == "hypothesis"
        for rec in trace
    )
