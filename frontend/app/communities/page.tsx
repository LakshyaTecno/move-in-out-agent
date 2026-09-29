"use client";

import { useEffect, useState } from "react";

import { Card, RULE_LABEL } from "@/components/ui";
import { api, type Community, type RequestType } from "@/lib/api";

/** Shows that communities differ only by configuration: the same workflow
 *  code runs for both, driven by each one's YAML. */
export default function CommunitiesPage() {
  const [communities, setCommunities] = useState<Community[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    api.communities().then(setCommunities).catch((e) => setError(e.message));
  }, []);

  const rows: { label: string; value: (c: Community) => React.ReactNode }[] = [
    { label: "Moving days", value: (c) => c.slots.days.join(", ") },
    { label: "Time windows", value: (c) => `${c.slots.windows.join(", ")} (max ${c.slots.max_per_window} per window)` },
    { label: "Blackout dates", value: (c) => c.slots.blackout_dates.join(", ") || "None" },
    {
      label: "Agent may auto-approve",
      value: (c) => c.autonomy.auto_approve.map((k) => k.replace("_", " ").replace("_", "-")).join(", ") || "Nothing: every request goes to a human",
    },
    { label: "Agent books slot & gate pass", value: (c) => (c.autonomy.auto_schedule ? "Yes, after approval" : "No, admin confirms") },
  ];

  const typeRows = (t: RequestType): typeof rows => [
    {
      label: "Documents (owner)",
      value: (c) => c.request_types[t].required_docs.owner?.map((d) => c.doc_catalog[d]).join(", "),
    },
    {
      label: "Documents (tenant)",
      value: (c) => c.request_types[t].required_docs.tenant?.map((d) => c.doc_catalog[d]).join(", "),
    },
    {
      label: "Rules",
      value: (c) => (
        <ul className="space-y-0.5">
          {c.request_types[t].rules.map((r) => (
            <li key={r.rule}>
              {RULE_LABEL[r.rule] ?? r.rule}
              {Object.keys(r.params).length > 0 && (
                <span className="text-slate-500"> ({Object.entries(r.params).map(([k, v]) => `${k.replace("_", " ")}: ${v}`).join(", ")})</span>
              )}
              {!r.blocking && <span className="ml-1 rounded bg-amber-100 px-1 text-xs text-amber-800">advisory</span>}
            </li>
          ))}
        </ul>
      ),
    },
    {
      label: "Fees",
      value: (c) =>
        Object.entries(c.request_types[t].fees)
          .map(([k, v]) => `${k.replaceAll("_", " ")}: ₹${v.toLocaleString("en-IN")}`)
          .join(", ") || "None",
    },
  ];

  const table = (title: string, data: typeof rows) => (
    <Card title={title}>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] table-fixed text-sm">
          <thead>
            <tr className="text-left">
              <th className="w-48 py-2" />
              {communities.map((c) => (
                <th key={c.id} className="py-2 pr-4 font-semibold">
                  {c.name}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 align-top">
            {data.map((row) => (
              <tr key={row.label}>
                <td className="py-2 pr-4 text-slate-500">{row.label}</td>
                {communities.map((c) => (
                  <td key={c.id} className="py-2 pr-4">
                    {row.value(c)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold">Community rules</h1>
        <p className="max-w-3xl text-sm text-slate-600">
          Each community is one YAML file. The workflow, agents, and rule implementations are shared; what varies is
          which rules apply, their parameters, required documents, slots, fees, and how much the agent may do on its
          own. Adding a community or changing a rule is a config change, not a code change.
        </p>
      </div>
      {error && <p className="text-sm text-red-600">{error}</p>}
      {communities.length > 0 && (
        <>
          {table("Scheduling & autonomy", rows)}
          {table("Move-in", typeRows("move_in"))}
          {table("Move-out", typeRows("move_out"))}
        </>
      )}
    </div>
  );
}
