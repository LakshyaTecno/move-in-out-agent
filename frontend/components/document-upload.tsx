"use client";

import { useRef, useState } from "react";

import { Button } from "@/components/ui";
import { api, type Community, type MoveRequest } from "@/lib/api";

/** The prototype records document metadata (type, file name, name on it,
 *  expiry) rather than storing files; see the explanation doc. */
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
  const [file, setFile] = useState<File | null>(null);
  const [nameOn, setNameOn] = useState("");
  const [validUntil, setValidUntil] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const required = request.resident_type
    ? (community.request_types[request.request_type].required_docs[request.resident_type] ?? [])
    : [];
  const uploaded = new Map(request.documents.map((d) => [d.doc_type, d]));

  async function run(action: () => Promise<MoveRequest>) {
    setBusy(true);
    setError("");
    try {
      onUploaded(await action());
      return true;
    } catch (e) {
      setError((e as Error).message);
      return false;
    } finally {
      setBusy(false);
    }
  }

  if (!request.resident_type) {
    return (
      <div className="space-y-2 text-sm">
        <p className="text-slate-600">Required documents depend on whether you own or rent the flat:</p>
        {editable ? (
          <div className="flex gap-2">
            {(["owner", "tenant"] as const).map((t) => (
              <Button
                key={t}
                variant="secondary"
                disabled={busy}
                onClick={() => run(() => api.updateRequest(request.id, { resident_type: t }))}
              >
                I&apos;m {t === "owner" ? "the owner" : "a tenant"}
              </Button>
            ))}
          </div>
        ) : null}
        {error && <p className="text-red-600">{error}</p>}
      </div>
    );
  }

  function pick(docType: string) {
    setTarget(docType);
    setFile(null);
    setNameOn(request.resident_name ?? "");
    setValidUntil("");
    setError("");
    fileInput.current?.click();
  }

  async function save() {
    if (!target || !file) return;
    const ok = await run(() =>
      api.uploadDocument(request.id, {
        doc_type: target,
        file_name: file.name,
        name_on_document: nameOn || null,
        valid_until: validUntil || null,
      }),
    );
    if (ok) setTarget(null);
  }

  return (
    <div className="space-y-2">
      <input
        ref={fileInput}
        type="file"
        accept=".pdf,.jpg,.jpeg,.png"
        className="hidden"
        onChange={(e) => {
          setFile(e.target.files?.[0] ?? null);
          e.target.value = ""; // allow picking the same file again
        }}
      />
      <ul className="space-y-2">
        {required.map((docType) => {
          const doc = uploaded.get(docType);
          const active = target === docType && file;
          return (
            <li
              key={docType}
              className={`rounded-lg border px-3 py-2 text-sm ${doc ? "border-emerald-200 bg-emerald-50/50" : "border-slate-200"}`}
            >
              <div className="flex items-center justify-between gap-2">
                <div className="min-w-0">
                  <div className="font-medium">
                    {doc ? <span className="text-emerald-700">✓ </span> : null}
                    {community.doc_catalog[docType]}
                  </div>
                  {doc && (
                    <div className="truncate text-xs text-slate-500">
                      {doc.file_name}
                      {doc.name_on_document && ` · ${doc.name_on_document}`}
                      {doc.valid_until && ` · valid until ${doc.valid_until}`}
                    </div>
                  )}
                </div>
                {editable && !active && (
                  <Button
                    variant={doc ? "secondary" : "primary"}
                    className="shrink-0 px-2.5 py-1 text-xs"
                    disabled={busy}
                    onClick={() => pick(docType)}
                  >
                    {doc ? "Replace" : "Choose file"}
                  </Button>
                )}
              </div>

              {active && (
                <div className="mt-2 space-y-2 rounded-md bg-slate-50 p-2">
                  <div className="truncate text-xs text-slate-700">📎 {file.name}</div>
                  <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                    <label className="text-xs text-slate-600">
                      Name on document
                      <input
                        className="mt-0.5 w-full rounded border border-slate-300 bg-white px-2 py-1 text-xs"
                        value={nameOn}
                        onChange={(e) => setNameOn(e.target.value)}
                      />
                    </label>
                    <label className="text-xs text-slate-600">
                      Valid until (optional)
                      <input
                        className="mt-0.5 w-full rounded border border-slate-300 bg-white px-2 py-1 text-xs"
                        type="date"
                        value={validUntil}
                        onChange={(e) => setValidUntil(e.target.value)}
                      />
                    </label>
                  </div>
                  <div className="flex gap-2">
                    <Button className="px-2.5 py-1 text-xs" disabled={busy} onClick={save}>
                      {busy ? "Uploading…" : "Upload"}
                    </Button>
                    <Button variant="secondary" className="px-2.5 py-1 text-xs" onClick={() => setTarget(null)}>
                      Cancel
                    </Button>
                  </div>
                </div>
              )}
            </li>
          );
        })}
      </ul>
      {error && <p className="text-sm text-red-600">{error}</p>}
      {!editable && request.documents.length === 0 && <p className="text-sm text-slate-500">No documents.</p>}
    </div>
  );
}
