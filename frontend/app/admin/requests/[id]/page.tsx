"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { RecommendationBadge } from "@/components/recommendation";
import { Button, Card, FIELD_LABEL, RuleList, StatusBadge, Timeline, formatDate, requestLabel } from "@/components/ui";
import { api, type Community, type MoveRequest, type Status } from "@/lib/api";

type Action = { action: string; label: string; status: Status; variant: "primary" | "secondary" | "danger"; needsNote?: boolean };

const ACTIONS: Action[] = [
  { action: "approve", label: "Approve", status: "approved", variant: "primary" },
  { action: "schedule", label: "Confirm slot & issue gate pass", status: "scheduled", variant: "primary" },
  { action: "complete", label: "Mark move completed", status: "completed", variant: "primary" },
  { action: "request_info", label: "Ask resident for info", status: "needs_info", variant: "secondary", needsNote: true },
  { action: "reject", label: "Reject", status: "rejected", variant: "danger", needsNote: true },
];

export default function AdminRequestPage() {
  const { id } = useParams<{ id: string }>();
  const [req, setReq] = useState<MoveRequest | null>(null);
  const [community, setCommunity] = useState<Community | null>(null);
  const [pending, setPending] = useState<Action | null>(null);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(() => api.getRequest(id, "admin").then((r) => (setReq(r), r)), [id]);

  useEffect(() => {
    load()
      .then(async (r) => setCommunity((await api.communities()).find((c) => c.id === r.community_id) ?? null))
      .catch((e) => setError(e.message));
  }, [load]);

  async function run(fn: () => Promise<MoveRequest>) {
    setBusy(true);
    setError("");
    try {
      setReq(await fn());
      setPending(null);
      setNote("");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  function choose(a: Action) {
    setError("");
    setNote(a.action === "request_info" ? (req?.review?.questions_for_resident.join("\n") ?? "") : "");
    const blocked = a.action === "approve" && req?.policy_results.some((r) => r.status === "fail" || r.status === "pending");
    if (a.needsNote || blocked) setPending(a);
    else run(() => api.adminAction(id, a.action));
  }

  if (!req || !community) return <p className="text-slate-500">{error || "Loading…"}</p>;

  const review = req.review;
  const available = ACTIONS.filter((a) => req.allowed_actions.includes(a.status));
  const failing = req.policy_results.filter((r) => r.status === "fail" || r.status === "pending");

  return (
    <div className="space-y-4">
      <Link href="/admin" className="text-sm text-slate-500 hover:text-slate-800">
        ← Back to queue
      </Link>
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-xl font-semibold">
          {requestLabel(req.request_type)} · {req.unit} · {req.resident_name}
        </h1>
        <StatusBadge status={req.status} />
        <span className="text-xs text-slate-400">
          {community.name} · #{req.id}
        </span>
      </div>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
        <div className="space-y-4">
          <Card className="border-fuchsia-200">
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">AI review</h2>
              <RecommendationBadge review={review} />
            </div>
            {review ? (
              <div className="space-y-3 text-sm">
                <p className="text-base text-slate-900">{review.summary}</p>
                <p className="text-slate-600">{review.reasoning}</p>
                {review.guardrail_note && (
                  <p className="rounded-lg bg-amber-50 px-3 py-2 text-amber-900">🛡 {review.guardrail_note}</p>
                )}
                {review.risk_flags.length > 0 && (
                  <div>
                    <div className="font-medium text-slate-800">Flags</div>
                    <ul className="list-disc pl-5 text-slate-700">
                      {review.risk_flags.map((f) => (
                        <li key={f}>{f}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {review.generated_by === "seed" && (
                  <p className="text-xs text-slate-500">
                    Demo request: this brief was pre-written. Requests you create are reviewed live by the agent.
                  </p>
                )}
                {review.generated_by === "fallback" && (
                  <div className="flex items-center justify-between gap-2 rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-600">
                    AI was unavailable; this summary was built from the policy checks.
                    <Button variant="secondary" className="px-2 py-1 text-xs" disabled={busy} onClick={() => run(() => api.regenerateReview(id))}>
                      Re-run AI review
                    </Button>
                  </div>
                )}
              </div>
            ) : (
              <p className="text-sm text-slate-500">Not reviewed yet.</p>
            )}
          </Card>

          <Card title="Policy checks">
            <RuleList results={req.policy_results} />
          </Card>

          <Card title="Request details">
            <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-sm">
              {Object.keys(FIELD_LABEL).map((f) => {
                const v = req[f as keyof MoveRequest];
                if (v == null || v === "") return null;
                return (
                  <div key={f} className="contents">
                    <dt className="text-slate-500">{FIELD_LABEL[f]}</dt>
                    <dd className="font-medium capitalize">{f === "move_date" ? formatDate(String(v)) : String(v)}</dd>
                  </div>
                );
              })}
            </dl>
            <h3 className="mb-1 mt-4 text-sm font-medium text-slate-700">Documents</h3>
            <ul className="space-y-1 text-sm">
              {req.documents.map((d) => (
                <li key={d.doc_type}>
                  <span className="font-medium">{community.doc_catalog[d.doc_type] ?? d.doc_type}</span>
                  <span className="text-slate-500">
                    {" "}
                    · {d.file_name}
                    {d.name_on_document && ` · name: ${d.name_on_document}`}
                    {d.valid_until && ` · valid until ${d.valid_until}`}
                  </span>
                </li>
              ))}
              {req.documents.length === 0 && <li className="text-slate-500">None</li>}
            </ul>
          </Card>
        </div>

        <div className="space-y-4">
          <Card title="Decide">
            {req.gate_pass && (
              <div className="mb-3 rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-900">
                Gate pass <span className="font-mono font-bold">{req.gate_pass}</span> · {formatDate(req.move_date)} {req.slot}
              </div>
            )}
            {req.status === "needs_info" && req.info_request && (
              <div className="mb-3 rounded-lg bg-orange-50 px-3 py-2 text-sm text-orange-900">
                Waiting on resident: {req.info_request}
              </div>
            )}
            {available.length === 0 && <p className="text-sm text-slate-500">No actions available in this status.</p>}
            {!pending && (
              <div className="flex flex-col gap-2">
                {available.map((a) => (
                  <Button key={a.action} variant={a.variant} disabled={busy} onClick={() => choose(a)}>
                    {a.label}
                  </Button>
                ))}
              </div>
            )}
            {pending && (
              <div className="space-y-2">
                <div className="text-sm font-medium">{pending.label}</div>
                {pending.action === "approve" && (
                  <p className="text-xs text-amber-800">
                    {failing.length} blocking check(s) not passing. Approving is an override — add a reason for the record.
                  </p>
                )}
                <textarea
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                  rows={4}
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  placeholder={
                    pending.action === "request_info"
                      ? "What does the resident need to provide?"
                      : pending.action === "reject"
                        ? "Reason (shown to the resident)"
                        : "Override reason"
                  }
                />
                {pending.action === "request_info" && review?.questions_for_resident.length ? (
                  <p className="text-xs text-slate-500">Pre-filled from the AI review. Edit before sending.</p>
                ) : null}
                <div className="flex gap-2">
                  <Button
                    variant={pending.variant}
                    disabled={busy || !note.trim()}
                    onClick={() => run(() => api.adminAction(id, pending.action, note))}
                  >
                    Confirm
                  </Button>
                  <Button variant="secondary" onClick={() => setPending(null)}>
                    Back
                  </Button>
                </div>
              </div>
            )}
            {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
          </Card>

          <Card title="Timeline">
            <Timeline events={req.history} />
          </Card>
        </div>
      </div>
    </div>
  );
}
