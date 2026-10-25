"""Tests for entbench.harness_files — external harness loading.

The key guarantee: with no harness directory (or the exported base_harness/),
every prompt sent to the model is byte-identical to the prompts that produced
the published EntBench v1 results. tests/v1_prompt_hashes.json holds SHA-256
hashes taken from the original commit, before prompts were moved out of code.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from entbench.harness import make_specialist_registry
from entbench.harness_files import (
    ParHarness,
    builtin_harness,
    export_harness,
    load_harness,
    validate_harness_dir,
)
from par.planner import run_planner
from par.types import Subtask, WorkflowState

REPO = Path(__file__).resolve().parent.parent
GOLDEN = json.loads((Path(__file__).parent / "v1_prompt_hashes.json").read_text())


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _hashes(h: ParHarness) -> dict[str, str]:
    out = {f"specialist:{k}": _sha(v) for k, v in h.specialist_prompts.items()}
    out["planner"] = _sha(h.planner_system)
    out["classifier"] = _sha(h.classifier_prompt)
    return out


# ---------------------------------------------------------------------------
# Byte-identity with v1
# ---------------------------------------------------------------------------


def test_builtin_harness_matches_v1_prompts():
    assert _hashes(builtin_harness()) == GOLDEN


def test_checked_in_base_harness_matches_v1_prompts():
    assert _hashes(load_harness(REPO / "base_harness")) == GOLDEN


def test_export_load_roundtrip(tmp_path):
    h = ParHarness(
        planner_prompt="PLAN",
        classifier_prompt="CLASSIFY",
        specialist_bodies={k: f"body {k}" for k in builtin_harness().specialist_bodies},
        guardrails="Always return JSON.",
        tool_guidance="Dates are ISO.",
        memory="Prefer CTEs.",
    )
    loaded = load_harness(export_harness(h, tmp_path / "h"))
    assert loaded.specialist_prompts == h.specialist_prompts
    assert loaded.planner_system == h.planner_system
    assert loaded.classifier_prompt == h.classifier_prompt


def test_env_var_selects_harness(tmp_path, monkeypatch):
    export_harness(builtin_harness(), tmp_path / "h")
    monkeypatch.setenv("PAR_HARNESS_DIR", str(tmp_path / "h"))
    assert load_harness().source == str(tmp_path / "h")
    monkeypatch.delenv("PAR_HARNESS_DIR")
    assert load_harness().source == "builtin"


# ---------------------------------------------------------------------------
# Composition
# ---------------------------------------------------------------------------


def test_empty_optional_components_add_no_bytes():
    h = builtin_harness()
    assert h.specialist_system("sql_gen") == h.specialist_bodies["sql_gen"]
    assert h.planner_system == h.planner_prompt


def test_optional_components_append_in_order():
    base = builtin_harness()
    h = ParHarness(
        planner_prompt=base.planner_prompt,
        classifier_prompt=base.classifier_prompt,
        specialist_bodies=base.specialist_bodies,
        guardrails="G",
        tool_guidance="T",
        memory="M",
    )
    sql = h.specialist_system("sql_gen")
    assert sql.startswith(base.specialist_bodies["sql_gen"])
    assert sql.index("G") < sql.index("TOOL AND SCHEMA") < sql.index("LESSONS")
    assert h.planner_system.endswith("M")
    assert "G" not in h.planner_system.replace(base.planner_prompt, "")


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_validation_lists_all_problems(tmp_path):
    root = export_harness(builtin_harness(), tmp_path / "h")
    (root / "systemprompt.md").write_text("")
    (root / "sub_agents" / "extract" / "AGENT.md").write_text("---\nmode: subagent\n---\n")
    (root / "skills" / "x").mkdir(parents=True)
    (root / "skills" / "x" / "SKILL.md").write_text("hi")
    (root / "sub_agents" / "rogue").mkdir()
    with pytest.raises(ValueError) as e:
        validate_harness_dir(root)
    msg = str(e.value)
    for needle in ("systemprompt.md", "extract/AGENT.md", "skills/", "rogue"):
        assert needle in msg


def test_readme_stubs_in_unsupported_dirs_are_allowed(tmp_path):
    root = export_harness(builtin_harness(), tmp_path / "h")
    (root / "skills").mkdir()
    (root / "skills" / "README.md").write_text("stub")
    validate_harness_dir(root)


# ---------------------------------------------------------------------------
# Prompts actually reach the API
# ---------------------------------------------------------------------------


class _FakeClient:
    """Records every messages.create call and returns a minimal valid response."""

    def __init__(self, text: str = '{"sql": "SELECT 1"}', tool_input: dict | None = None):
        self.calls: list[dict] = []
        self._text = text
        self._tool_input = tool_input
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kw):
        self.calls.append(kw)
        usage = SimpleNamespace(input_tokens=10, output_tokens=5, cache_read_input_tokens=0)
        if "tools" in kw:
            block = SimpleNamespace(type="tool_use", input=self._tool_input or {})
        else:
            block = SimpleNamespace(type="text", text=self._text)
        return SimpleNamespace(content=[block], usage=usage)


def _subtask(spec: str) -> Subtask:
    return Subtask(id="s1", description="d", specialist=spec, tier="small")


def test_default_registry_sends_v1_prompts():
    client = _FakeClient()
    registry = make_specialist_registry(client)
    for name in ("sql_gen", "extract", "cross_recon", "multitool_plan", "policy_action"):
        registry[name](_subtask(name), "small", {}, client)
    registry["mongo_query"](_subtask("mongo_query"), "small", {}, client)
    sent = [_sha(c["system"][0]["text"]) for c in client.calls]
    expected = [
        GOLDEN[f"specialist:{n}"]
        for n in (
            "sql_gen",
            "extract",
            "cross_recon",
            "multitool_plan",
            "policy_action",
            "mongo_query",
        )
    ]
    assert sent == expected


def test_registry_uses_harness_prompts(tmp_path):
    root = export_harness(builtin_harness(), tmp_path / "h")
    (root / "sub_agents" / "sql_gen" / "AGENT.md").write_text("CUSTOM SQL PROMPT")
    (root / "guardrails.md").write_text("NEVER USE SELECT *")
    client = _FakeClient()
    registry = make_specialist_registry(client, load_harness(root))
    registry["sql_gen"](_subtask("sql_gen"), "small", {}, client)
    system = client.calls[0]["system"][0]["text"]
    assert system.startswith("CUSTOM SQL PROMPT")
    assert "NEVER USE SELECT *" in system


def test_planner_uses_harness_prompts(tmp_path):
    root = export_harness(builtin_harness(), tmp_path / "h")
    (root / "systemprompt.md").write_text("CUSTOM PLANNER")
    (root / "sub_agents" / "complexity_classifier" / "AGENT.md").write_text("CUSTOM CLASSIFIER")
    harness = load_harness(root)

    class _Client(_FakeClient):
        def _create(self, **kw):
            self.calls.append(kw)
            usage = SimpleNamespace(input_tokens=1, output_tokens=1, cache_read_input_tokens=0)
            if "tools" in kw:
                plan = {"subtasks": [_subtask("sql_gen").model_dump()], "cost_rationale": "x"}
                return SimpleNamespace(
                    content=[SimpleNamespace(type="tool_use", input=plan)], usage=usage
                )
            return SimpleNamespace(content=[SimpleNamespace(text="COMPLEX")], usage=usage)

    client = _Client()
    state = WorkflowState(query="q", task_id="t", router="par", seed=1)
    run_planner(state, client, harness=harness)
    assert client.calls[0]["system"][0]["text"] == "CUSTOM CLASSIFIER"
    assert client.calls[1]["system"][0]["text"] == "CUSTOM PLANNER"


def test_no_rationale_ablation_ignores_harness(tmp_path):
    from par.planner import PLANNER_SYSTEM_PROMPT_NO_RATIONALE, _run_full_planner

    client = _FakeClient(tool_input={"subtasks": [_subtask("sql_gen").model_dump()]})
    state = WorkflowState(query="q", task_id="t", router="par_no_rationale", seed=1)
    _run_full_planner(state, client, no_rationale=True, planner_prompt="SHOULD BE IGNORED")
    assert client.calls[0]["system"][0]["text"] == PLANNER_SYSTEM_PROMPT_NO_RATIONALE


def test_specialist_max_tokens_reaches_api():
    """Regression: _call_specialist used to ignore its max_tokens and send 800."""
    client = _FakeClient()
    registry = make_specialist_registry(client)
    registry["sql_gen"](_subtask("sql_gen"), "small", {}, client)
    registry["cross_recon"](_subtask("cross_recon"), "small", {}, client)
    assert [c["max_tokens"] for c in client.calls] == [2000, 1000]
