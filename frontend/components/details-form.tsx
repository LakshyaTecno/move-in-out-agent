"use client";

import { useState } from "react";

import { Button, FIELD_LABEL } from "@/components/ui";
import type { Community, MoveRequest } from "@/lib/api";

const FIELDS = ["resident_name", "phone", "unit", "resident_type", "move_date", "slot", "household_size", "vehicle_count", "notes"] as const;
type Field = (typeof FIELDS)[number];

/** Non-AI path to complete a request, so residents are never blocked if the assistant is down. */
export function DetailsForm({
  request,
  community,
  onSave,
  onCancel,
}: {
  request: MoveRequest;
  community: Community;
  onSave: (fields: Partial<MoveRequest>) => void;
  onCancel: () => void;
}) {
  const [values, setValues] = useState<Record<Field, string>>(
    () => Object.fromEntries(FIELDS.map((f) => [f, request[f] == null ? "" : String(request[f])])) as Record<Field, string>,
  );
  const required = community.request_types[request.request_type].required_fields;
  const set = (f: Field) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
    setValues((v) => ({ ...v, [f]: e.target.value }));

  function save() {
    const fields: Record<string, string | number> = {};
    for (const f of FIELDS) {
      if (values[f] === "") continue;
      fields[f] = f === "household_size" || f === "vehicle_count" ? Number(values[f]) : values[f];
    }
    onSave(fields as Partial<MoveRequest>);
  }

  const input = "w-full rounded-lg border border-slate-300 px-2.5 py-1.5 text-sm";

  return (
    <div className="space-y-2.5">
      {FIELDS.map((f) => (
        <label key={f} className="block text-sm">
          <span className="text-slate-600">
            {FIELD_LABEL[f]}
            {required.includes(f) && <span className="text-red-500"> *</span>}
          </span>
          {f === "resident_type" ? (
            <select className={input} value={values[f]} onChange={set(f)}>
              <option value="">Select…</option>
              <option value="owner">Owner</option>
              <option value="tenant">Tenant</option>
            </select>
          ) : f === "slot" ? (
            <select className={input} value={values[f]} onChange={set(f)}>
              <option value="">Select…</option>
              {community.slots.windows.map((w) => (
                <option key={w}>{w}</option>
              ))}
            </select>
          ) : f === "notes" ? (
            <textarea className={input} rows={2} value={values[f]} onChange={set(f)} />
          ) : (
            <input
              className={input}
              value={values[f]}
              onChange={set(f)}
              type={f === "move_date" ? "date" : f === "household_size" || f === "vehicle_count" ? "number" : "text"}
            />
          )}
        </label>
      ))}
      <div className="flex gap-2 pt-1">
        <Button onClick={save}>Save</Button>
        <Button variant="secondary" onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </div>
  );
}
