from datetime import date

import pytest

from app.core.community import get_community, load_communities
from app.core.models import Actor, Document, MoveRequest, RequestType, ResidentType, RuleStatus, Status, UnitRecord
from app.core.policy import PolicyContext, can_auto_approve, evaluate, is_approvable, validate_config
from app.core.state_machine import InvalidTransition, allowed_next, transition

TODAY = date(2026, 9, 30)  # a Wednesday
NEXT_SAT = date(2026, 10, 10)  # 10 days out


def statuses(results):
    return {r.rule: r.status for r in results}


def owner_move_in(community_id: str, **overrides) -> MoveRequest:
    fields = dict(
        community_id=community_id,
        request_type=RequestType.MOVE_IN,
        resident_name="Asha Rao",
        phone="9876543210",
        unit="A-1204",
        resident_type=ResidentType.OWNER,
        move_date=NEXT_SAT,
        slot="09:00-13:00",
        household_size=3,
        documents=[
            Document(doc_type="id_proof", file_name="aadhaar.pdf"),
            Document(doc_type="sale_deed", file_name="deed.pdf"),
        ],
    )
    return MoveRequest(**(fields | overrides))


def ctx(community_id: str, unit=None, booked=()) -> PolicyContext:
    return PolicyContext(
        community=get_community(community_id),
        unit_record=unit or UnitRecord(unit="A-1204"),
        booked_slots=list(booked),
        today=TODAY,
    )


def test_all_configs_reference_known_rules():
    for community in load_communities().values():
        validate_config(community)


def test_clean_owner_move_in_is_auto_approved_in_green_valley():
    req = owner_move_in("green-valley")
    results = evaluate(req, ctx("green-valley"))
    assert is_approvable(results)
    assert can_auto_approve(req, results, get_community("green-valley"))


def test_same_request_needs_a_human_in_sunrise_heights():
    req = owner_move_in("sunrise-heights", slot="08:00-12:00")
    results = evaluate(req, ctx("sunrise-heights"))
    assert is_approvable(results)
    assert not can_auto_approve(req, results, get_community("sunrise-heights"))


def test_tenant_missing_police_verification_is_blocked():
    req = owner_move_in(
        "green-valley",
        resident_type=ResidentType.TENANT,
        documents=[Document(doc_type="id_proof", file_name="id.pdf"), Document(doc_type="rental_agreement", file_name="ra.pdf")],
    )
    results = evaluate(req, ctx("green-valley"))
    assert statuses(results)["documents_complete"] == RuleStatus.FAIL
    assert "Police verification" in next(r.message for r in results if r.rule == "documents_complete")
    assert not is_approvable(results)


def test_weekday_move_rejected_by_green_valley_slots():
    req = owner_move_in("green-valley", move_date=date(2026, 10, 7))  # Wednesday
    assert statuses(evaluate(req, ctx("green-valley")))["slot_allowed"] == RuleStatus.FAIL


def test_full_slot_is_detected():
    req = owner_move_in("green-valley")
    results = evaluate(req, ctx("green-valley", booked=[(NEXT_SAT, "09:00-13:00")]))
    assert statuses(results)["slot_available"] == RuleStatus.FAIL


def test_dues_block_move_out_in_green_valley_but_only_warn_in_sunrise():
    unit = UnitRecord(unit="A-1204", occupant_name="Asha Rao", occupant_type=ResidentType.OWNER, dues_outstanding=4500)
    base = dict(request_type=RequestType.MOVE_OUT, documents=[Document(doc_type="id_proof", file_name="id.pdf")])

    gv = owner_move_in("green-valley", **base)
    gv_results = evaluate(gv, ctx("green-valley", unit=unit))
    assert statuses(gv_results)["dues_cleared"] == RuleStatus.FAIL
    assert not is_approvable(gv_results)

    sh = owner_move_in("sunrise-heights", slot="08:00-12:00", **base)
    sh_results = evaluate(sh, ctx("sunrise-heights", unit=unit))
    assert statuses(sh_results)["dues_cleared"] == RuleStatus.WARN
    assert is_approvable(sh_results)


def test_short_notice_move_out_fails():
    unit = UnitRecord(unit="A-1204", occupant_name="Asha Rao")
    req = owner_move_in("green-valley", request_type=RequestType.MOVE_OUT, move_date=date(2026, 10, 3))
    assert statuses(evaluate(req, ctx("green-valley", unit=unit)))["notice_period"] == RuleStatus.FAIL


def test_incomplete_draft_reports_pending_not_crash():
    req = MoveRequest(community_id="green-valley", request_type=RequestType.MOVE_IN)
    results = evaluate(req, PolicyContext(community=get_community("green-valley"), today=TODAY))
    assert statuses(results)["documents_complete"] == RuleStatus.PENDING
    assert statuses(results)["required_fields"] == RuleStatus.FAIL


def test_happy_path_lifecycle_records_history():
    req = owner_move_in("green-valley")
    transition(req, Status.SUBMITTED, Actor.RESIDENT)
    transition(req, Status.UNDER_REVIEW, Actor.SYSTEM)
    transition(req, Status.APPROVED, Actor.AGENT, note="auto-approved: all checks passed")
    transition(req, Status.SCHEDULED, Actor.AGENT)
    transition(req, Status.COMPLETED, Actor.ADMIN)
    assert req.status == Status.COMPLETED
    assert [e.to_status for e in req.history][-1] == Status.COMPLETED
    assert len(req.history) == 5


def test_agent_can_never_reject():
    req = owner_move_in("green-valley", status=Status.UNDER_REVIEW)
    with pytest.raises(InvalidTransition):
        transition(req, Status.REJECTED, Actor.AGENT)
    assert Status.REJECTED not in allowed_next(req, Actor.AGENT)
    assert Status.REJECTED in allowed_next(req, Actor.ADMIN)


def test_cannot_skip_review():
    req = owner_move_in("green-valley", status=Status.SUBMITTED)
    with pytest.raises(InvalidTransition):
        transition(req, Status.APPROVED, Actor.ADMIN)
