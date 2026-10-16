"""The intake agent's tools, exercised directly (no LLM)."""

import pytest
from langchain.tools import ToolRuntime
from langchain_core.messages import HumanMessage

from app import services, store
from app.agents.intake import phone_was_typed
from app.core.models import RequestType, Status


def resident_said(*messages: str) -> ToolRuntime:
    """What LangGraph injects into a tool: the conversation so far."""
    return ToolRuntime(state={"messages": [HumanMessage(m) for m in messages]}, context=None, config={},
                       stream_writer=lambda *_: None, tool_call_id="test", store=None)


@pytest.fixture
def tools(tmp_path, monkeypatch):
    monkeypatch.setattr("app.store.DB_PATH", str(tmp_path / "t.db"))
    store.init_db()
    from app.agents import intake
    from app.seed import seed_if_empty

    seed_if_empty()
    req = services.create_draft("green-valley", RequestType.MOVE_IN)
    return req.id, {t.name: t for t in intake._tools(req.id)}


def test_update_details_saves_fields(tools):
    rid, t = tools
    result = t["update_request_details"].invoke({"resident_name": "Karan Shah", "unit": "b-302", "resident_type": "tenant",
                                                 "runtime": resident_said("I'm Karan Shah renting b-302")})
    assert isinstance(result, dict), result
    saved = services.get(rid)
    assert (saved.resident_name, saved.unit, saved.resident_type) == ("Karan Shah", "B-302", "tenant")
    assert "Police verification certificate" in result["documents_missing"]


def test_invalid_value_returns_error_instead_of_raising(tools):
    _, t = tools
    result = t["update_request_details"].invoke({"move_date": "next saturday", "runtime": resident_said("next saturday")})
    assert result.startswith("Could not save")


def test_agent_cannot_submit_incomplete_request(tools):
    rid, t = tools
    assert t["submit_request"].invoke({}).startswith("Not submitted")
    assert services.get(rid).status == Status.DRAFT


def test_invented_phone_is_not_saved_but_other_details_are(tools):
    """Regression: the resident typed "12345" and the model saved 9876543210."""
    rid, t = tools
    result = t["update_request_details"].invoke({
        "resident_name": "Rohan Gupta", "unit": "A-102", "resident_type": "tenant", "phone": "9876543210",
        "runtime": resident_said("Hi, I'm Rohan Gupta, renting A-102. My number is 12345."),
    })
    saved = services.get(rid)
    assert saved.phone is None
    assert (saved.resident_name, saved.unit) == ("Rohan Gupta", "A-102")
    assert "not saved" in result["not_saved"][0]


def test_phone_the_resident_typed_is_saved(tools):
    rid, t = tools
    t["update_request_details"].invoke({"phone": "9812345678",
                                        "runtime": resident_said("hi", "my number is +91 98123 45678")})
    assert services.get(rid).phone == "9812345678"


@pytest.mark.parametrize("phone, typed, grounded", [
    ("9812345678", ["call me on 98123-45678"], True),
    ("9812345678", ["+91 9812345678"], True),
    ("9876543210", ["my number is 12345"], False),   # made up
    ("1234512345", ["my number is 12345"], False),   # "fixed" by padding
    ("9812345678", ["98123"], False),
])
def test_phone_was_typed(phone, typed, grounded):
    assert phone_was_typed(phone, typed) is grounded
