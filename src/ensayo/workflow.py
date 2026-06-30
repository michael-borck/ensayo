"""Declarative workflow engine (Phase 7 spike, spec §14).

A simulation's lifecycle is described in ``workflow.yaml`` as a state machine:
**stages**, each activating a set of interaction **surfaces**, connected by
**transitions** that fire on named events (optionally guarded by event context).
The engine is domain-independent — the same code drives an internship, a medical
case, or a financial deal; only the YAML differs.

The spike's question: is this declarative schema sufficient, or do we need a
Python-plugin escape hatch? See docs/adr/0008.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml
from pydantic import Field, model_validator

from .models import _Model

# The composable interaction surfaces a stage can activate (spec §2.2, §12).
SURFACES = {"messaging", "booking", "conversation", "group_chat", "tasks", "assessment"}

_WORKFLOWS_DIR = Path(__file__).resolve().parent / "library" / "workflows"


class WorkflowError(Exception):
    """Raised when a workflow is missing or invalid."""


class Transition(_Model):
    event: str                   # event name that fires this transition (avoid YAML `on:` → True)
    to: str                      # target stage id
    when: dict = Field(default_factory=dict)  # context guard: all key==value must match


class Stage(_Model):
    id: str
    label: str = ""
    surfaces: list[str] = Field(default_factory=list)
    on_enter: list[dict] = Field(default_factory=list)  # actions emitted on entry
    transitions: list[Transition] = Field(default_factory=list)
    terminal: bool = False


class Workflow(_Model):
    name: str
    description: str = ""
    initial_stage: str
    stages: list[Stage]

    @model_validator(mode="after")
    def _validate(self) -> "Workflow":
        ids = [s.id for s in self.stages]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate stage ids")
        idset = set(ids)
        if self.initial_stage not in idset:
            raise ValueError(f"initial_stage {self.initial_stage!r} is not a stage")
        for s in self.stages:
            for surf in s.surfaces:
                if surf not in SURFACES:
                    raise ValueError(f"stage {s.id!r}: unknown surface {surf!r} "
                                     f"(known: {sorted(SURFACES)})")
            for t in s.transitions:
                if t.to not in idset:
                    raise ValueError(f"stage {s.id!r}: transition to unknown stage {t.to!r}")
        return self

    # --- engine ---------------------------------------------------------
    def stage(self, stage_id: str) -> Stage:
        for s in self.stages:
            if s.id == stage_id:
                return s
        raise WorkflowError(f"no such stage: {stage_id!r}")

    def surfaces(self, stage_id: str) -> list[str]:
        return self.stage(stage_id).surfaces

    def is_terminal(self, stage_id: str) -> bool:
        return self.stage(stage_id).terminal

    def advance(self, current: str, event: str, context: dict | None = None) -> "AdvanceResult | None":
        """Return the next stage + its entry actions, or None if no transition fires."""
        context = context or {}
        for t in self.stage(current).transitions:
            if t.event == event and all(context.get(k) == v for k, v in t.when.items()):
                return AdvanceResult(to=t.to, actions=list(self.stage(t.to).on_enter))
        return None


@dataclass
class AdvanceResult:
    to: str
    actions: list[dict]


@dataclass
class Step:
    stage: str
    label: str
    surfaces: list[str]
    actions: list[dict]
    via: str  # the event that led here ("(initial)" for the first step)


@dataclass
class RunResult:
    steps: list[Step]
    final_stage: str
    ignored: list[str] = field(default_factory=list)  # events that fired no transition


def run(wf: Workflow, events: list) -> RunResult:
    """Drive a fresh run from the initial stage through *events*.

    Each event is either ``"name"`` or ``("name", {context})`` or the CLI shorthand
    ``"name:value"`` (→ context ``{"outcome": value}``). Stops at a terminal stage.
    """
    current = wf.initial_stage
    s0 = wf.stage(current)
    steps = [Step(current, s0.label, s0.surfaces, list(s0.on_enter), "(initial)")]
    ignored: list[str] = []

    for raw in events:
        event, ctx = _parse_event(raw)
        if wf.is_terminal(current):
            ignored.append(event)
            continue
        res = wf.advance(current, event, ctx)
        if res is None:
            ignored.append(event)
            continue
        current = res.to
        s = wf.stage(current)
        steps.append(Step(current, s.label, s.surfaces, res.actions, event))
    return RunResult(steps=steps, final_stage=current, ignored=ignored)


def _parse_event(raw) -> tuple[str, dict]:
    if isinstance(raw, tuple):
        return raw[0], (raw[1] or {})
    if ":" in raw:
        name, value = raw.split(":", 1)
        return name, {"outcome": value}
    return raw, {}


# --- loading ---------------------------------------------------------------

def load_workflow_text(text: str) -> Workflow:
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise WorkflowError(f"invalid YAML\n{exc}") from exc
    if not isinstance(raw, dict):
        raise WorkflowError("workflow YAML must be a mapping")
    try:
        return Workflow.model_validate(raw)
    except Exception as exc:  # pydantic ValidationError → friendly message
        raise WorkflowError(str(exc)) from exc


def load_workflow(name_or_path: str, workflows_dir: Path | None = None) -> Workflow:
    """Load a shipped workflow by name, or any ``workflow.yaml`` by path."""
    p = Path(name_or_path)
    if p.exists():
        return load_workflow_text(p.read_text(encoding="utf-8"))
    wf_path = (workflows_dir or _WORKFLOWS_DIR) / f"{name_or_path}.yaml"
    if not wf_path.exists():
        avail = ", ".join(list_workflows(workflows_dir)) or "(none)"
        raise WorkflowError(f"workflow {name_or_path!r} not found. Available: {avail}")
    return load_workflow_text(wf_path.read_text(encoding="utf-8"))


def list_workflows(workflows_dir: Path | None = None) -> list[str]:
    d = workflows_dir or _WORKFLOWS_DIR
    return sorted(p.stem for p in d.glob("*.yaml")) if d.exists() else []


_TEMPLATES_DIR = Path(__file__).resolve().parent / "library" / "templates"


def list_multisite_templates() -> list[dict]:
    """Load all multi-site template configs from the library."""
    import json
    d = _TEMPLATES_DIR
    if not d.exists():
        return []
    out = []
    for p in sorted(d.glob("*.json")):
        try:
            out.append(json.loads(p.read_text(encoding="utf-8")))
        except Exception:
            pass
    return out
