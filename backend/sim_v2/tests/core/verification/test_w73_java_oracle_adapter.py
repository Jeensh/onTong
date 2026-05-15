"""W73 — Java oracle adapter tests."""
from __future__ import annotations

from backend.sim_v2.core.verification.behavior_twin_runner import BehaviorFixture
from backend.sim_v2.core.verification.java_oracle_adapter import (
    BaselineAttachmentReport,
    JavaBaselineEntry,
    JavaBaselineMap,
    attach_baselines,
)


_SRC = "def f(self, a, b):\n    return a + b\n"


def _fx(fid, args):
    return BehaviorFixture(
        fixture_id=fid, python_source=_SRC, function_name="f",
        input_args=args, input_kwargs={}, expected_output=None,
    )


def test_empty_map_returns_empty_matched():
    fxs = (_fx("f.1", (None, 1, 2)),)
    rep = attach_baselines("a.x", fxs, JavaBaselineMap())
    assert isinstance(rep, BaselineAttachmentReport)
    assert rep.matched_fixtures == ()
    assert rep.unmatched_count == 1
    assert rep.total_fixtures == 1
    assert rep.match_rate == 0.0


def test_single_match_attaches_expected_output():
    m = JavaBaselineMap([
        JavaBaselineEntry("a.x", (None, 1, 2), 3),
    ])
    fxs = (_fx("f.1", (None, 1, 2)),)
    rep = attach_baselines("a.x", fxs, m)
    assert len(rep.matched_fixtures) == 1
    assert rep.matched_fixtures[0].expected_output == 3
    assert rep.unmatched_count == 0
    assert rep.match_rate == 1.0


def test_partial_match_drops_unmatched():
    m = JavaBaselineMap([
        JavaBaselineEntry("a.x", (None, 1, 2), 3),
    ])
    fxs = (
        _fx("f.1", (None, 1, 2)),
        _fx("f.2", (None, 5, 6)),
    )
    rep = attach_baselines("a.x", fxs, m)
    assert len(rep.matched_fixtures) == 1
    assert rep.unmatched_count == 1
    assert rep.matched_fixtures[0].fixture_id == "f.1"


def test_action_scoping_ignores_other_actions():
    m = JavaBaselineMap([
        JavaBaselineEntry("a.x", (None, 1, 2), 99),
    ])
    fxs = (_fx("f.1", (None, 1, 2)),)
    rep = attach_baselines("a.y", fxs, m)   # different action
    assert rep.matched_fixtures == ()
    assert rep.unmatched_count == 1


def test_list_args_are_keyable():
    m = JavaBaselineMap([
        JavaBaselineEntry("a.x", (None, [1, 2, 3]), "ok"),
    ])
    fxs = (_fx("f.1", (None, [1, 2, 3])),)
    rep = attach_baselines("a.x", fxs, m)
    assert len(rep.matched_fixtures) == 1
    assert rep.matched_fixtures[0].expected_output == "ok"


def test_dict_args_are_keyable():
    m = JavaBaselineMap([
        JavaBaselineEntry("a.x", (None, {"k1": 1, "k2": 2}), True),
    ])
    fxs = (_fx("f.1", (None, {"k2": 2, "k1": 1})),)  # different insertion order
    rep = attach_baselines("a.x", fxs, m)
    assert len(rep.matched_fixtures) == 1
    assert rep.matched_fixtures[0].expected_output is True


def test_idempotent_add_overwrites():
    m = JavaBaselineMap()
    m.add(JavaBaselineEntry("a.x", (None, 1), 10))
    m.add(JavaBaselineEntry("a.x", (None, 1), 20))   # overwrite
    assert m.lookup("a.x", (None, 1)).expected_output == 20
    assert len(m) == 1


def test_keys_for_returns_only_matching_action():
    m = JavaBaselineMap([
        JavaBaselineEntry("a.x", (None, 1), "x1"),
        JavaBaselineEntry("a.x", (None, 2), "x2"),
        JavaBaselineEntry("a.y", (None, 1), "y1"),
    ])
    keys = m.keys_for("a.x")
    assert len(keys) == 2


def test_attached_fixture_preserves_metadata():
    """Tolerance, kwargs, trace events should survive the attachment rewrite."""
    fx = BehaviorFixture(
        fixture_id="f.1", python_source=_SRC, function_name="f",
        input_args=(None, 1, 2), input_kwargs={"opt": True},
        expected_output=None, tolerance=0.01,
        expected_trace_events=None, trace_numeric_tolerance=0.0,
    )
    m = JavaBaselineMap([
        JavaBaselineEntry("a.x", (None, 1, 2), 3),
    ])
    rep = attach_baselines("a.x", (fx,), m)
    attached = rep.matched_fixtures[0]
    assert attached.tolerance == 0.01
    assert attached.input_kwargs == {"opt": True}
    assert attached.expected_output == 3


def test_zero_fixtures_yields_zero_match_rate():
    rep = attach_baselines("a.x", (), JavaBaselineMap())
    assert rep.total_fixtures == 0
    assert rep.match_rate == 0.0
