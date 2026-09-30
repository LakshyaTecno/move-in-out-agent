"""Intake agent: the resident's guide for starting, completing, submitting, and
following a request.

It turns free text ("moving into A-101 next Saturday morning, I'm renting")
into structured fields, asks only for what *this community* still needs, and
explains the rules. Its tools are bound to one request and call the same
services as the UI, so it can fill in and submit a request but cannot approve,
reject, or touch anyone else's data. Conversation memory is persisted per
request by a LangGraph checkpointer (thread_id = request id)."""

import os
import sqlite3
from datetime import date, timedelta
from typing import Literal

from langchain.agents import create_agent
from langchain.agents.middleware import ModelFallbackMiddleware
from langchain_core.tools import tool
from langgraph.checkpoint.sqlite import SqliteSaver

from app import services
from app.agents.llm import LLMUnavailable, get_models
from app.core.community import get_community
from app.core.models import Actor, MoveRequest, RuleStatus

_checkpointer = SqliteSaver(sqlite3.connect(os.getenv("CHECKPOINT_DB", "checkpoints.db"), check_same_thread=False))


def checklist(req: MoveRequest) -> dict:
    """The request's progress as the resident (and the agent) should see it."""
    community = get_community(req.community_id)
    rt = community.request_config(req.request_type)
    required_docs = rt.required_docs.get(req.resident_type, []) if req.resident_type else []
    results = services.check(req)
    return {
        "status": req.status,
        "details": req.model_dump(mode="json", include=services.DETAIL_FIELDS),
        "missing_fields": [f for f in rt.required_fields if getattr(req, f) in (None, "")],
        "documents_uploaded": [community.doc_catalog.get(d, d) for d in req.doc_types()],
        "documents_missing": [community.doc_catalog[d] for d in required_docs if d not in req.doc_types()],
        "issues": [r.message for r in results if r.status == RuleStatus.FAIL],
        "warnings": [r.message for r in results if r.status == RuleStatus.WARN],
        "fees": rt.fees,
        "admin_question": req.info_request,
        "gate_pass": req.gate_pass,
        "recent_updates": [f"{e.at:%d %b %H:%M} {e.action} {e.note or ''}".strip() for e in req.history[-4:]],
    }


def _tools(request_id: str):
    @tool
    def update_request_details(
        resident_name: str | None = None,
        phone: str | None = None,
        unit: str | None = None,
        resident_type: Literal["owner", "tenant"] | None = None,
        move_date: str | None = None,
        slot: str | None = None,
        household_size: int | None = None,
        vehicle_count: int | None = None,
        notes: str | None = None,
    ) -> dict | str:
        """Save any details the resident has given. Pass only fields you learned. move_date must be YYYY-MM-DD;
        slot must exactly match one of the community's windows, e.g. "09:00-13:00". Returns the updated checklist."""
        fields = {
            "resident_name": resident_name,
            "phone": phone,
            "unit": unit,
            "resident_type": resident_type,
            "move_date": move_date,
            "slot": slot,
            "household_size": household_size,
            "vehicle_count": vehicle_count,
            "notes": notes,
        }
        try:
            req = services.update_details(request_id, fields, actor=Actor.AGENT)
        except Exception as exc:
            return f"Could not save: {exc}"
        return checklist(req)

    @tool
    def get_checklist() -> dict:
        """Current status, what's missing, rule issues, fees, any question from the admin, and the gate pass."""
        return checklist(services.get(request_id))

    @tool
    def find_available_slots(start_date: str | None = None, days: int = 14) -> list[dict]:
        """Free moving slots from start_date (YYYY-MM-DD, default today) for the next `days` days."""
        req = services.get(request_id)
        start = date.fromisoformat(start_date) if start_date else None
        return services.available_slots(req.community_id, start, days)[:12]

    @tool
    def submit_request() -> dict | str:
        """Submit the request for review. Only call after the resident has explicitly confirmed the summary.
        Also used to resubmit after the admin asked for more information."""
        try:
            req = services.submit(request_id)
        except Exception as exc:
            return f"Not submitted: {exc}"
        return {"status": req.status, "gate_pass": req.gate_pass, "auto_approved": bool(req.review and req.review.auto_approved)}

    @tool
    def cancel_request(reason: str) -> str:
        """Cancel this request. Only after the resident clearly confirms they want to cancel."""
        try:
            services.cancel(request_id, Actor.RESIDENT, reason)
        except Exception as exc:
            return f"Could not cancel: {exc}"
        return "Cancelled"

    return [update_request_details, get_checklist, find_available_slots, submit_request, cancel_request]


SYSTEM_PROMPT = """You are the {community} move assistant helping a resident with a {kind} request.
Today is {today}. Upcoming dates: {calendar}.

How to work:
- Extract every detail the resident mentions and save it immediately with update_request_details. Convert relative
  dates ("next Saturday") to YYYY-MM-DD using the dates above. Match slot wording ("morning") to an exact window.
- Then ask for what's still missing, a couple of items at a time. Never ask for something already known.
- Documents are uploaded with the upload panel next to this chat, not in the chat. Tell the resident which ones
  are still needed by name.
- If a date or slot is not allowed or is full, say why and offer alternatives from find_available_slots.
- Explain rules, fees and house rules when relevant, in plain language. Don't invent rules not listed below.
- When nothing is missing, show a short summary and ask the resident to confirm. Only after a clear "yes", call
  submit_request. If the resident has already explicitly asked you to submit and nothing is missing, submit
  right away and include the summary in your reply. Then explain what happens next.
- After submission, answer status questions using get_checklist. If the admin asked a question, help the
  resident answer it (update details / upload), then resubmit with submit_request once they confirm.
- Only tell the resident something is saved or submitted if the tool result confirms it. If a tool returns
  an error ("Could not save", "Not submitted"), explain the problem plainly and how to fix it.
- You cannot approve or reject requests; the management office decides. Be warm, brief, and practical.

Community rules for this request:
- Allowed moving days: {days}; windows: {windows}; blackout dates: {blackouts}
- Required documents: {docs}
- Fees: {fees}
- Guidance: {guidance}
- House rules: {house_rules}"""


def _system_prompt(req: MoveRequest) -> str:
    community = get_community(req.community_id)
    rt = community.request_config(req.request_type)
    today = services.today()
    calendar = ", ".join(f"{(today + timedelta(d)):%a %Y-%m-%d}" for d in range(15))
    docs = "; ".join(
        f"{who}: {', '.join(community.doc_catalog[d] for d in docs)}" for who, docs in rt.required_docs.items()
    )
    return SYSTEM_PROMPT.format(
        community=community.name,
        kind=rt.label,
        today=f"{today:%A %Y-%m-%d}",
        calendar=calendar,
        days=", ".join(community.slots.days),
        windows=", ".join(community.slots.windows),
        blackouts=", ".join(map(str, community.slots.blackout_dates)) or "none",
        docs=docs,
        fees=", ".join(f"{k.replace('_', ' ')}: Rs {v:,}" for k, v in rt.fees.items()) or "none",
        guidance=" ".join(rt.guidance) or "none",
        house_rules=" ".join(community.house_rules) or "none",
    )


def greeting(req: MoveRequest) -> str:
    """Static opening line, so starting a request costs no LLM call."""
    community = get_community(req.community_id)
    kind = community.request_config(req.request_type).label.lower()
    return (
        f"Hi! I'll help you set up your {kind} at {community.name}. "
        "Tell me your flat number, when you'd like to move, and whether you're the owner or a tenant, "
        "in whatever words are easiest."
    )


def _config(request_id: str) -> dict:
    return {"configurable": {"thread_id": request_id}}


def chat(request_id: str, message: str) -> str:
    req = services.get(request_id)
    primary, *fallbacks = get_models("chat")
    agent = create_agent(
        primary,
        _tools(request_id),
        system_prompt=_system_prompt(req),
        middleware=[ModelFallbackMiddleware(*fallbacks)] if fallbacks else [],
        checkpointer=_checkpointer,
    )
    try:
        state = agent.invoke({"messages": [{"role": "user", "content": message}]}, _config(request_id))
    except Exception as exc:  # every model in the chain failed (quota, network)
        raise LLMUnavailable("the assistant is busy right now, please try again in a minute") from exc
    return state["messages"][-1].text


def transcript(request_id: str) -> list[dict]:
    snapshot = _checkpointer.get_tuple(_config(request_id))
    if snapshot is None:
        return []
    messages = snapshot.checkpoint["channel_values"].get("messages", [])
    return [
        {"role": "user" if m.type == "human" else "assistant", "content": m.text}
        for m in messages
        if m.type in ("human", "ai") and m.text
    ]
