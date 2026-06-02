"""
baselines/frugal_confidence.py — Confidence scorer for the FrugalGPT cascade.

Background
----------
The FrugalGPT cascade (`frugal_cascade_dispatch`) runs each subtask on the
cheapest tier first and escalates to the next tier when the current tier's
answer is judged insufficient. That escalation decision needs a *scoring
function* over the produced answer (Chen et al. 2023, "FrugalGPT").

The original implementation read ``result.output.get("confidence", 1.0)``, but
no specialist ever emits a ``confidence`` key, so the score was always 1.0 and
the cascade never escalated — making FrugalGPT behave identically to AllSmall.

This module supplies a real scorer. Faithful to FrugalGPT's scoring-function
component, but rather than a trained DistilBERT scorer we use a lightweight
LLM judge (the same self-verification technique as AutoMix, Madaan et al. 2023):
a cheap Haiku call inspects the produced output and rates its likely
correctness/completeness on a 0..1 scale.

The judge is itself a real API call, so ``score_confidence`` returns the judge's
token usage alongside the score; the cascade adds that cost to cumulative spend
so FrugalGPT's reported cost honestly includes its scoring overhead.
"""

from __future__ import annotations

import json

import anthropic
from anthropic.types import TextBlock

# The judge runs on the cheapest model so the scorer itself adds minimal cost.
JUDGE_MODEL = "claude-haiku-4-5-20251001"
JUDGE_MAX_TOKENS = 128

# FrugalGPT-style: accept the current tier's answer if confidence >= threshold,
# otherwise escalate to the next tier. Mirrors FRUGAL_CONFIDENCE_THRESHOLD.
FRUGAL_CONFIDENCE_THRESHOLD = 0.70

# Returned for the judge "usage" when no judge call is made (deterministic
# short-circuit) or when the call fails — i.e. zero billable scoring cost.
_ZERO_USAGE: dict[str, int] = {"input_tokens": 0, "output_tokens": 0, "cached_tokens": 0}


def score_confidence(
    client: anthropic.Anthropic,
    subtask_description: str,
    specialist_type: str,
    output: dict | None,
    error: str | None,
) -> tuple[float, dict[str, int]]:
    """
    Return ``(confidence, judge_usage)`` for a specialist's output.

    ``confidence`` is in [0, 1]; ``judge_usage`` is a dict with
    ``input_tokens`` / ``output_tokens`` / ``cached_tokens`` for the judge call
    (all zero when no judge call was made) so the caller can bill the scorer's
    cost via ``compute_cost("small", ...)``.

    Deterministic short-circuits (no LLM call, zero usage):
      - hard error           -> 0.0  (force escalation)
      - empty/missing output -> 0.0  (force escalation)
    """
    # Deterministic signals first — these don't need a judge call.
    if error:
        return 0.0, dict(_ZERO_USAGE)
    if not output:
        return 0.0, dict(_ZERO_USAGE)

    # Serialize the output compactly for the judge.
    try:
        output_str = json.dumps(output, default=str)[:1500]
    except Exception:
        output_str = str(output)[:1500]

    judge_prompt = (
        "You are a strict reviewer scoring whether a specialist agent's output "
        "is likely correct and complete for the given subtask. "
        "Consider: is the output well-formed for the task type, does it appear "
        "to actually answer the subtask (not a refusal, placeholder, or partial "
        "stub), and is it internally consistent? "
        'Respond with ONLY a JSON object of the form {"confidence": <float 0..1>}. '
        "Use a LOW score (<0.5) if the output looks incomplete, malformed, generic, "
        "or likely wrong; a HIGH score (>0.8) only if it looks genuinely correct.\n\n"
        f"SUBTASK ({specialist_type}): {subtask_description}\n\n"
        f"SPECIALIST OUTPUT: {output_str}\n\n"
        "JSON score:"
    )

    try:
        resp = client.messages.create(
            model=JUDGE_MODEL,
            max_tokens=JUDGE_MAX_TOKENS,
            messages=[{"role": "user", "content": judge_prompt}],
        )
        text = "".join(
            block.text for block in resp.content if isinstance(block, TextBlock)
        ).strip()
        usage = {
            "input_tokens": getattr(resp.usage, "input_tokens", 0),
            "output_tokens": getattr(resp.usage, "output_tokens", 0),
            "cached_tokens": getattr(resp.usage, "cache_read_input_tokens", 0) or 0,
        }
        # Be tolerant of code fences / stray text around the JSON.
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            score = float(json.loads(text[start : end + 1]).get("confidence", 0.5))
        else:
            score = 0.5
    except Exception:
        # If the judge call fails, be conservative: mid confidence (no forced
        # escalation, no forced accept). Avoids the old always-1.0 bug.
        return 0.5, dict(_ZERO_USAGE)

    # Clamp.
    return max(0.0, min(1.0, score)), usage
