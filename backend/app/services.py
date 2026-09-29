"""Application services: the only way to change a request.

Both the REST API and the agents' tools call these functions, so an agent can
never do anything the UI couldn't, and every change passes through the same
validation, state machine, and history log."""

import secrets
from datetime import date, timedelta

from app import store
from app.core.community import get_community
from app.core.models import Actor, Document, HistoryEvent, MoveRequest, RequestType, RuleResult, Status
from app.core.policy import PolicyContext, evaluate, is_approvable
from app.core.state_machine import transition

EDITABLE = {Status.DRAFT, Status.NEEDS_INFO}
BOOKED = [Status.APPROVED, Status.SCHEDULED]
DETAIL_FIELDS = {"resident_name", "phone", "unit", "resident_type", "move_date", "slot", "household_size", "vehicle_count", "notes"}


class ServiceError(Exception):
    pass


def today() -> date:
    return date.today()


def get(request_id: str) -> MoveRequest:
    req = store.get_request(request_id)
    if req is None:
        raise ServiceError(f"Request {request_id} not found")
    return req


def _log(req: MoveRequest, actor: Actor, action: str, note: str | None = None) -> None:
    req.history.append(HistoryEvent(actor=actor, action=action, note=note))


# --- policy -----------------------------------------------------------------


def booked_slots(community_id: str, exclude_id: str | None = None) -> list[tuple[date, str]]:
    return [
        (r.move_date, r.slot)
        for r in store.list_requests(community_id, BOOKED)
        if r.id != exclude_id and r.move_date and r.slot
    ]


def policy_context(req: MoveRequest) -> PolicyContext:
    return PolicyContext(
        community=get_community(req.community_id),
        unit_record=store.get_unit(req.community_id, req.unit) if req.unit else None,
        booked_slots=booked_slots(req.community_id, exclude_id=req.id),
        today=today(),
    )


def check(req: MoveRequest) -> list[RuleResult]:
    return evaluate(req, policy_context(req))


def available_slots(community_id: str, start: date | None = None, days: int = 14) -> list[dict]:
    """Free (date, window) pairs, honouring allowed days, blackouts, and capacity."""
    community = get_community(community_id)
    slots = community.slots
    taken = booked_slots(community_id)
    start = start or today()
    free = []
    for offset in range(days):
        d = start + timedelta(days=offset)
        if d.strftime("%a") not in slots.days or d in slots.blackout_dates:
            continue
        for window in slots.windows:
            left = slots.max_per_window - taken.count((d, window))
            if left > 0:
                free.append({"date": d.isoformat(), "day": d.strftime("%a"), "slot": window, "remaining": left})
    return free


# --- resident actions -----------------------------------------------------------


def create_draft(community_id: str, request_type: RequestType) -> MoveRequest:
    get_community(community_id)  # validates the id
    req = MoveRequest(community_id=community_id, request_type=request_type)
    _log(req, Actor.RESIDENT, "created")
    return store.save_request(req)


def update_details(request_id: str, fields: dict, actor: Actor = Actor.RESIDENT) -> MoveRequest:
    req = get(request_id)
    if req.status not in EDITABLE:
        raise ServiceError(f"Request can't be edited while {req.status}")
    unknown = set(fields) - DETAIL_FIELDS
    if unknown:
        raise ServiceError(f"Unknown fields: {', '.join(sorted(unknown))}")
    changes = {k: v for k, v in fields.items() if v is not None}
    if "unit" in changes:
        changes["unit"] = str(changes["unit"]).strip().upper()
    # Re-validate through pydantic so the agent can't store malformed values.
    updated = MoveRequest.model_validate(req.model_dump() | changes)
    if changes:
        _log(updated, actor, "details_updated", ", ".join(f"{k}={v}" for k, v in changes.items()))
    return store.save_request(updated)


def add_document(request_id: str, doc: Document) -> MoveRequest:
    req = get(request_id)
    if req.status not in EDITABLE:
        raise ServiceError(f"Documents can't be changed while {req.status}")
    catalog = get_community(req.community_id).doc_catalog
    if doc.doc_type not in catalog:
        raise ServiceError(f"Unknown document type {doc.doc_type}")
    req.documents = [d for d in req.documents if d.doc_type != doc.doc_type] + [doc]
    _log(req, Actor.RESIDENT, "document_uploaded", catalog[doc.doc_type])
    return store.save_request(req)


def submit(request_id: str) -> MoveRequest:
    """Resident submits (or resubmits after NEEDS_INFO); review runs immediately."""
    from app.agents.review import run_review  # avoid import cycle

    req = get(request_id)
    if req.status == Status.DRAFT:
        results = check(req)
        incomplete = [r.message for r in results if r.rule in ("required_fields", "documents_complete") and r.status != "pass"]
        if incomplete:
            raise ServiceError("Request is incomplete: " + "; ".join(incomplete))
        transition(req, Status.SUBMITTED, Actor.RESIDENT)
        transition(req, Status.UNDER_REVIEW, Actor.SYSTEM)
    elif req.status == Status.NEEDS_INFO:
        transition(req, Status.UNDER_REVIEW, Actor.RESIDENT, note="resubmitted with updates")
        req.info_request = None
    else:
        raise ServiceError(f"Cannot submit a request that is {req.status}")
    store.save_request(req)
    return run_review(req.id)


def cancel(request_id: str, actor: Actor, reason: str | None = None) -> MoveRequest:
    req = get(request_id)
    transition(req, Status.CANCELLED, actor, note=reason)
    return store.save_request(req)


# --- admin / agent actions ----------------------------------------------------------


def schedule(req: MoveRequest, actor: Actor) -> MoveRequest:
    """Confirm the slot and issue the gate pass security will check."""
    taken = booked_slots(req.community_id, exclude_id=req.id).count((req.move_date, req.slot))
    if taken >= get_community(req.community_id).slots.max_per_window:
        raise ServiceError("Slot was taken by another request; ask the resident to pick a new one")
    transition(req, Status.SCHEDULED, actor, note=f"{req.move_date} {req.slot}")
    req.gate_pass = f"GP-{req.community_id[:2].upper()}-{secrets.token_hex(3).upper()}"
    _log(req, actor, "gate_pass_issued", f"{req.gate_pass}; security notified for {req.move_date} {req.slot}")
    return req


def admin_action(request_id: str, action: str, note: str | None = None) -> MoveRequest:
    req = get(request_id)
    match action:
        case "approve":
            # Humans may override policy, but never silently.
            if not is_approvable(check(req)) and not note:
                raise ServiceError("Blocking checks are failing; add an override reason to approve anyway")
            transition(req, Status.APPROVED, Actor.ADMIN, note=note)
            if get_community(req.community_id).autonomy.auto_schedule:
                schedule(req, Actor.AGENT)
        case "schedule":
            schedule(req, Actor.ADMIN)
        case "request_info":
            if not note:
                raise ServiceError("Tell the resident what is needed")
            transition(req, Status.NEEDS_INFO, Actor.ADMIN, note=note)
            req.info_request = note
        case "reject":
            if not note:
                raise ServiceError("A reason is required to reject")
            transition(req, Status.REJECTED, Actor.ADMIN, note=note)
        case "complete":
            transition(req, Status.COMPLETED, Actor.ADMIN, note=note)
        case _:
            raise ServiceError(f"Unknown action {action}")
    return store.save_request(req)
