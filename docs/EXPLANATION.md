# Move-in / Move-out Agentic Workflow: Explanation

**Prototype:** https://move-in-out-agent.vercel.app · **API:** https://move-in-out-agent-api.onrender.com · **Code:** https://github.com/LakshyaTecno/move-in-out-agent

> The hosted backend runs on a free tier that sleeps when idle. The first request after a pause can take about 30–60 seconds.

---

## 1. Problem interpretation

Moving in or out of a gated community is a compliance process that looks like a form. Behind the request, the society has to answer a few questions:

- **Is this person entitled to do this?** Owner or tenant, the right unit, the unit actually vacant (for a move-in) or actually theirs (for a move-out).
- **Is the paperwork complete and consistent?** ID, sale deed or rental agreement, police verification, the owner's NOC. The names and dates have to agree across documents.
- **Is the society protected?** Dues cleared before anyone leaves, a damage deposit, notice given.
- **Can it happen safely on the day?** A slot within allowed days and hours, not on a blackout date, the service lift not double-booked, and security holding a gate pass.

**The two roles experience this very differently:**

| | Resident | Admin |
|---|---|---|
| Main pain | Doesn't know the rules and finds out what's missing only after several rounds with the office | Checks every request by hand, often the same checks, and chases missing information |
| Wants | "Tell me exactly what I need, let me say it my way, tell me when it's done" | "Show me what's wrong, what's risky, and let me decide in seconds" |

**Communities differ a lot:** a 1,000-flat township allows weekend moves only and needs police verification, while a 40-flat society allows any day and trusts residents. Hard-coding one process would fail most customers.

**My framing:** most of this is *deterministic rule checking*, and a smaller part is *language and judgement*. The design gives each part to the right tool. Code enforces the rules, the AI handles the conversation and the judgement calls, and each community's configuration decides how much the AI may do on its own.

---

## 2. The experiences

### 2.1 Resident journey

```
Start (pick community, move-in / move-out)
  → Describe the move in plain language to the assistant
  → Assistant fills the request, asks only for what's missing, explains rules & fees
  → Upload the documents it names (checklist updates live)
  → Confirm the summary → submit
  → Track: status, timeline, admin questions, gate pass
  → If "needs info": fix it (chat or form) → resubmit
```

Design choices and why:

- **Conversation first, with the form always available.** *"I'm renting B-302, moving in next Saturday morning with my wife"* is the fastest way to give 6 fields. The assistant turns that into structured data (resolving "next Saturday" to a date and "morning" to a real slot window). A plain form sits alongside it because some people prefer forms, and because the resident must never be blocked when the AI is unavailable.
- **The checklist is the source of truth, not the chat.** The right-hand panel always shows what's saved, what's missing and what's failing. The chat helps, but the resident never has to trust it blindly.
- **The assistant asks only for what this community needs.** A tenant in Green Valley is asked for police verification. The same tenant in Sunrise Heights isn't, because that community doesn't require it.
- **Confirm before submit.** The assistant summarises the request and submits only after an explicit "yes".
- **The loop closes in one place.** After submission, the same page shows the admin's questions, lets the resident fix and resubmit, and finally shows the gate pass to present at the gate.

### 2.2 Admin journey

```
Queue (prioritised: needs decision → approved-to-schedule → waiting on resident → scheduled)
  → Open request: AI brief (summary, recommendation, reasoning, flags)
  → Policy checks (pass / fail / advisory), details, documents, full timeline
  → Act: approve · ask for info (pre-drafted questions) · reject (reason required)
         · confirm slot & issue gate pass · mark completed
```

Design choices and why:

- **Read the brief, then decide.** The admin starts with a two-sentence summary and a recommendation, and every claim can be traced to a specific check or document underneath.
- **Show the evidence next to the AI's opinion.** The policy checks are shown separately from the AI's recommendation, so the admin can see exactly which facts it's based on.
- **"Ask for info" is prefilled with the agent's drafted questions**, which the admin can edit. This is the most common admin action and the most tedious to write.
- **Overrides are allowed but recorded.** An admin can approve despite a failing check (they're the human in charge), but must give a reason, which goes into the timeline.
- **The queue shows what the agent handled** ("Handled by agent" count, "Auto-approved" badge), so automation is visible and can be audited, never silent.

---

## 3. Architecture

```
┌──────────── Next.js (Vercel) ────────────┐
│ Resident: chat · checklist · uploads · form │
│ Admin: queue · brief · checks · actions      │
│ Community rules comparison                   │
└──────────────────┬───────────────────────────┘
                   │ REST
┌──────────────────▼──────────── FastAPI (Render) ─────────────────────────┐
│                                                                           │
│  Intake agent (LangChain create_agent)      Review graph (LangGraph)      │
│  tools bound to ONE request                 check_policy → assess(LLM)    │
│   update_request_details                      → guardrail → [auto_approve │
│   get_checklist · find_available_slots          → schedule] → persist     │
│   submit_request · cancel_request                                         │
│              │                                        │                   │
│              └──────────────┬─────────────────────────┘                   │
│                     services.py  ◄── REST handlers (UI) use the same layer │
│                   ┌─────────┴─────────┐                                   │
│           state_machine.py      policy.py (rule registry)                 │
│                   └─────────┬─────────┘                                   │
│              community YAML configs · store.py (SQLite)                   │
└───────────────────────────────────────────────────────────────────────────┘
```

| Layer | Responsibility | AI? |
|---|---|---|
| `communities/*.yaml` | Everything that differs between societies | – |
| `core/policy.py` | Rule implementations, registered by name, with parameters from YAML | No |
| `core/state_machine.py` | Allowed status transitions and **which role may make each one** | No |
| `services.py` | The only way to change a request. Validation, history log, slot booking, gate pass | No |
| `agents/intake.py` | Resident-facing conversational agent | Yes |
| `agents/review.py` | Admin-facing review pipeline | Yes (one node) |
| `store.py` | Persistence behind a small interface | No |

**Key principle: one path to change data.** The REST endpoints and the agents' tools both call `services.py`. So the agent can never do anything the UI couldn't, every change passes the same validation, and everything is recorded in the history with the acting role (`resident`, `admin`, `agent` or `system`).

**Stack:** Python 3.12, FastAPI, LangChain 1.x / LangGraph, Gemini (`langchain-google-genai`), SQLite, Next.js 16, Tailwind.

---

## 4. Agent design

### 4.1 Where AI creates value, and where it doesn't

| Task | Who does it | Why |
|---|---|---|
| Understand free-text details, resolve relative dates and slot wording | **LLM** (intake) | Language understanding is the LLM's strength, and it removes form friction |
| Decide what to ask next, explain rules in plain words | **LLM** (intake), driven by the checklist | It needs context and tone, but *what's missing* comes from code |
| Are the documents complete? Is notice sufficient? Dues cleared? Slot free? | **Code** (policy engine) | These must be exact, repeatable and auditable. An LLM guess here would be a liability |
| Do names match across documents? Does a resubmission answer the admin's question? Anything odd in the notes? | **LLM** (review) | Fuzzy judgement that rules can't express: "K. Shah" ≈ "Karan Shah", but "Karan Shaw" is a different name |
| Summarise for the admin, draft questions to the resident | **LLM** (review) | Saves the most admin time |
| Approve / reject | **Human by default.** Agent only under strict, configured conditions | Accountability |
| Book the slot, issue the gate pass | **Agent or admin**, per community config | Mechanical once approved |

### 4.2 The intake agent

- **Implementation:** LangChain `create_agent` (a tool-calling loop) with 5 tools, all **bound to a single request ID** created on the server. The agent can't read or change any other request, however it's prompted.
- **Tools:** `update_request_details` (validated through Pydantic and the service layer), `get_checklist`, `find_available_slots`, `submit_request`, `cancel_request`.
- **Context:** the system prompt is rebuilt on every turn from the community's config: allowed days, windows, blackout dates, required documents for each resident type, fees, guidance and house rules. It also includes a 15-day calendar, so "next Saturday" is resolved reliably. The agent learns the request's current state through `get_checklist`, not from memory.
- **Memory:** conversation history is saved by a LangGraph checkpointer (SQLite), using the request ID as the thread ID. A resident can leave and come back to the same conversation.
- **Handling ambiguity:** it saves what's clear straight away, then asks about what's missing or unclear a couple of items at a time. If a date isn't allowed or a slot is full, it says why and offers real alternatives from `find_available_slots`. It never invents rules that aren't in the config.
- **Honesty rule:** the agent may only say something was saved or submitted when a tool result confirms it. This rule came from testing (see §7).

### 4.3 The review pipeline (LangGraph)

```
check_policy ──► assess ──► guardrail ──┬─► auto_approve ─► persist
   (code)         (LLM)      (code)      └──────────────────► persist
```

1. **`check_policy`** runs the community's rules and returns a list of pass / fail / warn / pending results.
2. **`assess`** is one LLM call with **structured output** (a Pydantic `Assessment`: summary, recommendation, reasoning, risk flags, questions). The prompt tells the model that policy results are authoritative, and gives it the jobs rules can't do: comparing names, checking consistency, checking whether a resubmission answers the admin, and reading the notes.
3. **`guardrail`**: if the LLM recommends *approve* while any blocking rule fails, code overrides it to *request_info* and records why (`guardrail_note`, shown to the admin).
4. **`route` → `auto_approve`** only runs when **both keys turn**:
   - **Policy key:** every rule passed cleanly (not even a warning), and this exact case (e.g. `owner_move_in`) is in the community's `autonomy.auto_approve` list.
   - **AI key:** the LLM recommends approve and raised no risk flags.

   If `autonomy.auto_schedule` is on, the agent then books the slot and issues the gate pass.
5. **`persist`** saves the brief onto the request.

### 4.4 The autonomy ladder

| Level | What the agent does | Where it's enforced |
|---|---|---|
| **Guide** | Collects details, explains rules, finds slots | Always on (intake agent) |
| **Recommend** | Brief + recommendation + drafted questions | Always on (review graph) |
| **Decide** | Approves without a human | Only if the community opts in for that case, and both keys turn |
| **Act** | Books the slot, issues the gate pass, notifies security | Only if `auto_schedule` is on and the request is approved |
| **Never** | Reject, or override policy | **The state machine gives the agent role no permission to reject.** This is enforced in code and tested, not just stated in the prompt |

The boundaries are enforced in code at three layers: the tools (scoped to one request), the service layer (validation), and the state machine (who may make which transition). The prompt explains the boundaries to the model, but the code is what enforces them.

---

## 5. Scalability: configuration vs core logic

**Configuration (per community, YAML, no code changes):**

- Required details and **required documents for each resident type** (owner / tenant)
- **Which rules apply** to each request type, their **parameters** (e.g. `notice_period: {min_days: 7}`) and whether each one **blocks** approval or is **advisory**
- Moving days, time windows, capacity per window, blackout dates
- Fees, guidance text, house rules (the agent uses these to explain rules)
- **Autonomy:** which cases may be auto-approved, and whether the agent may schedule

The same situation handled two ways in the demo:

| | Green Valley | Sunrise Heights |
|---|---|---|
| Move-out with dues outstanding | `dues_cleared` blocks, so admin asks for payment | `dues_cleared: blocking: false`, so a warning is shown and dues are settled from the deposit |
| Clean owner move-in | Auto-approved, slot booked, gate pass issued by the agent | Goes to the committee, which confirms the slot manually |
| Tenant move-in documents | ID, rental agreement, police verification, owner NOC | ID, rental agreement |

The **Community rules** page in the prototype shows this side by side.

**Core logic (shared, changes rarely):** the rule implementations, the state machine, the service layer, the agents and the prompts.

**How it grows:**

- **New community:** add a YAML file. It's validated at startup (`validate_config` fails fast if a YAML names a rule that doesn't exist).
- **New rule** (e.g. "no moves during festival week", "max 2 vehicles"): write one ~10-line function decorated with `@rule("name")`, and any community can turn it on in YAML.
- **New request type** (e.g. interior renovation, pet registration): add a `RequestType` value and a YAML block. The state machine, agents and UI are generic over request types.
- **Production step:** the YAML becomes rows in a database with an admin UI for editing them. The schema (`CommunityConfig`) stays the same.

---

## 6. Assumptions

| Assumption | Why it was necessary | How production would differ |
|---|---|---|
| No real login; a role switch in the nav, and the resident's requests are remembered in the browser | Keeps the demo usable without creating accounts | ANACITY's existing resident/admin identity. Residents would be linked to units, and admins scoped to their communities |
| Unit occupancy and dues come from a seeded table | These normally live in ANACITY's resident and billing systems | Read through integrations. Policy rules would call those services instead of `store.get_unit` |
| Documents store **metadata only** (type, file name, name on it, expiry). The name/expiry are typed in by the resident | File storage and OCR are out of scope for a 24-hour prototype. The metadata is enough to show consistency checking | Files in object storage. OCR / document AI would extract names and dates instead of the resident typing them, and the review agent would reason over the extracted fields |
| Fees and deposits are collected by the office, outside the system | No payment integration | A payment step between approval and scheduling, with a `deposit_paid` rule |
| "Security notified" is a timeline entry | No SMS / WhatsApp / guard-app integration | Push the gate pass to the security app and to the resident via their preferred channel |
| Time slots are the only shared resource (capacity per window) | Stands in for the service lift and the loading bay | Model lifts and loading bays as separate resources, possibly per tower |
| Dates use the server's local date | Simple and consistent for a single-timezone demo | Community timezone in config |
| Gemini free tier | Free, hosted and good at tool calling | A paid tier with higher limits. The LLM layer is one small module and LangChain makes the provider swappable |

---

## 7. Testing and results

### Automated tests (`cd backend && uv run pytest`): 20 passing

- **Policy engine:** every rule, including pending vs fail for incomplete drafts.
- **Per-community behaviour:** the same request is auto-approvable in Green Valley and needs a human in Sunrise Heights; the same dues block in one community and only warn in the other.
- **State machine:** the full lifecycle, history recording, *the agent can never reject*, and review can't be skipped.
- **API end to end with the LLM disabled:** auto-approval and gate pass; incomplete submission refused; the dues → needs-info → resubmit round trip; an override without a reason refused; manual scheduling in Sunrise Heights; booked slots removed from availability; the admin brief hidden from residents.
- **Agent tools (no LLM):** details are saved correctly, invalid values return an error instead of crashing, and the agent can't submit an incomplete request.
- **Config validation:** every YAML only references rules that exist.

### Live testing with Gemini (manual)

| Scenario | Result |
|---|---|
| *"I am Karan Shah, renting B-302, moving in next Saturday morning with my wife. My number is 9812345678"* | All 7 fields extracted in one turn: date resolved, "morning" mapped to `09:00-13:00`, household size 2 from "with my wife" |
| Owner move-in (Asha Rao, A-101) via the UI | Submitted, **auto-approved, scheduled, gate pass issued** by the agent with no human involved |
| Tenant with the NOC made out to "Karan Shaw" | Review agent flagged the name mismatch, accepted "K. Shah" on the rental agreement, recommended *request info*, and drafted the question to the resident |

### Problems found by testing, and what changed

1. **A hallucinated success.** A bug in a tool meant nothing was saved, and the agent still told the resident *"I've saved your details."* The tool was fixed, a regression test was added, and the prompt now forbids confirming anything a tool didn't confirm. This is also why the checklist panel, not the chat, is the resident's source of truth.
2. **The model was retired.** `gemini-2.5-flash` returned 404 for new keys. The default moved to `gemini-3.8-flash`, and the model list is now configurable.
3. **Free-tier limits (5 requests/min per model, shared by everyone using the key).** One agent turn makes several model calls. The fix is a **fallback chain across models** that each have their own quota (`ModelFallbackMiddleware` for the agent, `with_fallbacks` for the review), with retries off so a 429 moves on straight away.
4. **Over-cautious confirmation.** The agent asked for confirmation after the resident had already said "yes please submit". The prompt now allows submitting directly when the request is explicit and complete.
5. **Slow turns on the hosted demo (25–50s).** Timing each model showed a trivial call taking 0.8s on `gemini-3.1-flash-lite`, 5.5s on `gemini-3.8-flash` (it "thinks" first) and 29s on `gemini-3.5-flash`, which was the first fallback. Benchmarking a full agent turn, `flash-lite` finished in 5.1s with the same correct behaviour. The agents now use **different chains for different jobs**: chat leads with the fastest model because it makes several calls per turn; review leads with the strongest because it's one call where judgement matters most. The slow model was dropped and the timeout cut to 20s.

---

## 8. Failure handling and recovery

| Failure | Behaviour |
|---|---|
| LLM rate-limited or down (intake) | Falls back through the model chain. If every model fails, the resident sees "assistant busy, use the form" and can still complete and submit the request with the form |
| LLM down (review) | A **deterministic brief** is built from the policy results (`generated_by: fallback`) and labelled in the UI. The admin can **re-run the AI review** later. The workflow never waits on AI |
| LLM recommends something policy forbids | The guardrail node overrides it and explains why to the admin |
| Agent passes bad data to a tool | Pydantic / service validation rejects it and the tool returns an error the agent can recover from. Nothing malformed is stored |
| Invalid status change (from any role) | The state machine refuses it with a clear error |
| Slot taken between approval and scheduling | Scheduling re-checks capacity and refuses, and the admin asks the resident to pick another slot |
| Bad community config | Startup fails with the exact YAML and rule name |
| Host restarts (free tier wipes the disk) | Demo units and five pre-reviewed requests are re-seeded on boot |

---

## 9. Limitations and trade-offs

- **SQLite on an ephemeral free host.** New requests are lost when the host restarts. That's acceptable for a demo; production would use Postgres, and only `store.py` changes.
- **Documents are metadata, not files.** The consistency checks are real, but they run on names the resident types in, not on extracted text.
- **No authentication.** Anyone with a request's URL can view it.
- **Synchronous LLM calls.** A chat reply takes a few seconds, and the review runs inside the submit request. Production would stream chat tokens and run the review in a background worker.
- **One LLM call for the review.** It's cheap, fast and easy to reason about. A multi-step reviewer (e.g. one that fetches documents or history on demand) could catch more, but it would be slower and harder to audit.
- **Deliberately narrow autonomy.** The agent only auto-approves cases a community has explicitly opted into. This trades some automation for trust. The ladder allows more autonomy as trust builds.
- **Hand-written seed briefs.** The pre-loaded demo requests have pre-written briefs (labelled in the UI) so the hosted demo doesn't spend rate-limited AI calls on boot. Requests created in the demo are reviewed live.

---

## 10. Next steps toward production

1. **Integrations:** ANACITY identity, unit / occupancy / billing APIs, payments, the security or gate app, and notifications.
2. **Document intelligence:** file storage, plus OCR / document AI to extract names, dates and IDs, so the review agent reasons over the documents themselves.
3. **Configuration as data:** community configs in a database, with an admin UI, version history, and a "preview impact" check before a rule change goes live.
4. **Reliability:** Postgres, a background worker for reviews, streaming chat, idempotent actions, and retries with backoff on a paid LLM tier.
5. **Evaluation:** a labelled set of requests (clean, missing documents, name mismatches, occupied units, dues) run on every prompt or model change. Track extraction accuracy, recommendation agreement with admins, and the auto-approval false-positive rate. Auto-approval scope should only grow when these numbers justify it.
6. **Observability:** trace every agent run (e.g. LangSmith), plus metrics on time-to-decision, the share of requests auto-handled, and the needs-info rate.
7. **Wider workflow:** a move-out inspection checklist and deposit refund, linking a move-out to the next tenant's move-in for the same unit, and multi-tower lift scheduling.
