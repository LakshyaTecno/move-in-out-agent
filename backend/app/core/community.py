"""Community configuration: everything that differs between societies.

Adding a community = dropping a YAML file in app/communities/. Changing a rule
(notice period, required documents, slots, auto-approval) = editing YAML.
Core code only changes when a genuinely new *kind* of rule is needed."""

from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from app.core.models import RequestType, ResidentType

COMMUNITIES_DIR = Path(__file__).resolve().parent.parent / "communities"


class RuleSpec(BaseModel):
    rule: str  # name registered in app.core.policy.RULES
    params: dict[str, Any] = Field(default_factory=dict)
    blocking: bool = True


class RequestTypeConfig(BaseModel):
    label: str
    required_fields: list[str]
    required_docs: dict[ResidentType, list[str]]
    fees: dict[str, int] = Field(default_factory=dict)
    rules: list[RuleSpec]
    # Plain-language guidance the intake agent can explain to residents.
    guidance: list[str] = Field(default_factory=list)


class SlotConfig(BaseModel):
    days: list[str]  # "Mon".."Sun"
    windows: list[str]  # "09:00-13:00"
    blackout_dates: list[date] = Field(default_factory=list)
    max_per_window: int = 1


class AutonomyConfig(BaseModel):
    # "<resident_type>_<request_type>" combos the agent may approve on its own
    # when every rule passes, e.g. "owner_move_in".
    auto_approve: list[str] = Field(default_factory=list)
    # After approval, may the agent book the slot + issue the gate pass itself?
    auto_schedule: bool = True


class CommunityConfig(BaseModel):
    id: str
    name: str
    doc_catalog: dict[str, str]  # doc key -> human label
    slots: SlotConfig
    autonomy: AutonomyConfig
    request_types: dict[RequestType, RequestTypeConfig]
    house_rules: list[str] = Field(default_factory=list)

    def request_config(self, request_type: RequestType) -> RequestTypeConfig:
        return self.request_types[request_type]


@lru_cache
def load_communities() -> dict[str, CommunityConfig]:
    communities = {}
    for path in sorted(COMMUNITIES_DIR.glob("*.yaml")):
        config = CommunityConfig.model_validate(yaml.safe_load(path.read_text()))
        communities[config.id] = config
    return communities


def get_community(community_id: str) -> CommunityConfig:
    try:
        return load_communities()[community_id]
    except KeyError:
        raise KeyError(f"Unknown community: {community_id}") from None
