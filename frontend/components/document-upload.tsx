"use client";

import { useState } from "react";

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
  const required = request.resident_type
    ? community.request_types[request.request_type].required_docs[request.resident_type] ?? []
    : [];
  const uploaded = new Map(request.documents.map((d) => [d.doc_type, d]));
  const [open, setOpen] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [nameOn, setNameOn] = useState(request.resident_name ?? "");
  const [validUntil, setValidUntil] = useState("");
  const [error, setError] = useState("");

  if (!request.resident_type) {
    return <p className="text-sm text-slate-500">Tell the assistant whether you&apos;re the owner or a tenant to see which documents you need.</p>;
  }

  async function upload(docType: string) {
    if (!file) return;
    setError("");
    try {
      onUploaded(
        await api.uploadDocument(request.id, {
          doc_type: docType,
          file_name: file.name,
          name_on_document: nameOn || null,
          valid_until: validUntil || null,
        }),
      );
      setOpen(null);
      setFile(null);
      setValidUntil("");
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <ul className="space-y-2">
      {required.map((docType) => {
        const doc = uploaded.get(docType);
        return (
          <li key={docType} className="rounded-lg border border-slate-100 px-3 py-2 text-sm">
            <div className="flex items-center justify-between gap-2">
              <div>
                <div className="font-medium">
                  {doc ? "✓ " : ""}
                  {community.doc_catalog[docType]}
                </div>
                {doc && (
                  <div className="text-xs text-slate-500">
                    {doc.file_name}
                    {doc.name_on_document && ` · ${doc.name_on_document}`}
                    {doc.valid_until && ` · valid until ${doc.valid_until}`}
                  </div>
                )}
              </div>
              {editable && open !== docType && (
                <button
                  className="shrink-0 text-xs font-medium text-brand hover:underline"
                  onClick={() => {
                    setOpen(docType);
                    setNameOn(request.resident_name ?? "");
                  }}
                >
                  {doc ? "Replace" : "Upload"}
                </button>
              )}
            </div>
            {open === docType && (
              <div className="mt-2 space-y-2">
                <input type="file" className="block w-full text-xs" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
                <div className="grid grid-cols-2 gap-2">
                  <input
                    className="rounded border border-slate-300 px-2 py-1 text-xs"
                    placeholder="Name on document"
                    value={nameOn}
                    onChange={(e) => setNameOn(e.target.value)}
                  />
                  <input
                    className="rounded border border-slate-300 px-2 py-1 text-xs"
                    type="date"
                    title="Valid until (optional)"
                    value={validUntil}
                    onChange={(e) => setValidUntil(e.target.value)}
                  />
                </div>
                <div className="flex gap-2">
                  <Button className="px-2.5 py-1 text-xs" disabled={!file} onClick={() => upload(docType)}>
                    Save
                  </Button>
                  <Button variant="secondary" className="px-2.5 py-1 text-xs" onClick={() => setOpen(null)}>
                    Cancel
                  </Button>
                </div>
              </div>
            )}
          </li>
        );
      })}
      {error && <li className="text-sm text-red-600">{error}</li>}
    </ul>
  );
}
