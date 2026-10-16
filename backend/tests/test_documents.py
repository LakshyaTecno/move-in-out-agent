"""AI document verification: the AI's reading is faked so these tests are
about the judging logic and the workflow, not about Gemini."""

import pytest

from app.agents.llm import LLMUnavailable
from app.core.doc_checks import Verdict, names_match, verdict
from app.core.models import Document, DocumentCheck, RuleStatus
from app.core.policy import can_auto_approve, evaluate, is_approvable
from app.core.community import get_community
from tests.test_api import client, make_request, next_weekday, upload  # noqa: F401  (fixtures/helpers)
from tests.test_core import ctx, owner_move_in, read_as

CATALOG = get_community("green-valley").doc_catalog


@pytest.mark.parametrize("a, b, same", [
    ("Karan Shah", "Karan Shah", True),
    ("KARAN  SHAH", "karan shah", True),
    ("K. Shah", "Karan Shah", True),          # initial + same surname
    ("Mr. Karan Shah", "Karan Shah", True),   # titles ignored
    ("Karan Shaw", "Karan Shah", False),      # different surname: the planted mistake
    ("Rajesh Kumar", "Karan Shah", False),
    ("", "Karan Shah", False),
])
def test_names_match(a, b, same):
    assert names_match(a, b) is same


def doc(doc_type="owner_noc", check=None):
    return Document(doc_type=doc_type, file_name="x.png", check=check)


def test_verdicts_for_each_situation():
    name = "Karan Shah"
    assert verdict(doc(check=read_as("owner_noc", "Rajesh Kumar", "Karan Shah")), name, CATALOG)[0] == Verdict.VERIFIED
    assert verdict(doc(check=read_as("owner_noc", "Rajesh Kumar", "Karan Shaw")), name, CATALOG)[0] == Verdict.PROBLEM
    assert verdict(doc(check=read_as("id_proof", "Karan Shah")), name, CATALOG)[0] == Verdict.PROBLEM  # wrong type
    assert verdict(doc(check=read_as("other", readable=False)), name, CATALOG)[0] == Verdict.PROBLEM
    assert verdict(doc(check=DocumentCheck(checked_by="unavailable")), name, CATALOG)[0] == Verdict.UNVERIFIED
    assert verdict(doc(check=None), name, CATALOG)[0] == Verdict.UNVERIFIED
    assert verdict(doc(check=read_as("owner_noc", "Karan Shah")), None, CATALOG)[0] == Verdict.WAITING


def statuses(results):
    return {r.rule: r.status for r in results}


def test_wrong_name_on_a_document_blocks_approval():
    req = owner_move_in("green-valley", documents=[
        Document(doc_type="id_proof", file_name="a.png", check=read_as("id_proof", "Asha Rao")),
        Document(doc_type="sale_deed", file_name="b.png", check=read_as("sale_deed", "Asha Roy")),
    ])
    results = evaluate(req, ctx("green-valley"))
    assert statuses(results)["documents_verified"] == RuleStatus.FAIL
    assert not is_approvable(results)


def test_unverified_documents_can_be_approved_by_a_human_but_never_auto_approved():
    req = owner_move_in("green-valley", documents=[
        Document(doc_type="id_proof", file_name="a.png"),
        Document(doc_type="sale_deed", file_name="b.png"),
    ])
    results = evaluate(req, ctx("green-valley"))
    assert statuses(results)["documents_verified"] == RuleStatus.WARN
    assert is_approvable(results)
    assert not can_auto_approve(req, results, get_community("green-valley"))


def test_expiry_read_by_ai_is_checked_by_document_validity():
    req = owner_move_in("green-valley")
    req.documents[0].valid_until = req.move_date.replace(year=req.move_date.year - 1)
    assert statuses(evaluate(req, ctx("green-valley")))["document_validity"] == RuleStatus.FAIL


# --- through the API ----------------------------------------------------------

TENANT = {"resident_name": "Karan Shah", "phone": "9812345678", "unit": "B-302", "resident_type": "tenant",
          "household_size": 2, "slot": "09:00-13:00"}


def test_wrong_name_upload_is_flagged_and_fixed_by_reupload(client):  # noqa: F811
    rid = make_request(client, "green-valley", "move_in", TENANT | {"move_date": next_weekday("Sat")},
                       ["id_proof", "rental_agreement", "police_verification"])
    view = upload(client, rid, "owner_noc", name="Rajesh Kumar|Karan Shaw").json()
    checks = {c["document"]: c for c in view["checklist"]["document_checks"]}
    assert checks["NOC from flat owner"]["verdict"] == "problem"
    assert "Karan Shaw" in checks["NOC from flat owner"]["detail"]
    assert any("Karan Shaw" in i for i in view["checklist"]["issues"])  # the agent and the UI both see it

    fixed = upload(client, rid, "owner_noc", name="Rajesh Kumar|Karan Shah").json()
    assert {c["verdict"] for c in fixed["checklist"]["document_checks"]} == {"verified"}
    assert fixed["documents"][-1]["name_on_document"] == "Karan Shah"


def test_receipt_uploaded_as_id_is_rejected(client):  # noqa: F811
    rid = make_request(client, "green-valley", "move_in", {"resident_name": "Asha Rao", "resident_type": "owner"}, [])
    view = upload(client, rid, "id_proof", reads_as="other", name="", readable="0").json()
    assert view["checklist"]["document_checks"][0]["verdict"] == "problem"


def test_ai_unavailable_marks_document_unverified_and_blocks_auto_approval(client, monkeypatch):  # noqa: F811
    def down(*_):
        raise LLMUnavailable("quota exceeded")
    monkeypatch.setattr("app.agents.documents.read_document", down)
    rid = make_request(client, "green-valley", "move_in",
                       {"resident_name": "Asha Rao", "phone": "9876543210", "resident_type": "owner", "household_size": 3,
                        "unit": "A-101", "move_date": next_weekday("Sat"), "slot": "09:00-13:00"},
                       ["id_proof", "sale_deed"])
    res = client.post(f"/requests/{rid}/submit").json()
    assert res["status"] == "under_review"  # would have been auto-approved if the documents were verified
    assert {c["verdict"] for c in res["checklist"]["document_checks"]} == {"unverified"}


def test_expired_document_detected_from_ai_reading(client):  # noqa: F811
    date = next_weekday("Sat")
    rid = make_request(client, "green-valley", "move_in", TENANT | {"move_date": date}, [])
    view = upload(client, rid, "police_verification", name="Karan Shah", valid="2026-01-01").json()
    validity = next(r for r in view["policy_results"] if r["rule"] == "document_validity")
    assert validity["status"] == "fail"


@pytest.mark.parametrize("content, mime, error", [
    (b"type=id_proof", "text/plain", "PNG, JPG"),
    (b"", "image/png", "between 1 byte"),
    (b"x" * (5 * 1024 * 1024 + 1), "image/png", "between 1 byte"),
])
def test_bad_files_are_rejected(client, content, mime, error):  # noqa: F811
    rid = client.post("/requests", json={"community_id": "green-valley", "request_type": "move_in"}).json()["id"]
    r = client.post(f"/requests/{rid}/documents/upload", data={"doc_type": "id_proof"},
                    files={"file": ("f", content, mime)})
    assert r.status_code == 400 and error in r.json()["detail"]


def test_expired_document_shows_as_a_problem_in_its_own_verdict():
    from datetime import date
    expired = Document(doc_type="police_verification", file_name="pv.png", valid_until=date(2026, 8, 31),
                       check=read_as("police_verification", "Karan Shah"))
    assert verdict(expired, "Karan Shah", CATALOG)[0] == Verdict.VERIFIED  # policy view: expiry is another rule's job
    v, msg = verdict(expired, "Karan Shah", CATALOG, expires_before=date(2026, 10, 24))
    assert v == Verdict.PROBLEM and "expired on 2026-08-31" in msg
