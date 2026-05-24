"""Reusable structured assessment (spec §12 — the assessment surface).

Evaluates a transcript or a document against a rubric and returns a structured
result (score 0–100, pass/fail outcome, feedback, focus areas). Used by the
conversation and document-submission surfaces. Stub mode is deterministic so the
runtime works offline; a real provider returns a JSON-mode evaluation.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from .llm import LLMError, LLMProvider, ProviderSpec


@dataclass
class AssessmentResult:
    score: int
    outcome: str  # "pass" | "fail"
    feedback: str
    focus_areas: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"score": self.score, "outcome": self.outcome,
                "feedback": self.feedback, "focus_areas": self.focus_areas}


def assess(provider: LLMProvider, spec: ProviderSpec, *, content: str,
           rubric: str = "", kind: str = "assessment", pass_mark: int = 50) -> AssessmentResult:
    """Assess *content*. Deterministic in stub mode; LLM JSON eval otherwise."""
    if spec.provider == "stub":
        return _stub_assess(content, kind, pass_mark)

    system = ("You are a fair assessor for a teaching simulation. Respond with ONLY "
              "JSON: {\"score\": 0-100, \"feedback\": str, \"focus_areas\": [str]}.")
    prompt = (f"Activity: {kind}\nRubric: {rubric or 'general quality and engagement'}\n\n"
              f"Submission / transcript:\n{content}\n\nAssess it.")
    try:
        res = provider.generate(prompt, system=system, max_tokens=600, temperature=0.2)
        data = json.loads(res.text)
        score = int(max(0, min(100, data.get("score", 0))))
        return AssessmentResult(
            score=score, outcome="pass" if score >= pass_mark else "fail",
            feedback=str(data.get("feedback", "")),
            focus_areas=list(data.get("focus_areas", [])))
    except (LLMError, ValueError, KeyError, TypeError):
        # Never let an assessment failure strand a student — fall back to stub.
        return _stub_assess(content, kind, pass_mark)


def _stub_assess(content: str, kind: str, pass_mark: int) -> AssessmentResult:
    # Deterministic: reward engagement (length), clamp to a sensible band.
    words = len((content or "").split())
    score = max(40, min(85, 45 + words // 8))
    outcome = "pass" if score >= pass_mark else "fail"
    return AssessmentResult(
        score=score, outcome=outcome,
        feedback=(f"[stub assessment] Engaged well in the {kind.replace('_', ' ')}. "
                  "Regenerate with an LLM provider for detailed, rubric-based feedback."),
        focus_areas=["Add specifics", "Show your reasoning"])
