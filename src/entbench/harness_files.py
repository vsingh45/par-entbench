"""
entbench/harness_files.py — Load PaR's prompts from an external harness directory.

The harness is the editable layer around the models: the planner prompt, the
specialist prompts, and shared guidance. Keeping it in files (rather than Python
constants) lets an outer optimizer such as Harness² propose and test edits
without touching code.

Directory layout (names follow Harness²'s c1..c8 component tree so its tree
tooling can read, diff and validate a PaR harness unchanged):

    systemprompt.md                         c1  planner system prompt
    guardrails.md                           c2  rules appended to every specialist
    LongTermMEMORY.md                       c3  lessons appended to planner + specialists
    tool_descriptions/tool_guidance.md      c4  tool/schema guidance appended to specialists
    sub_agents/<specialist>/AGENT.md        c5  one specialist prompt each (frontmatter optional)
    sub_agents/complexity_classifier/AGENT.md   the cascade's SIMPLE/COMPLEX classifier

c6 (skills), c7 (scripts) and c8 (plugins) have no PaR executor equivalent yet;
`validate_harness_dir` rejects them so an optimizer cannot spend budget on
components that would be silently ignored.

Composition is additive and byte-preserving: with empty or missing c2/c3/c4
files, every composed prompt is identical to the built-in constants that produced
the published EntBench v1 results. `builtin_harness()` is that default.

The PaR-no-rationale ablation prompt is deliberately NOT part of the harness;
it stays a fixed code constant so the ablation is not perturbed by refinement.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from entbench.specialist_prompts import SPECIALIST_PROMPTS
from par.planner import COMPLEXITY_CLASSIFIER_PROMPT, PLANNER_SYSTEM_PROMPT

HARNESS_DIR_ENV = "PAR_HARNESS_DIR"

PLANNER_FILE = "systemprompt.md"
GUARDRAILS_FILE = "guardrails.md"
MEMORY_FILE = "LongTermMEMORY.md"
TOOL_GUIDANCE_FILE = "tool_descriptions/tool_guidance.md"
SUBAGENT_DIR = "sub_agents"
CLASSIFIER_NAME = "complexity_classifier"

UNSUPPORTED_DIRS = ("skills", "scripts", "plugin")

# Section headers used when appending optional components. Only emitted when the
# component is non-empty, so the default composition adds no bytes.
_GUARDRAILS_HEADER = "\n\nADDITIONAL RULES:\n"
_TOOL_GUIDANCE_HEADER = "\n\nTOOL AND SCHEMA GUIDANCE:\n"
_MEMORY_HEADER = "\n\nLESSONS FROM PREVIOUS TASKS:\n"

_FRONTMATTER = re.compile(r"\A---\n.*?\n---\n", re.S)


@dataclass(frozen=True)
class ParHarness:
    """One complete PaR harness. Raw components; use the properties for composed prompts."""

    planner_prompt: str
    classifier_prompt: str
    specialist_bodies: dict[str, str]
    guardrails: str = ""
    tool_guidance: str = ""
    memory: str = ""
    source: str = "builtin"
    extra: dict[str, str] = field(default_factory=dict)

    @property
    def planner_system(self) -> str:
        """Planner system prompt: c1 + optional c3 lessons."""
        out = self.planner_prompt
        if self.memory.strip():
            out += _MEMORY_HEADER + self.memory.strip()
        return out

    def specialist_system(self, name: str) -> str:
        """Specialist system prompt: c5 body + optional c2, c4, c3 (in that order)."""
        out = self.specialist_bodies[name]
        if self.guardrails.strip():
            out += _GUARDRAILS_HEADER + self.guardrails.strip()
        if self.tool_guidance.strip():
            out += _TOOL_GUIDANCE_HEADER + self.tool_guidance.strip()
        if self.memory.strip():
            out += _MEMORY_HEADER + self.memory.strip()
        return out

    @property
    def specialist_prompts(self) -> dict[str, str]:
        """Composed system prompt for every specialist, keyed by specialist name."""
        return {name: self.specialist_system(name) for name in self.specialist_bodies}


def builtin_harness() -> ParHarness:
    """The harness that produced the published EntBench v1 results."""
    return ParHarness(
        planner_prompt=PLANNER_SYSTEM_PROMPT,
        classifier_prompt=COMPLEXITY_CLASSIFIER_PROMPT,
        specialist_bodies=dict(SPECIALIST_PROMPTS),
    )


def _strip_frontmatter(text: str) -> str:
    return _FRONTMATTER.sub("", text, count=1)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def validate_harness_dir(harness_dir: Path) -> None:
    """Raise ValueError listing every problem, in prose an optimizer can act on."""
    problems: list[str] = []
    if not harness_dir.is_dir():
        raise ValueError(f"harness directory {harness_dir} does not exist")

    if not _read(harness_dir / PLANNER_FILE).strip():
        problems.append(f"{PLANNER_FILE} is missing or empty; the planner needs a system prompt.")

    for name in SPECIALIST_PROMPTS:
        agent = harness_dir / SUBAGENT_DIR / name / "AGENT.md"
        if not _strip_frontmatter(_read(agent)).strip():
            problems.append(f"{SUBAGENT_DIR}/{name}/AGENT.md is missing or empty.")

    for d in UNSUPPORTED_DIRS:
        p = harness_dir / d
        if p.is_dir() and any(f.name != "README.md" for f in p.rglob("*") if f.is_file()):
            problems.append(
                f"{d}/ is not supported by the PaR executor yet; content there would be "
                f"ignored. Put the guidance in guardrails.md or a sub_agents/<name>/AGENT.md."
            )

    known = set(SPECIALIST_PROMPTS) | {CLASSIFIER_NAME}
    sub = harness_dir / SUBAGENT_DIR
    if sub.is_dir():
        for child in sub.iterdir():
            if child.is_dir() and child.name not in known:
                problems.append(
                    f"{SUBAGENT_DIR}/{child.name}/ is not a PaR specialist; the planner can "
                    f"only route to: {', '.join(sorted(SPECIALIST_PROMPTS))}."
                )

    if problems:
        raise ValueError("Invalid PaR harness:\n- " + "\n- ".join(problems))


def load_harness(harness_dir: str | Path | None = None) -> ParHarness:
    """Load a harness from a directory, or the built-in one.

    Resolution order: explicit argument, then $PAR_HARNESS_DIR, then built-in.
    A missing classifier AGENT.md falls back to the built-in classifier prompt.
    """
    if harness_dir is None:
        harness_dir = os.environ.get(HARNESS_DIR_ENV) or None
    if harness_dir is None:
        return builtin_harness()

    root = Path(harness_dir)
    validate_harness_dir(root)

    bodies = {
        name: _strip_frontmatter(_read(root / SUBAGENT_DIR / name / "AGENT.md"))
        for name in SPECIALIST_PROMPTS
    }
    classifier = _strip_frontmatter(_read(root / SUBAGENT_DIR / CLASSIFIER_NAME / "AGENT.md"))

    return ParHarness(
        planner_prompt=_read(root / PLANNER_FILE),
        classifier_prompt=classifier or COMPLEXITY_CLASSIFIER_PROMPT,
        specialist_bodies=bodies,
        guardrails=_read(root / GUARDRAILS_FILE),
        tool_guidance=_read(root / TOOL_GUIDANCE_FILE),
        memory=_read(root / MEMORY_FILE),
        source=str(root),
    )


_SPECIALIST_DESCRIPTIONS = {
    "sql_gen": "Generates one Postgres SQL query against the EntBench warehouse.",
    "mongo_query": "Generates one MongoDB aggregation pipeline over the SAM collections.",
    "extract": "Extracts structured fields from a document as JSON.",
    "cross_recon": "Reconciles MongoDB state with SQL history and classifies each entity.",
    "multitool_plan": "Produces a tool-call plan from the enterprise tool registry.",
    "policy_action": "Evaluates an action against a policy registry and selects a decision.",
    CLASSIFIER_NAME: "Classifies a query as SIMPLE or COMPLEX for the planner cascade.",
}


def export_harness(harness: ParHarness, out_dir: str | Path) -> Path:
    """Write a harness to disk in the layout above. Round-trips through load_harness."""
    root = Path(out_dir)
    (root / "tool_descriptions").mkdir(parents=True, exist_ok=True)
    (root / PLANNER_FILE).write_text(harness.planner_prompt, encoding="utf-8")
    (root / GUARDRAILS_FILE).write_text(harness.guardrails, encoding="utf-8")
    (root / MEMORY_FILE).write_text(harness.memory, encoding="utf-8")
    (root / TOOL_GUIDANCE_FILE).write_text(harness.tool_guidance, encoding="utf-8")

    agents = dict(harness.specialist_bodies)
    agents[CLASSIFIER_NAME] = harness.classifier_prompt
    for name, body in agents.items():
        d = root / SUBAGENT_DIR / name
        d.mkdir(parents=True, exist_ok=True)
        front = (
            f"---\nmode: subagent\ndescription: {_SPECIALIST_DESCRIPTIONS.get(name, name)}\n---\n"
        )
        (d / "AGENT.md").write_text(front + body, encoding="utf-8")
    return root
