"""End-to-end workflow through the HTTP API with the LLM disabled, proving the
system still works (via the deterministic fallback) when AI is unavailable."""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app import services
from app.agents.documents import DocumentReading


def fake_read_document(content: bytes, mime_type: str, catalog: dict) -> DocumentReading:
    """Stands in for Gemini: the test file's bytes say what the 'AI' should read,
    e.g. b"type=id_proof;name=Asha Rao;valid=2030-01-01;readable=1"."""
    fields = dict(part.split("=", 1) for part in content.decode().split(";"))
    return DocumentReading(
        is_readable_document=fields.get("readable", "1") == "1",
        detected_type=fields["type"],
        names=[n for n in fields.get("name", "").split("|") if n],
        valid_until=fields.get("valid") or None,
        notes="",
    )


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "")
    monkeypatch.setattr("app.store.DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setattr("app.agents.documents.read_document", fake_read_document)
    from app.main import app

    with TestClient(app) as c:
        yield c


def upload(client, rid, doc_type, *, reads_as=None, name="Asha Rao", valid="", readable="1"):
    body = f"type={reads_as or doc_type};name={name};valid={valid};readable={readable}".encode()
    return client.post(f"/requests/{rid}/documents/upload", data={"doc_type": doc_type},
                       files={"file": (f"{doc_type}.png", body, "image/png")})


def next_weekday(name: str, min_days: int = 10) -> str:
    d = services.today() + timedelta(days=min_days)
    while d.strftime("%a") != name:
        d += timedelta(days=1)
    return d.isoformat()


def make_request(client, community, kind, fields, docs, verified=True):
    """verified=True uploads real files that the (fake) AI reads; False uses the
    old metadata-only endpoint, so documents stay unverified."""
    req = client.post("/requests", json={"community_id": community, "request_type": kind}).json()
    assert req["greeting"]
    client.patch(f"/requests/{req['id']}", json=fields)
    for doc_type in docs:
        if verified:
            upload(client, req["id"], doc_type, name=fields.get("resident_name", ""))
        else:
            client.post(f"/requests/{req['id']}/documents", json={"doc_type": doc_type, "file_name": f"{doc_type}.pdf"})
    return req["id"]


OWNER = {"resident_name": "Asha Rao", "phone": "9876543210", "resident_type": "owner", "household_size": 3}


def test_owner_move_in_is_auto_approved_and_scheduled(client):
    rid = make_request(client, "green-valley", "move_in",
                       OWNER | {"unit": "a-101", "move_date": next_weekday("Sat"), "slot": "09:00-13:00"},
                       ["id_proof", "sale_deed"])
    res = client.post(f"/requests/{rid}/submit").json()
    # Fallback brief has no risk flags when all rules pass, so both keys turn.
    assert res["status"] == "scheduled"
    assert res["gate_pass"].startswith("GP-")
    assert "review" not in res  # the admin brief is hidden from residents

    admin = client.get(f"/requests/{rid}", params={"role": "admin"}).json()
    assert admin["review"]["auto_approved"] and admin["review"]["generated_by"] == "fallback"


def test_incomplete_request_cannot_be_submitted(client):
    rid = make_request(client, "green-valley", "move_in", {"unit": "A-101"}, [])
    r = client.post(f"/requests/{rid}/submit")
    assert r.status_code == 400 and "incomplete" in r.json()["detail"]


def test_move_out_with_dues_goes_to_admin_and_round_trips_needs_info(client):
    rid = make_request(client, "green-valley", "move_out",
                       {"resident_name": "Priya Nair", "phone": "9000000000", "unit": "A-202",
                        "resident_type": "owner", "move_date": next_weekday("Sun"), "slot": "14:00-18:00"},
                       ["id_proof"])
    res = client.post(f"/requests/{rid}/submit").json()
    assert res["status"] == "under_review"

    queue = client.get("/admin/requests", params={"community_id": "green-valley"}).json()
    item = next(r for r in queue if r["id"] == rid)
    assert item["review"]["recommendation"] == "request_info"
    assert any("dues" in f for f in item["review"]["risk_flags"])

    # Approving over a blocking failure requires an override reason.
    assert client.post(f"/admin/requests/{rid}/action", json={"action": "approve"}).status_code == 400

    client.post(f"/admin/requests/{rid}/action", json={"action": "request_info", "note": "Please clear Rs 8,200 dues"})
    view = client.get(f"/requests/{rid}").json()
    assert view["status"] == "needs_info" and view["checklist"]["admin_question"]

    assert client.post(f"/requests/{rid}/submit").json()["status"] == "under_review"


def test_sunrise_heights_requires_admin_and_manual_scheduling(client):
    rid = make_request(client, "sunrise-heights", "move_in",
                       OWNER | {"unit": "101", "move_date": next_weekday("Tue"), "slot": "08:00-12:00"},
                       ["id_proof"])
    assert client.post(f"/requests/{rid}/submit").json()["status"] == "under_review"
    approved = client.post(f"/admin/requests/{rid}/action", json={"action": "approve"}).json()
    assert approved["status"] == "approved"  # auto_schedule is off here
    scheduled = client.post(f"/admin/requests/{rid}/action", json={"action": "schedule"}).json()
    assert scheduled["status"] == "scheduled" and scheduled["gate_pass"]


def test_booked_slot_disappears_from_availability(client):
    date = next_weekday("Sat")
    rid = make_request(client, "green-valley", "move_in",
                       OWNER | {"unit": "A-102", "move_date": date, "slot": "09:00-13:00"}, ["id_proof", "sale_deed"])
    client.post(f"/requests/{rid}/submit")
    free = client.get("/communities/green-valley/slots", params={"start": date, "days": 1}).json()
    assert {"slot": "09:00-13:00"} not in [{"slot": s["slot"]} for s in free]


def test_invalid_phone_gives_clear_400_not_500(client):
    rid = client.post("/requests", json={"community_id": "green-valley", "request_type": "move_in"}).json()["id"]
    r = client.patch(f"/requests/{rid}", json={"phone": "12345"})
    assert r.status_code == 400
    assert "10-digit Indian mobile" in r.json()["detail"]
    ok = client.patch(f"/requests/{rid}", json={"phone": "+91 98765 43210"})
    assert ok.json()["phone"] == "9876543210"
