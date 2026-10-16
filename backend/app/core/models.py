"""Core domain types. These are the same for every community; per-community
differences live in the YAML configs under app/communities/."""

import re
from datetime import date, datetime, timezone
from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


class RequestType(StrEnum):
    MOVE_IN = "move_in"
    MOVE_OUT = "move_out"


class ResidentType(StrEnum):
    OWNER = "owner"
    TENANT = "tenant"


class Status(StrEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    NEEDS_INFO = "needs_info"
    APPROVED = "approved"
    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class Actor(StrEnum):
    RESIDENT = "resident"
    ADMIN = "admin"
    AGENT = "agent"  # an LLM-driven step
    SYSTEM = "system"  # deterministic automation (policy engine, scheduler)


def _now() -> datetime:
    return datetime.now(timezone.utc)


class DocumentCheck(BaseModel):
    """What the AI read from an uploaded file: facts only. Whether those facts
    are acceptable (right type, right person) is judged live by the
    documents_verified policy rule, so it re-evaluates if the request changes."""

    readable: bool | None = None  # None = not checked (AI unavailable)
    detected_type: str | None = None  # doc_catalog key, or "other"
    names_found: list[str] = Field(default_factory=list)
    ai_notes: str | None = None
    checked_by: str = "agent"  # "agent", or "unavailable" when the AI couldn't be reached


class Document(BaseModel):
    """The uploaded file itself isn't stored, only what was read from it."""

    doc_type: str  # key from the community's doc_catalog
    file_name: str
    name_on_document: str | None = None
    valid_until: date | None = None  # read by the AI when the file is checked
    uploaded_at: datetime = Field(default_factory=_now)
    check: DocumentCheck | None = None  # None for documents that were never AI-checked


class HistoryEvent(BaseModel):
    at: datetime = Field(default_factory=_now)
    actor: Actor
    action: str
    from_status: Status | None = None
    to_status: Status | None = None
    note: str | None = None


class MoveRequest(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex[:8])
    community_id: str
    request_type: RequestType
    status: Status = Status.DRAFT

    # Details gathered by the intake agent. All optional because a draft is
    # filled progressively over a conversation.
    resident_name: str | None = None
    phone: str | None = None
    unit: str | None = None
    resident_type: ResidentType | None = None
    move_date: date | None = None
    slot: str | None = None  # e.g. "09:00-13:00"
    household_size: int | None = None
    vehicle_count: int | None = None
    notes: str | None = None

    documents: list[Document] = Field(default_factory=list)
    history: list[HistoryEvent] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_now)

    # Produced by the workflow
    review: "ReviewBrief | None" = None
    info_request: str | None = None  # admin's question when status is NEEDS_INFO
    gate_pass: str | None = None  # issued when the move is scheduled

    @field_validator("phone")
    @classmethod
    def indian_mobile(cls, value: str | None) -> str | None:
        """Accept common ways people type an Indian mobile ("+91 98765 43210",
        "098765-43210") and store just the 10 digits."""
        if value is None:
            return None
        digits = re.sub(r"\D", "", value)
        if len(digits) == 12 and digits.startswith("91"):
            digits = digits[2:]
        elif len(digits) == 11 and digits.startswith("0"):
            digits = digits[1:]
        if not re.fullmatch(r"[6-9]\d{9}", digits):
            raise ValueError("phone must be a 10-digit Indian mobile number starting with 6-9")
        return digits

    def doc_types(self) -> set[str]:
        return {d.doc_type for d in self.documents}


class UnitRecord(BaseModel):
    """What the society already knows about a flat (would come from ANACITY's
    resident/billing systems in production)."""

    unit: str
    occupant_name: str | None = None
    occupant_type: ResidentType | None = None
    dues_outstanding: int = 0


class RuleStatus(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    WARN = "warn"
    PENDING = "pending"  # not enough info yet to evaluate


class RuleResult(BaseModel):
    rule: str
    status: RuleStatus
    message: str
    blocking: bool = True  # a blocking FAIL prevents approval


class Recommendation(StrEnum):
    APPROVE = "approve"
    REQUEST_INFO = "request_info"
    REJECT = "reject"


class ReviewBrief(BaseModel):
    """What the admin sees at the top of a request: policy results plus the
    review agent's reading of them."""

    summary: str
    recommendation: Recommendation
    reasoning: str
    risk_flags: list[str] = Field(default_factory=list)
    questions_for_resident: list[str] = Field(default_factory=list)
    policy_results: list[RuleResult] = Field(default_factory=list)
    generated_by: str = "agent"  # "agent" or "fallback" when the LLM was unavailable
    guardrail_note: str | None = None  # set when policy overrode the LLM's recommendation
    auto_approved: bool = False


MoveRequest.model_rebuild()
