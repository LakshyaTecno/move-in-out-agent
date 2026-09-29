"""Demo data: unit records, plus a handful of already-submitted requests so the
admin queue has something to review on a fresh deploy (the free host resets
its disk). Each unit and request is chosen to exercise a specific scenario.

Seeded review briefs are written by hand and marked generated_by="seed";
policy results are always recomputed live when a request is viewed."""

from datetime import date, timedelta

from app import services, store
from app.core.models import (
    Actor,
    Document,
    MoveRequest,
    Recommendation,
    RequestType,
    ResidentType,
    ReviewBrief,
    Status,
    UnitRecord,
)
from app.core.state_machine import transition

O, T = ResidentType.OWNER, ResidentType.TENANT

UNITS = {
    "green-valley": [
        UnitRecord(unit="A-101"),  # vacant: clean move-in
        UnitRecord(unit="A-102"),  # vacant
        UnitRecord(unit="A-201", occupant_name="Rahul Mehta", occupant_type=T),  # clean move-out
        UnitRecord(unit="A-202", occupant_name="Priya Nair", occupant_type=O, dues_outstanding=8200),  # dues block move-out
        UnitRecord(unit="B-301", occupant_name="Vikram Singh", occupant_type=T),  # occupied: move-in conflict
        UnitRecord(unit="B-302"),
    ],
    "sunrise-heights": [
        UnitRecord(unit="101"),
        UnitRecord(unit="102"),
        UnitRecord(unit="201", occupant_name="Neha Kapoor", occupant_type=T, dues_outstanding=3000),  # dues only warn here
        UnitRecord(unit="202", occupant_name="Arjun Das", occupant_type=O),
    ],
}


def _next(day: str, min_days: int, today: date) -> date:
    d = today + timedelta(days=min_days)
    while d.strftime("%a") != day:
        d += timedelta(days=1)
    return d


def _docs(*pairs: tuple[str, str]) -> list[Document]:
    return [Document(doc_type=t, file_name=f"{t}.pdf", name_on_document=n) for t, n in pairs]


def _demo_requests(today: date) -> list[tuple[MoveRequest, dict]]:
    sat, sun = _next("Sat", 8, today), _next("Sun", 8, today)
    return [
        (
            MoveRequest(
                community_id="green-valley", request_type=RequestType.MOVE_IN, resident_name="Karan Shah",
                phone="9812345678", unit="B-302", resident_type=T, move_date=sat, slot="09:00-13:00", household_size=2,
                documents=_docs(("id_proof", "Karan Shah"), ("rental_agreement", "K. Shah"),
                                ("police_verification", "Karan Shah"), ("owner_noc", "Karan Shaw")),
            ),
            dict(
                summary="Karan Shah (tenant) is moving into B-302 with one other person. All policy checks pass, but the owner's NOC is made out to a different name.",
                recommendation=Recommendation.REQUEST_INFO,
                reasoning="The NOC names 'Karan Shaw' while every other document and the request say 'Karan Shah'. "
                "'K. Shah' on the rental agreement is a normal short form. An NOC must name the actual tenant, so this should be corrected before approval.",
                risk_flags=["Owner NOC is issued to 'Karan Shaw', not 'Karan Shah'"],
                questions_for_resident=["Your owner's NOC says 'Karan Shaw'. Could you upload a corrected NOC with your name as 'Karan Shah'?"],
            ),
        ),
        (
            MoveRequest(
                community_id="green-valley", request_type=RequestType.MOVE_OUT, resident_name="Priya Nair",
                phone="9000011111", unit="A-202", resident_type=O, move_date=sun, slot="14:00-18:00",
                documents=_docs(("id_proof", "Priya Nair")),
            ),
            dict(
                summary="Priya Nair (owner) wants to move out of A-202. Rs 8,200 in maintenance dues is outstanding, which blocks a move-out here.",
                recommendation=Recommendation.REQUEST_INFO,
                reasoning="Green Valley requires dues to be cleared before a gate pass is issued. Everything else checks out.",
                risk_flags=["Rs 8,200 maintenance dues outstanding"],
                questions_for_resident=["Please clear the outstanding maintenance dues of Rs 8,200 so we can issue your gate pass."],
            ),
        ),
        (
            MoveRequest(
                community_id="green-valley", request_type=RequestType.MOVE_OUT, resident_name="Rahul Mehta",
                phone="9000022222", unit="A-201", resident_type=T, move_date=_next("Sat", 15, today), slot="14:00-18:00",
                documents=_docs(("id_proof", "Rahul Mehta"), ("owner_noc", "Rahul Mehta")),
                notes="Moving a piano, will need the service lift for the full slot.",
            ),
            dict(
                summary="Rahul Mehta (tenant) is moving out of A-201. All checks pass and the documents are consistent.",
                recommendation=Recommendation.APPROVE,
                reasoning="He is the registered occupant, has no dues, and gave more than the 7-day notice. Move-outs aren't auto-approved in this community, so this needs your sign-off.",
                risk_flags=[],
                questions_for_resident=[],
            ),
        ),
        (
            MoveRequest(
                community_id="green-valley", request_type=RequestType.MOVE_IN, resident_name="Sanjay Gupta",
                phone="9000033333", unit="B-301", resident_type=T, move_date=_next("Sun", 15, today), slot="09:00-13:00",
                household_size=4,
                documents=_docs(("id_proof", "Sanjay Gupta"), ("rental_agreement", "Sanjay Gupta"),
                                ("police_verification", "Sanjay Gupta"), ("owner_noc", "Sanjay Gupta")),
                notes="Current tenant is leaving the week before.",
            ),
            dict(
                summary="Sanjay Gupta (tenant) wants to move into B-301, which records show is still occupied by Vikram Singh.",
                recommendation=Recommendation.REQUEST_INFO,
                reasoning="The resident says the current tenant leaves the week before, but no move-out request from Vikram Singh exists yet. "
                "Confirm the handover before approving so two households aren't booked into one flat.",
                risk_flags=["Unit B-301 is currently occupied by Vikram Singh", "No move-out request on file for the current occupant"],
                questions_for_resident=["Records show B-301 is still occupied. Could you share the date the current tenant is handing over the flat?"],
            ),
        ),
        (
            MoveRequest(
                community_id="sunrise-heights", request_type=RequestType.MOVE_OUT, resident_name="Neha Kapoor",
                phone="9000044444", unit="201", resident_type=T, move_date=_next("Wed", 5, today), slot="12:00-16:00",
                documents=_docs(("id_proof", "Neha Kapoor"), ("owner_noc", "Neha Kapoor")),
            ),
            dict(
                summary="Neha Kapoor (tenant) is moving out of 201. Rs 3,000 in dues is pending, which Sunrise Heights allows to be adjusted from the deposit.",
                recommendation=Recommendation.APPROVE,
                reasoning="All blocking checks pass. The dues are advisory here per the committee's rule, so settle them from the security deposit.",
                risk_flags=["Rs 3,000 dues pending: adjust against the security deposit"],
                questions_for_resident=[],
            ),
        ),
    ]


def _seed_requests() -> None:
    for req, brief in _demo_requests(services.today()):
        transition(req, Status.SUBMITTED, Actor.RESIDENT)
        transition(req, Status.UNDER_REVIEW, Actor.SYSTEM)
        req.review = ReviewBrief(**brief, policy_results=services.check(req), generated_by="seed")
        store.save_request(req)


def seed_if_empty() -> None:
    if store.has_units():
        return
    for community_id, units in UNITS.items():
        for unit in units:
            store.save_unit(community_id, unit)
    _seed_requests()
