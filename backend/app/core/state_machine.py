"""Request lifecycle. Every status change goes through `transition`, which
enforces both the allowed path and *who* may take it. This is where the
agent's autonomy boundary is enforced in code: the agent can approve (only
when policy allows auto-approval, checked by the caller) and schedule, but it
can never reject; rejection always needs a human."""

from app.core.models import Actor, HistoryEvent, MoveRequest, Status

A, S = Actor, Status

TRANSITIONS: dict[tuple[Status, Status], set[Actor]] = {
    (S.DRAFT, S.SUBMITTED): {A.RESIDENT},
    (S.SUBMITTED, S.UNDER_REVIEW): {A.SYSTEM},
    (S.UNDER_REVIEW, S.NEEDS_INFO): {A.ADMIN},
    (S.NEEDS_INFO, S.UNDER_REVIEW): {A.RESIDENT},
    (S.UNDER_REVIEW, S.APPROVED): {A.ADMIN, A.AGENT},
    (S.UNDER_REVIEW, S.REJECTED): {A.ADMIN},
    (S.APPROVED, S.SCHEDULED): {A.ADMIN, A.AGENT},
    (S.SCHEDULED, S.COMPLETED): {A.ADMIN},
}

OPEN_STATUSES = {S.DRAFT, S.SUBMITTED, S.UNDER_REVIEW, S.NEEDS_INFO, S.APPROVED, S.SCHEDULED}
for _status in OPEN_STATUSES:
    TRANSITIONS[(_status, S.CANCELLED)] = {A.RESIDENT, A.ADMIN}


class InvalidTransition(Exception):
    pass


def allowed_next(req: MoveRequest, actor: Actor) -> list[Status]:
    return [to for (frm, to), actors in TRANSITIONS.items() if frm == req.status and actor in actors]


def transition(req: MoveRequest, to: Status, actor: Actor, note: str | None = None) -> MoveRequest:
    actors = TRANSITIONS.get((req.status, to))
    if actors is None:
        raise InvalidTransition(f"Cannot move from {req.status} to {to}")
    if actor not in actors:
        raise InvalidTransition(f"{actor} is not allowed to move a request from {req.status} to {to}")
    req.history.append(HistoryEvent(actor=actor, action="status_change", from_status=req.status, to_status=to, note=note))
    req.status = to
    return req
