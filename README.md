# Move-in / Move-out Agent

An agentic workflow for residential communities. Residents describe their move in plain language and an AI assistant turns it into a complete request that follows their community's rules. Admins get each request already reviewed, with a recommendation, risk flags, and the policy checks behind it. When a community allows it, the agent approves clean cases and books them on its own.

📄 **[Explanation document](docs/EXPLANATION.md)**: experience, architecture, agent design, assumptions, testing, and production considerations.

**Stack:** FastAPI · LangChain / LangGraph · Gemini · SQLite · Next.js · Tailwind

## How it works

```
Resident chat ─► Intake agent (LangChain create_agent + tools) ─┐
Resident form ──────────────────────────────────────────────────┼─► services ─► state machine + policy engine ─► SQLite
Admin actions ──────────────────────────────────────────────────┘      │
                                                  submit ─► Review graph (LangGraph)
                       check_policy (code) → assess (LLM) → guardrail (code) → [auto_approve → schedule] → persist
```

- **Community YAML** (`backend/app/communities/*.yaml`) sets each community's documents, slots, notice periods, fees, which rules apply, and how much autonomy the agent has. Adding a community means adding a file.
- **The policy engine** (`backend/app/core/policy.py`) checks the hard rules in plain code. The LLM never decides whether a rule passed.
- **The state machine** (`backend/app/core/state_machine.py`) controls who may change a request's status. The agent can approve (only when policy allows it) and schedule, but only a human can reject.
- **The intake agent** extracts details, asks only for what's missing, explains the rules, and submits once the resident confirms.
- **The review graph** writes the admin brief, catches what rules can't (for example name mismatches across documents), and auto-approves only when policy, the community's config, and the LLM all agree.
- **Resilience:** Gemini calls fall back along a chain of models. If AI is unavailable, the review is built from the policy checks and residents can use the form instead.

## Run locally

Prerequisites: Python 3.12+ with [uv](https://docs.astral.sh/uv/), Node 20+, and a free Gemini key from https://aistudio.google.com/app/apikey

```bash
# backend
cd backend
echo "GOOGLE_API_KEY=your-key" > .env
uv sync
uv run uvicorn app.main:app --port 8000 --reload
```

```bash
# frontend (new terminal)
cd frontend
npm install
npm run dev
```

Open http://localhost:3000. Set `NEXT_PUBLIC_API_URL` if the backend isn't on `localhost:8000`, and `CORS_ORIGINS` on the backend if the frontend isn't on `localhost:3000`.

Optional: `GEMINI_MODELS` is a comma-separated list of models to try in order.

## Tests

```bash
cd backend && uv run pytest
```

The tests cover the policy rules, state machine permissions, the per-community differences, the full API workflow with the LLM disabled, and the agent's tools.

## Demo scenarios

| Community · Unit | Scenario |
|---|---|
| Green Valley · A-101 | Owner move-in on a weekend: auto-approved, gate pass issued by the agent |
| Green Valley · B-302 | Tenant move-in: needs police verification and owner NOC; admin reviews |
| Green Valley · A-202 (Priya Nair) | Move-out with ₹8,200 dues: blocked, admin asks for info |
| Sunrise Heights · 201 (Neha Kapoor) | Same dues situation: only a warning here, committee approves manually |
| Green Valley · B-301 | Move-in to an occupied flat: policy flags the conflict |
