"use client";

import { useRef, useState } from "react";

import { Button } from "@/components/ui";
import { api, type Community, type DocVerdict, type MoveRequest } from "@/lib/api";

const VERDICT_STYLE: Record<DocVerdict, { box: string; icon: string; label: string }> = {
  verified: { box: "border-emerald-200 bg-emerald-50/60", icon: "✓", label: "Verified by AI" },
  problem: { box: "border-red-200 bg-red-50/60", icon: "✕", label: "Problem found" },
  unverified: { box: "border-amber-200 bg-amber-50/60", icon: "!", label: "Not verified, the office will check it" },
  waiting: { box: "border-slate-200 bg-slate-50", icon: "…", label: "Will be matched once your name is added" },
};

/** Each file is read by the AI on upload; only what it read is stored, never the file. */
export function DocumentUpload({
  request,
  community,
  editable,
  onUploaded,
}: {
  request: MoveRequest;
  community: Community;
  editable: boolean;
  onUploaded: (r: MoveRequest) => void;
}) {
  const fileInput = useRef<HTMLInputElement>(null);
  const [target, setTarget] = useState<string | null>(null); // doc type being uploaded
  const [busy, setBusy] = useState<string | null>(null); // doc type currently being read
  const [error, setError] = useState("");

  const required = request.resident_type
    ? (community.request_types[request.request_type].required_docs[request.resident_type] ?? [])
    : [];
  const uploaded = new Map(request.documents.map((d) => [d.doc_type, d]));
  const checks = new Map(request.checklist.document_checks.map((c) => [c.doc_type, c]));

  async function setResidentType(t: "owner" | "tenant") {
    setError("");
    try {
      onUploaded(await api.updateRequest(request.id, { resident_type: t }));
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function upload(docType: string, file: File) {
    setBusy(docType);
    setError("");
    try {
      onUploaded(await api.uploadFile(request.id, docType, file));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  if (!request.resident_type) {
    return (
      <div className="space-y-2 text-sm">
        <p className="text-slate-600">Required documents depend on whether you own or rent the flat:</p>
        {editable ? (
          <div className="flex gap-2">
            {(["owner", "tenant"] as const).map((t) => (
              <Button key={t} variant="secondary" onClick={() => setResidentType(t)}>
                I&apos;m {t === "owner" ? "the owner" : "a tenant"}
              </Button>
            ))}
          </div>
        ) : null}
        {error && <p className="text-red-600">{error}</p>}
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <input
        ref={fileInput}
        type="file"
        accept=".pdf,.jpg,.jpeg,.png,.webp"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          e.target.value = ""; // allow picking the same file again
          if (file && target) upload(target, file);
        }}
      />
      <p className="text-xs text-slate-500">Each upload is read and checked automatically by AI.</p>
      <ul className="space-y-2">
        {required.map((docType) => {
          const doc = uploaded.get(docType);
          const check = checks.get(docType);
          const style = check ? VERDICT_STYLE[check.verdict] : null;
          const reading = busy === docType;
          return (
            <li key={docType} className={`rounded-lg border px-3 py-2 text-sm ${style?.box ?? "border-slate-200"}`}>
              <div className="flex items-center justify-between gap-2">
                <div className="min-w-0">
                  <div className="font-medium">
                    {style && <span className="mr-1">{style.icon}</span>}
                    {community.doc_catalog[docType]}
                  </div>
                  {reading && <div className="text-xs text-slate-600">Reading document with AI…</div>}
                  {!reading && doc && check && (
                    <div className="text-xs text-slate-600">
                      <span className="font-medium">{style?.label}</span>
                      {check.verdict === "problem" && <span>: {check.detail.split(": ").slice(1).join(": ")}</span>}
                      <div className="truncate text-slate-500">
                        {doc.file_name}
                        {doc.name_on_document && ` · ${doc.name_on_document}`}
                        {doc.valid_until && ` · valid until ${doc.valid_until}`}
                      </div>
                    </div>
                  )}
                </div>
                {editable && (
                  <Button
                    variant={doc ? "secondary" : "primary"}
                    className="shrink-0 px-2.5 py-1 text-xs"
                    disabled={busy !== null}
                    onClick={() => {
                      setTarget(docType);
                      fileInput.current?.click();
                    }}
                  >
                    {reading ? "Reading…" : doc ? "Replace" : "Choose file"}
                  </Button>
                )}
              </div>
            </li>
          );
        })}
      </ul>
      {error && <p className="text-sm text-red-600">{error}</p>}
      {!editable && request.documents.length === 0 && <p className="text-sm text-slate-500">No documents.</p>}
    </div>
  );
}
