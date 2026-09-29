"""The intake agent's tools, exercised directly (no LLM)."""

import pytest

from app import services, store
from app.core.models import RequestType, Status


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
    result = t["update_request_details"].invoke({"resident_name": "Karan Shah", "unit": "b-302", "resident_type": "tenant"})
    assert isinstance(result, dict), result
    saved = services.get(rid)
    assert (saved.resident_name, saved.unit, saved.resident_type) == ("Karan Shah", "B-302", "tenant")
    assert "Police verification certificate" in result["documents_missing"]


def test_invalid_value_returns_error_instead_of_raising(tools):
    _, t = tools
    assert t["update_request_details"].invoke({"move_date": "next saturday"}).startswith("Could not save")


def test_agent_cannot_submit_incomplete_request(tools):
    rid, t = tools
    assert t["submit_request"].invoke({}).startswith("Not submitted")
    assert services.get(rid).status == Status.DRAFT
