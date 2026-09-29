"""Review pipeline: runs whenever a request is submitted or resubmitted.

    check_policy ──► assess ──► guardrail ──┬─► auto_approve ─► persist
      (code)        (LLM)       (code)      └──────────────────► persist

- check_policy: deterministic rules; the source of truth.
- assess: the LLM reads the request the way an experienced admin would and
  catches what rules can't: name mismatches across documents, notes that
  contradict the form, whether a resubmission actually answered the admin.
- guardrail: code overrides any LLM recommendation that contradicts policy.
- auto_approve: only if the community opted in for this case, every rule
  passed, and the LLM raised no risk. Both keys must turn.
If the LLM is down or rate-limited, a deterministic brief is used instead, so
the workflow never blocks on AI."""

import json
import logging
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from app import services, store
from app.agents.llm import get_llm
from app.core.community import get_community
from app.core.models import Actor, MoveRequest, Recommendation, ReviewBrief, RuleResult, RuleStatus, Status
from app.core.policy import can_auto_approve, is_approvable
from app.core.state_machine import transition

log = logging.getLogger(__name__)


class Assessment(BaseModel):
    summary: str = Field(description="Two sentences an admin can read in five seconds: who, what, when, and the headline issue if any.")
    recommendation: Recommendation
    reasoning: str = Field(description="Why this recommendation, referencing specific checks or facts.")
    risk_flags: list[str] = Field(default_factory=list, description="Concrete concerns a human should look at. Empty if none.")
    questions_for_resident: list[str] = Field(default_factory=list, description="Polite, specific questions to send if more info is needed.")


class ReviewState(TypedDict, total=False):
    request: MoveRequest
    results: list[RuleResult]
    brief: ReviewBrief


SYSTEM_PROMPT = """You review move-in / move-out requests for the management office of {community}.

The POLICY RESULTS were computed by the society's rule engine and are authoritative. Never contradict them;
never say a failing check passes. Your job is what the rules cannot do:
- Compare names across the request, each document's name_on_document, and the unit record. Treat initials or
  short forms (e.g. "R. Mehta" vs "Rahul Mehta") as a likely match worth noting, and different people as a risk.
- Spot inconsistencies or special needs in the resident's notes (e.g. heavy items, extra vehicles, other dates).
- If the admin earlier asked for information (see HISTORY), say whether this resubmission answers it.
- Consider the community's guidance and house rules.

Recommend:
- approve: every blocking check passes and you see no material risk.
- request_info: something fixable is missing, failing, or unclear. Write the questions to the resident.
- reject: only for a clear, non-fixable problem (e.g. the requester has no connection to the unit).
A human admin makes the final call on anything you don't approve. Be concise and specific."""


def _request_view(req: MoveRequest) -> dict:
    data = req.model_dump(mode="json", exclude={"history", "review"})
    data["history_notes"] = [f"{e.actor}: {e.action} {e.note or ''}".strip() for e in req.history if e.note]
    return data


def check_policy(state: ReviewState) -> ReviewState:
    return {"results": services.check(state["request"])}


def _fallback(req: MoveRequest, results: list[RuleResult]) -> Assessment:
    problems = [r.message for r in results if r.status in (RuleStatus.FAIL, RuleStatus.PENDING)]
    warnings = [r.message for r in results if r.status == RuleStatus.WARN]
    return Assessment(
        summary=f"{req.resident_name} ({req.resident_type}) requests a {req.request_type.replace('_', '-')} for "
        f"{req.unit} on {req.move_date} {req.slot}.",
        recommendation=Recommendation.REQUEST_INFO if problems else Recommendation.APPROVE,
        reasoning="Automatic summary of policy checks (AI review unavailable).",
        risk_flags=problems + warnings,
        questions_for_resident=[f"Please resolve: {p}" for p in problems],
    )


def assess(state: ReviewState) -> ReviewState:
    req, results = state["request"], state["results"]
    community = get_community(req.community_id)
    rt = community.request_config(req.request_type)
    unit = store.get_unit(req.community_id, req.unit) if req.unit else None
    context = {
        "today": services.today().isoformat(),
        "request": _request_view(req),
        "unit_record": unit.model_dump() if unit else None,
        "policy_results": [r.model_dump() for r in results],
        "community_guidance": rt.guidance,
        "house_rules": community.house_rules,
        "document_labels": community.doc_catalog,
    }
    generated_by = "agent"
    try:
        llm = get_llm().with_structured_output(Assessment)
        assessment = llm.invoke(
            [
                ("system", SYSTEM_PROMPT.format(community=community.name)),
                ("human", json.dumps(context, indent=2, default=str)),
            ]
        )
    except Exception as exc:  # rate limit, network, missing key, bad output
        log.warning("Review LLM unavailable, using fallback: %s", exc)
        assessment, generated_by = _fallback(req, results), "fallback"

    brief = ReviewBrief(**assessment.model_dump(), policy_results=results, generated_by=generated_by)
    return {"brief": brief}


def guardrail(state: ReviewState) -> ReviewState:
    brief, results = state["brief"], state["results"]
    if brief.recommendation == Recommendation.APPROVE and not is_approvable(results):
        failing = [r.message for r in results if r.status in (RuleStatus.FAIL, RuleStatus.PENDING)]
        brief.recommendation = Recommendation.REQUEST_INFO
        brief.guardrail_note = "Policy overrode the AI's approval: " + "; ".join(failing)
    return {"brief": brief}


def route(state: ReviewState) -> str:
    req, brief, results = state["request"], state["brief"], state["results"]
    two_keys = (
        req.status == Status.UNDER_REVIEW
        and brief.recommendation == Recommendation.APPROVE
        and not brief.risk_flags
        and can_auto_approve(req, results, get_community(req.community_id))
    )
    return "auto_approve" if two_keys else "persist"


def auto_approve(state: ReviewState) -> ReviewState:
    req, brief = state["request"], state["brief"]
    transition(req, Status.APPROVED, Actor.AGENT, note="Auto-approved: all checks passed and community allows it")
    brief.auto_approved = True
    if get_community(req.community_id).autonomy.auto_schedule:
        services.schedule(req, Actor.AGENT)
    return {"request": req, "brief": brief}


def persist(state: ReviewState) -> ReviewState:
    req = state["request"]
    req.review = state["brief"]
    store.save_request(req)
    return {"request": req}


def build_graph():
    g = StateGraph(ReviewState)
    g.add_node("check_policy", check_policy)
    g.add_node("assess", assess)
    g.add_node("guardrail", guardrail)
    g.add_node("auto_approve", auto_approve)
    g.add_node("persist", persist)
    g.add_edge(START, "check_policy")
    g.add_edge("check_policy", "assess")
    g.add_edge("assess", "guardrail")
    g.add_conditional_edges("guardrail", route, ["auto_approve", "persist"])
    g.add_edge("auto_approve", "persist")
    g.add_edge("persist", END)
    return g.compile()


review_graph = build_graph()


def run_review(request_id: str) -> MoveRequest:
    return review_graph.invoke({"request": services.get(request_id)})["request"]
