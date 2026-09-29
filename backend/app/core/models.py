"""Core domain types. These are the same for every community; per-community
differences live in the YAML configs under app/communities/."""

from datetime import date, datetime, timezone
from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, Field


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


class Document(BaseModel):
    """Prototype stores document metadata only; the name/date fields let the
    review agent spot inconsistencies (e.g. agreement name != resident name)."""

    doc_type: str  # key from the community's doc_catalog
    file_name: str
    name_on_document: str | None = None
    valid_until: date | None = None
    uploaded_at: datetime = Field(default_factory=_now)


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
