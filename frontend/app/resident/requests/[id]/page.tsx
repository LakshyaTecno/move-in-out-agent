"use client";

import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { Chat } from "@/components/chat";
import { DetailsForm } from "@/components/details-form";
import { DocumentUpload } from "@/components/document-upload";
import { Button, Card, FIELD_LABEL, StatusBadge, Timeline, formatDate, requestLabel } from "@/components/ui";
import { api, rememberRequest, type Community, type MoveRequest } from "@/lib/api";

const NEXT_STEP: Partial<Record<MoveRequest["status"], string>> = {
  under_review: "The management office is reviewing your request. You'll see updates here.",
  needs_info: "The office needs something from you. Update your request, then resubmit.",
  approved: "Approved! Your slot is being confirmed by the office.",
  scheduled: "You're all set. Show the gate pass to security on moving day.",
  completed: "Move completed. Thank you!",
  rejected: "Your request was not approved. See the timeline for the reason.",
};

export default function ResidentRequestPage() {
  const { id } = useParams<{ id: string }>();
  const [req, setReq] = useState<MoveRequest | null>(null);
  const [community, setCommunity] = useState<Community | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState(false);

  const load = useCallback(() => api.getRequest(id).then((r) => (setReq(r), r)), [id]);

  useEffect(() => {
    rememberRequest(id);
    Promise.all([load(), api.communities()])
      .then(([r, cs]) => setCommunity(cs.find((c) => c.id === r.community_id) ?? null))
      .catch((e) => setError(e.message));
  }, [id, load]);

  // Pick up admin decisions without a manual refresh.
  useEffect(() => {
    const t = setInterval(() => load().catch(() => {}), 10000);
    return () => clearInterval(t);
  }, [load]);

  async function run(action: () => Promise<MoveRequest>) {
    setBusy(true);
    setError("");
    try {
      setReq(await action());
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (!req || !community) return <p className="text-slate-500">{error || "Loading…"}</p>;

  const cl = req.checklist;
  const editable = req.status === "draft" || req.status === "needs_info";
  const ready = cl.missing_fields.length === 0 && cl.documents_missing.length === 0;
  const canCancel = req.allowed_actions.includes("cancelled");

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-xl font-semibold">
          {requestLabel(req.request_type)} · {community.name}
        </h1>
        <StatusBadge status={req.status} />
        <span className="text-xs text-slate-400">#{req.id}</span>
      </div>

      {NEXT_STEP[req.status] && (
        <div className="rounded-lg border border-brand/30 bg-brand-light px-4 py-3 text-sm text-slate-800">
          {NEXT_STEP[req.status]}
        </div>
      )}
      {req.status === "needs_info" && cl.admin_question && (
        <div className="rounded-lg border border-orange-300 bg-orange-50 px-4 py-3 text-sm">
          <div className="font-semibold text-orange-900">Message from the management office</div>
          <div className="text-orange-900">{cl.admin_question}</div>
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)]">
        <Chat requestId={req.id} onRequestUpdate={setReq} />

        <div className="space-y-4">
          {req.gate_pass && (
            <Card className="border-emerald-300 bg-emerald-50">
              <div className="text-xs font-semibold uppercase tracking-wide text-emerald-700">Gate pass</div>
              <div className="font-mono text-2xl font-bold text-emerald-900">{req.gate_pass}</div>
              <div className="text-sm text-emerald-800">
                {formatDate(req.move_date)} · {req.slot} · Unit {req.unit}
              </div>
            </Card>
          )}

          <Card title="Your request">
            {editing ? (
              <DetailsForm
                request={req}
                community={community}
                onCancel={() => setEditing(false)}
                onSave={(fields) =>
                  run(async () => {
                    const r = await api.updateRequest(req.id, fields);
                    setEditing(false);
                    return r;
                  })
                }
              />
            ) : (
              <>
                <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-sm">
                  {community.request_types[req.request_type].required_fields.map((f) => {
                    const v = req[f as keyof MoveRequest] as string | number | null | undefined;
                    return (
                      <div key={f} className="contents">
                        <dt className="text-slate-500">{FIELD_LABEL[f] ?? f}</dt>
                        <dd className={v == null || v === "" ? "text-slate-400 italic" : "font-medium"}>
                          {v == null || v === "" ? "needed" : f === "move_date" ? formatDate(String(v)) : String(v)}
                        </dd>
                      </div>
                    );
                  })}
                </dl>
                {editable && (
                  <button className="mt-3 text-sm font-medium text-brand hover:underline" onClick={() => setEditing(true)}>
                    Edit with a form instead
                  </button>
                )}
              </>
            )}
          </Card>

          <Card title="Documents">
            <DocumentUpload request={req} community={community} editable={editable} onUploaded={setReq} />
          </Card>

          {(cl.issues.length > 0 || cl.warnings.length > 0) && (
            <Card title="Things to fix">
              <ul className="space-y-1 text-sm">
                {cl.issues.map((m) => (
                  <li key={m} className="text-red-700">
                    ✕ {m}
                  </li>
                ))}
                {cl.warnings.map((m) => (
                  <li key={m} className="text-amber-700">
                    ! {m}
                  </li>
                ))}
              </ul>
            </Card>
          )}

          {Object.keys(cl.fees).length > 0 && (
            <Card title="Fees">
              {Object.entries(cl.fees).map(([k, v]) => (
                <div key={k} className="flex justify-between text-sm">
                  <span className="capitalize">{k.replaceAll("_", " ")}</span>
                  <span className="font-medium">₹{v.toLocaleString("en-IN")}</span>
                </div>
              ))}
            </Card>
          )}

          <div className="flex flex-wrap gap-2">
            {editable && (
              <Button disabled={!ready || busy} onClick={() => run(() => api.submit(req.id))}>
                {busy ? "Submitting…" : req.status === "needs_info" ? "Resubmit" : "Submit request"}
              </Button>
            )}
            {canCancel && (
              <Button
                variant="secondary"
                disabled={busy}
                onClick={() => confirm("Cancel this request?") && run(() => api.cancel(req.id, "Cancelled by resident"))}
              >
                Cancel request
              </Button>
            )}
          </div>
          {editable && !ready && (
            <p className="text-xs text-slate-500">
              Submit unlocks once all details and documents are in. You can finish either in the chat or with the form.
            </p>
          )}
          {error && <p className="text-sm text-red-600">{error}</p>}

          <Card title="Timeline">
            <Timeline events={req.history} />
          </Card>
        </div>
      </div>
    </div>
  );
}
