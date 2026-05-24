"""Phase 7 tests: declarative workflow engine, validated across two domains."""

import pytest

from ensayo.workflow import (
    WorkflowError,
    list_workflows,
    load_workflow,
    load_workflow_text,
    run,
)


def test_bundled_workflows_load():
    names = set(list_workflows())
    assert {"internship", "medical_network"} <= names
    assert load_workflow("internship").initial_stage == "application"
    assert load_workflow("medical_network").initial_stage == "triage"


def test_invalid_transition_target_rejected():
    with pytest.raises(WorkflowError):
        load_workflow_text(
            "name: x\ninitial_stage: a\nstages:\n"
            "  - {id: a, transitions: [{event: go, to: nowhere}]}\n")


def test_unknown_surface_rejected():
    with pytest.raises(WorkflowError):
        load_workflow_text("name: x\ninitial_stage: a\n"
                           "stages:\n  - {id: a, surfaces: [telepathy]}\n")


def test_unknown_initial_stage_rejected():
    with pytest.raises(WorkflowError):
        load_workflow_text("name: x\ninitial_stage: z\nstages:\n  - {id: a}\n")


# --- internship end-to-end -------------------------------------------------

def test_internship_happy_path():
    wf = load_workflow("internship")
    res = run(wf, ["application_submitted", "interview_result:pass",
                   "tasks_complete", "exit_complete"])
    assert res.final_stage == "complete"
    assert res.ignored == []
    visited = [s.stage for s in res.steps]
    assert visited == ["application", "interview", "placement", "exit_interview", "complete"]
    # surfaces activate per stage, from YAML only
    by_stage = {s.stage: s.surfaces for s in res.steps}
    assert by_stage["interview"] == ["booking", "conversation"]
    assert by_stage["placement"] == ["messaging", "tasks", "group_chat"]


def test_internship_reject_path():
    wf = load_workflow("internship")
    res = run(wf, ["application_submitted", "interview_result:fail"])
    assert res.final_stage == "rejected"


# --- medical end-to-end ----------------------------------------------------

def test_medical_admit_path_visits_ward_round():
    wf = load_workflow("medical_network")
    res = run(wf, ["consult_booked", "case_result:admit", "round_complete",
                   "discharge_complete"])
    assert res.final_stage == "closed"
    assert "ward_round" in [s.stage for s in res.steps]


def test_medical_discharge_path_skips_ward_round():
    wf = load_workflow("medical_network")
    res = run(wf, ["consult_booked", "case_result:discharge", "discharge_complete"])
    assert res.final_stage == "closed"
    assert "ward_round" not in [s.stage for s in res.steps]


# --- the gate question: domain independence --------------------------------

def test_same_surfaces_activate_at_different_stages_no_code_change():
    intern = load_workflow("internship")
    med = load_workflow("medical_network")
    # 'conversation' is used by both, at different stages
    assert "conversation" in intern.surfaces("interview")
    assert "conversation" in med.surfaces("consultation")
    # 'group_chat' too
    assert "group_chat" in intern.surfaces("placement")
    assert "group_chat" in med.surfaces("ward_round")
    # same engine, different YAML — the only difference between the two runs
    assert type(intern) is type(med)


def test_terminal_stage_ignores_further_events():
    wf = load_workflow("internship")
    res = run(wf, ["application_submitted", "interview_result:fail", "tasks_complete"])
    assert res.final_stage == "rejected"
    assert "tasks_complete" in res.ignored


def test_guard_routes_on_context():
    wf = load_workflow("internship")
    a = wf.advance("interview", "interview_result", {"outcome": "pass"})
    b = wf.advance("interview", "interview_result", {"outcome": "fail"})
    assert a.to == "placement" and b.to == "rejected"
    assert wf.advance("interview", "interview_result", {}) is None  # guard unmet
