"""Tests for entbench.rollout — the boundary an outer optimizer talks through."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import entbench.harness as H
from entbench import rollout
from entbench.harness_files import builtin_harness, export_harness

HIDDEN = (
    "gold_sql",
    "gold_pipeline",
    "gold_extraction",
    "gold_output",
    "gold_plan",
    "gold_workflow",
    "evaluator",
    "bug_patterns",
    "known_trap",
    "antipattern_to_avoid",
    "expected_specialists",
    "difficulty",
)


def test_describe_never_exposes_grading_fields(capsys, monkeypatch):
    monkeypatch.chdir(Path(__file__).resolve().parent.parent)
    assert rollout.main(["describe"]) == 0
    tasks = json.loads(capsys.readouterr().out)
    assert len(tasks) == 54
    for t in tasks:
        assert set(t) <= set(rollout.VISIBLE_FIELDS)
        assert not set(t) & set(HIDDEN)
        assert t["query"] and t["task_class"]


def test_validate_exit_codes(tmp_path, capsys):
    good = export_harness(builtin_harness(), tmp_path / "good")
    assert rollout.main(["validate", "--harness-dir", str(good)]) == 0
    (good / "systemprompt.md").write_text("")
    assert rollout.main(["validate", "--harness-dir", str(good)]) == 2
    assert "systemprompt.md" in capsys.readouterr().err


class _FakeClient:
    def __init__(self, *a, **kw):
        self.calls: list[dict] = []
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kw):
        self.calls.append(kw)
        usage = SimpleNamespace(input_tokens=10, output_tokens=5, cache_read_input_tokens=0)
        if "tools" in kw:
            return SimpleNamespace(
                content=[
                    SimpleNamespace(type="tool_use", input={"collection": "x", "pipeline": []})
                ],
                usage=usage,
            )
        if kw.get("max_tokens") == 10:  # complexity classifier
            return SimpleNamespace(content=[SimpleNamespace(text="SIMPLE")], usage=usage)
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text='{"sql": "SELECT 1"}')], usage=usage
        )


def test_run_writes_ungraded_trace(tmp_path, monkeypatch):
    monkeypatch.chdir(Path(__file__).resolve().parent.parent)
    import anthropic

    monkeypatch.setattr(anthropic, "Anthropic", _FakeClient)

    def _no_grading(*a, **kw):
        raise AssertionError("run must not grade")

    monkeypatch.setattr(H, "evaluate_task", _no_grading)

    run_dir = tmp_path / "r1"
    assert rollout.main(["run", "--task-id", "SQL-001", "--run-dir", str(run_dir)]) == 0
    trace = json.loads((run_dir / rollout.TRACE_FILE).read_text())
    metrics = json.loads((run_dir / rollout.METRICS_FILE).read_text())
    assert trace["task_correct"] is None
    assert trace["node_results"][0]["output"] == {"sql": "SELECT 1"}
    assert metrics["harness"] == "builtin" and metrics["cost_usd"] > 0


def test_run_uses_harness_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(Path(__file__).resolve().parent.parent)
    import anthropic

    seen: list[_FakeClient] = []

    def _factory(*a, **kw):
        c = _FakeClient()
        seen.append(c)
        return c

    monkeypatch.setattr(anthropic, "Anthropic", _factory)
    h = export_harness(builtin_harness(), tmp_path / "h")
    (h / "sub_agents" / "sql_gen" / "AGENT.md").write_text("EDITED SQL PROMPT")
    rollout.main(
        ["run", "--task-id", "SQL-001", "--run-dir", str(tmp_path / "r"), "--harness-dir", str(h)]
    )
    systems = [c["system"][0]["text"] for c in seen[0].calls]
    assert "EDITED SQL PROMPT" in systems


def test_score_reports_verdict(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(Path(__file__).resolve().parent.parent)
    from par.types import WorkflowTrace

    run_dir = tmp_path / "r"
    run_dir.mkdir()
    (run_dir / rollout.TRACE_FILE).write_text(
        WorkflowTrace(task_id="SQL-001", router="par", seed=1).model_dump_json()
    )
    monkeypatch.setattr(H, "evaluate_task", lambda task, trace: task["task_id"] == "SQL-001")
    assert rollout.main(["score", "--task-id", "SQL-001", "--run-dir", str(run_dir)]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out == {"task_id": "SQL-001", "correct": True, "n_passed": 1, "n_criteria": 1}


def test_unknown_task_id_fails(tmp_path, monkeypatch):
    monkeypatch.chdir(Path(__file__).resolve().parent.parent)
    with pytest.raises(SystemExit):
        rollout.main(["score", "--task-id", "NOPE", "--run-dir", str(tmp_path)])
