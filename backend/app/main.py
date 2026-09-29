import logging
import os
from contextlib import asynccontextmanager
from datetime import date

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, Query, Request  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from app import services, store  # noqa: E402
from app.agents import intake  # noqa: E402
from app.agents.llm import LLMUnavailable  # noqa: E402
from app.agents.review import run_review  # noqa: E402
from app.core.community import load_communities  # noqa: E402
from app.core.models import Actor, Document, RequestType, Status  # noqa: E402
from app.core.policy import validate_config  # noqa: E402
from app.core.state_machine import InvalidTransition, allowed_next  # noqa: E402
from app.seed import seed_if_empty  # noqa: E402

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    for community in load_communities().values():
        validate_config(community)
    store.init_db()
    seed_if_empty()
    yield


app = FastAPI(title="ANACITY Move-in / Move-out Agent", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(services.ServiceError)
@app.exception_handler(InvalidTransition)
async def domain_error(_: Request, exc: Exception):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(LLMUnavailable)
async def llm_error(_: Request, exc: Exception):
    return JSONResponse(status_code=503, content={"detail": f"Assistant unavailable: {exc}. You can still use the form."})


def _view(req, actor: Actor):
    """A request plus everything the UI needs to render it for this role."""
    data = req.model_dump(mode="json")
    data["checklist"] = intake.checklist(req)
    data["policy_results"] = [r.model_dump() for r in services.check(req)]
    data["allowed_actions"] = allowed_next(req, actor)
    if actor == Actor.RESIDENT:
        data.pop("review")  # the admin's AI brief is internal
    return data


# --- shared ---------------------------------------------------------------------


@app.get("/health")
def health():
    return {"ok": True, "llm_configured": bool(os.getenv("GOOGLE_API_KEY"))}


@app.get("/communities")
def communities():
    return [c.model_dump(mode="json") for c in load_communities().values()]


@app.get("/communities/{community_id}/slots")
def slots(community_id: str, start: date | None = None, days: int = 14):
    return services.available_slots(community_id, start, days)


@app.get("/communities/{community_id}/units")
def units(community_id: str):
    return store.list_units(community_id)


# --- resident -------------------------------------------------------------------


class CreateRequest(BaseModel):
    community_id: str
    request_type: RequestType


class ChatMessage(BaseModel):
    message: str


class CancelBody(BaseModel):
    reason: str | None = None


@app.post("/requests")
def create_request(body: CreateRequest):
    req = services.create_draft(body.community_id, body.request_type)
    return _view(req, Actor.RESIDENT) | {"greeting": intake.greeting(req)}


@app.get("/requests/{request_id}")
def get_request(request_id: str, role: Actor = Actor.RESIDENT):
    return _view(services.get(request_id), role)


@app.patch("/requests/{request_id}")
def update_request(request_id: str, fields: dict):
    return _view(services.update_details(request_id, fields), Actor.RESIDENT)


@app.post("/requests/{request_id}/documents")
def upload_document(request_id: str, doc: Document):
    return _view(services.add_document(request_id, doc), Actor.RESIDENT)


@app.post("/requests/{request_id}/submit")
def submit(request_id: str):
    return _view(services.submit(request_id), Actor.RESIDENT)


@app.post("/requests/{request_id}/cancel")
def cancel(request_id: str, body: CancelBody, role: Actor = Actor.RESIDENT):
    return _view(services.cancel(request_id, role, body.reason), role)


@app.get("/requests/{request_id}/chat")
def chat_history(request_id: str):
    req = services.get(request_id)
    return [{"role": "assistant", "content": intake.greeting(req)}] + intake.transcript(request_id)


@app.post("/requests/{request_id}/chat")
def chat(request_id: str, body: ChatMessage):
    reply = intake.chat(request_id, body.message)
    return {"reply": reply, "request": _view(services.get(request_id), Actor.RESIDENT)}


# --- admin ----------------------------------------------------------------------


class AdminAction(BaseModel):
    action: str  # approve | request_info | reject | schedule | complete
    note: str | None = None


@app.get("/admin/requests")
def admin_queue(community_id: str | None = None, status: list[Status] | None = Query(None)):
    reqs = store.list_requests(community_id, status)
    return [r for r in (_view(r, Actor.ADMIN) for r in reqs) if r["status"] != Status.DRAFT]


@app.post("/admin/requests/{request_id}/action")
def admin_action(request_id: str, body: AdminAction):
    return _view(services.admin_action(request_id, body.action, body.note), Actor.ADMIN)


@app.post("/admin/requests/{request_id}/review")
def regenerate_review(request_id: str):
    """Re-run the AI review (e.g. after a rate-limit fallback)."""
    return _view(run_review(request_id), Actor.ADMIN)
