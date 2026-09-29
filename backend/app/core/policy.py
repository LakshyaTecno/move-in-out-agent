"""Deterministic policy engine.

Hard rules (documents, notice period, dues, slot capacity) are evaluated here
in plain code, never by the LLM, so every approval is explainable and
auditable. The agents *read* these results; they cannot override them.

Rules are registered by name. A community's YAML picks which rules apply to
each request type and supplies their params, so communities differ by config
while the rule implementations stay shared."""

from collections.abc import Callable
from datetime import date

from pydantic import BaseModel

from app.core.community import CommunityConfig, RuleSpec
from app.core.models import MoveRequest, RuleResult, RuleStatus, UnitRecord


class PolicyContext(BaseModel):
    community: CommunityConfig
    unit_record: UnitRecord | None = None
    # (date, slot) pairs already held by *other* approved/scheduled requests
    booked_slots: list[tuple[date, str]] = []
    today: date


FIELD_LABELS = {
    "resident_name": "name",
    "phone": "phone",
    "unit": "flat number",
    "resident_type": "owner or tenant",
    "move_date": "move date",
    "slot": "time slot",
    "household_size": "number of people",
    "vehicle_count": "vehicles",
}

RuleFn = Callable[[MoveRequest, PolicyContext, dict], RuleResult]
RULES: dict[str, RuleFn] = {}


def rule(name: str):
    def register(fn: RuleFn) -> RuleFn:
        RULES[name] = fn
        return fn

    return register


def _result(name: str, status: RuleStatus, message: str) -> RuleResult:
    return RuleResult(rule=name, status=status, message=message)


def _same_person(a: str | None, b: str | None) -> bool:
    return bool(a and b and a.strip().casefold() == b.strip().casefold())


@rule("required_fields")
def required_fields(req: MoveRequest, ctx: PolicyContext, params: dict) -> RuleResult:
    fields = ctx.community.request_config(req.request_type).required_fields
    missing = [FIELD_LABELS.get(f, f) for f in fields if getattr(req, f) in (None, "")]
    if missing:
        return _result("required_fields", RuleStatus.FAIL, f"Missing details: {', '.join(missing)}")
    return _result("required_fields", RuleStatus.PASS, "All required details provided")


@rule("documents_complete")
def documents_complete(req: MoveRequest, ctx: PolicyContext, params: dict) -> RuleResult:
    if req.resident_type is None:
        return _result("documents_complete", RuleStatus.PENDING, "Resident type unknown, so required documents can't be determined yet")
    required = ctx.community.request_config(req.request_type).required_docs.get(req.resident_type, [])
    missing = [d for d in required if d not in req.doc_types()]
    if missing:
        labels = [ctx.community.doc_catalog.get(d, d) for d in missing]
        return _result("documents_complete", RuleStatus.FAIL, f"Missing documents: {', '.join(labels)}")
    return _result("documents_complete", RuleStatus.PASS, "All required documents uploaded")


@rule("document_validity")
def document_validity(req: MoveRequest, ctx: PolicyContext, params: dict) -> RuleResult:
    cutoff = req.move_date or ctx.today
    expired = [d for d in req.documents if d.valid_until and d.valid_until < cutoff]
    if expired:
        labels = [ctx.community.doc_catalog.get(d.doc_type, d.doc_type) for d in expired]
        return _result("document_validity", RuleStatus.FAIL, f"Expired before move date: {', '.join(labels)}")
    return _result("document_validity", RuleStatus.PASS, "No expired documents")


def _days_ahead(name: str, req: MoveRequest, ctx: PolicyContext, min_days: int, what: str) -> RuleResult:
    if req.move_date is None:
        return _result(name, RuleStatus.PENDING, "Move date not set")
    days = (req.move_date - ctx.today).days
    if days < min_days:
        return _result(name, RuleStatus.FAIL, f"{what} requires {min_days} days; move date is {days} day(s) away")
    return _result(name, RuleStatus.PASS, f"{days} days ahead (minimum {min_days})")


@rule("lead_time")
def lead_time(req: MoveRequest, ctx: PolicyContext, params: dict) -> RuleResult:
    return _days_ahead("lead_time", req, ctx, params.get("min_days", 0), "Advance booking")


@rule("notice_period")
def notice_period(req: MoveRequest, ctx: PolicyContext, params: dict) -> RuleResult:
    return _days_ahead("notice_period", req, ctx, params.get("min_days", 0), "Notice period")


@rule("slot_allowed")
def slot_allowed(req: MoveRequest, ctx: PolicyContext, params: dict) -> RuleResult:
    if req.move_date is None or req.slot is None:
        return _result("slot_allowed", RuleStatus.PENDING, "Move date or slot not set")
    slots = ctx.community.slots
    day = req.move_date.strftime("%a")
    if day not in slots.days:
        return _result("slot_allowed", RuleStatus.FAIL, f"Moves not allowed on {day}; allowed days: {', '.join(slots.days)}")
    if req.move_date in slots.blackout_dates:
        return _result("slot_allowed", RuleStatus.FAIL, f"{req.move_date} is a blackout date")
    if req.slot not in slots.windows:
        return _result("slot_allowed", RuleStatus.FAIL, f"Slot {req.slot} not offered; options: {', '.join(slots.windows)}")
    return _result("slot_allowed", RuleStatus.PASS, f"{day} {req.slot} is an allowed moving window")


@rule("slot_available")
def slot_available(req: MoveRequest, ctx: PolicyContext, params: dict) -> RuleResult:
    if req.move_date is None or req.slot is None:
        return _result("slot_available", RuleStatus.PENDING, "Move date or slot not set")
    taken = ctx.booked_slots.count((req.move_date, req.slot))
    capacity = ctx.community.slots.max_per_window
    if taken >= capacity:
        return _result("slot_available", RuleStatus.FAIL, f"{req.move_date} {req.slot} is fully booked")
    return _result("slot_available", RuleStatus.PASS, f"{capacity - taken} of {capacity} bookings left in this slot")


@rule("unit_available_for_move_in")
def unit_available_for_move_in(req: MoveRequest, ctx: PolicyContext, params: dict) -> RuleResult:
    name = "unit_available_for_move_in"
    if req.unit is None:
        return _result(name, RuleStatus.PENDING, "Unit not set")
    if ctx.unit_record is None:
        return _result(name, RuleStatus.FAIL, f"Unit {req.unit} not found in community records")
    occupant = ctx.unit_record.occupant_name
    if occupant and not _same_person(occupant, req.resident_name):
        return _result(name, RuleStatus.FAIL, f"Unit {req.unit} is currently occupied by {occupant}")
    return _result(name, RuleStatus.PASS, f"Unit {req.unit} is available")


@rule("requester_is_occupant")
def requester_is_occupant(req: MoveRequest, ctx: PolicyContext, params: dict) -> RuleResult:
    name = "requester_is_occupant"
    if req.unit is None:
        return _result(name, RuleStatus.PENDING, "Unit not set")
    if ctx.unit_record is None:
        return _result(name, RuleStatus.FAIL, f"Unit {req.unit} not found in community records")
    occupant = ctx.unit_record.occupant_name
    if not _same_person(occupant, req.resident_name):
        return _result(name, RuleStatus.FAIL, f"Records list {occupant or 'no one'} as occupant of {req.unit}, not {req.resident_name}")
    return _result(name, RuleStatus.PASS, f"{req.resident_name} is the registered occupant")


@rule("dues_cleared")
def dues_cleared(req: MoveRequest, ctx: PolicyContext, params: dict) -> RuleResult:
    if ctx.unit_record is None:
        return _result("dues_cleared", RuleStatus.PENDING, "Unit not identified")
    dues = ctx.unit_record.dues_outstanding
    if dues > 0:
        return _result("dues_cleared", RuleStatus.FAIL, f"Rs {dues:,} maintenance dues outstanding")
    return _result("dues_cleared", RuleStatus.PASS, "No outstanding dues")


def _apply(spec: RuleSpec, req: MoveRequest, ctx: PolicyContext) -> RuleResult:
    result = RULES[spec.rule](req, ctx, spec.params)
    result.blocking = spec.blocking
    # A non-blocking failure is surfaced to the admin as a warning.
    if not spec.blocking and result.status == RuleStatus.FAIL:
        result.status = RuleStatus.WARN
    return result


def evaluate(req: MoveRequest, ctx: PolicyContext) -> list[RuleResult]:
    specs = ctx.community.request_config(req.request_type).rules
    return [_apply(spec, req, ctx) for spec in specs]


def is_approvable(results: list[RuleResult]) -> bool:
    """No blocking rule failed or is still waiting on information."""
    return all(r.status in (RuleStatus.PASS, RuleStatus.WARN) for r in results)


def can_auto_approve(req: MoveRequest, results: list[RuleResult], community: CommunityConfig) -> bool:
    """The agent may approve without a human only when the community opted in
    for this exact case AND every rule passed cleanly (warnings go to a human)."""
    key = f"{req.resident_type}_{req.request_type}"
    return key in community.autonomy.auto_approve and all(r.status == RuleStatus.PASS for r in results)


def validate_config(community: CommunityConfig) -> None:
    """Fail fast at startup if a YAML references a rule that doesn't exist."""
    for rt, cfg in community.request_types.items():
        for spec in cfg.rules:
            if spec.rule not in RULES:
                raise ValueError(f"{community.id}/{rt}: unknown rule '{spec.rule}'")
