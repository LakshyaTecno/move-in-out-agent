"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { RecommendationBadge } from "@/components/recommendation";
import { Card, StatusBadge, formatDate, requestLabel } from "@/components/ui";
import { api, type Community, type MoveRequest, type Status } from "@/lib/api";

const FILTERS: { label: string; statuses: Status[] | null }[] = [
  { label: "Needs decision", statuses: ["under_review"] },
  { label: "Waiting on resident", statuses: ["needs_info"] },
  { label: "Upcoming", statuses: ["approved", "scheduled"] },
  { label: "Closed", statuses: ["completed", "rejected", "cancelled"] },
  { label: "All", statuses: null },
];

// Surface what needs a human first, then soonest move date.
const PRIORITY: Partial<Record<Status, number>> = { under_review: 0, approved: 1, needs_info: 2, scheduled: 3 };

export default function AdminQueue() {
  const [communities, setCommunities] = useState<Community[]>([]);
  const [communityId, setCommunityId] = useState("");
  const [requests, setRequests] = useState<MoveRequest[]>([]);
  const [filter, setFilter] = useState(0);
  const [error, setError] = useState("");

  useEffect(() => {
    api.communities().then(setCommunities).catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    const load = () =>
      api
        .adminQueue(communityId || undefined)
        .then(setRequests)
        .catch((e) => setError(e.message));
    load();
    const t = setInterval(load, 10000);
    return () => clearInterval(t);
  }, [communityId]);

  const count = (s: Status[] | null) => requests.filter((r) => !s || s.includes(r.status)).length;
  const shown = requests
    .filter((r) => !FILTERS[filter].statuses || FILTERS[filter].statuses!.includes(r.status))
    .sort(
      (a, b) =>
        (PRIORITY[a.status] ?? 9) - (PRIORITY[b.status] ?? 9) || (a.move_date ?? "").localeCompare(b.move_date ?? ""),
    );
  const autoApproved = requests.filter((r) => r.review?.auto_approved).length;
  const name = (id: string) => communities.find((c) => c.id === id)?.name ?? id;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-semibold">Move requests</h1>
        <select
          className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
          value={communityId}
          onChange={(e) => setCommunityId(e.target.value)}
        >
          <option value="">All communities</option>
          {communities.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {[
          ["Needs your decision", count(["under_review"])],
          ["Waiting on resident", count(["needs_info"])],
          ["Upcoming moves", count(["approved", "scheduled"])],
          ["Handled by agent", autoApproved],
        ].map(([label, n]) => (
          <Card key={label}>
            <div className="text-2xl font-semibold">{n}</div>
            <div className="text-xs text-slate-500">{label}</div>
          </Card>
        ))}
      </div>

      <div className="flex flex-wrap gap-2">
        {FILTERS.map((f, i) => (
          <button
            key={f.label}
            onClick={() => setFilter(i)}
            className={`rounded-full px-3 py-1 text-sm ${
              filter === i ? "bg-slate-900 text-white" : "border border-slate-300 bg-white text-slate-600"
            }`}
          >
            {f.label} ({count(f.statuses)})
          </button>
        ))}
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
        <table className="w-full min-w-[720px] text-sm">
          <thead className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-4 py-2.5">Request</th>
              <th className="px-4 py-2.5">Resident</th>
              <th className="px-4 py-2.5">Move</th>
              <th className="px-4 py-2.5">AI review</th>
              <th className="px-4 py-2.5">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {shown.map((r) => (
              <tr key={r.id} className="hover:bg-slate-50">
                <td className="px-4 py-3">
                  <Link href={`/admin/requests/${r.id}`} className="font-medium text-brand hover:underline">
                    {requestLabel(r.request_type)} · {r.unit}
                  </Link>
                  <div className="text-xs text-slate-500">{name(r.community_id)}</div>
                </td>
                <td className="px-4 py-3">
                  {r.resident_name}
                  <div className="text-xs capitalize text-slate-500">{r.resident_type}</div>
                </td>
                <td className="px-4 py-3">
                  {formatDate(r.move_date)}
                  <div className="text-xs text-slate-500">{r.slot}</div>
                </td>
                <td className="px-4 py-3">
                  <RecommendationBadge review={r.review} />
                  {r.review && r.review.risk_flags.length > 0 && (
                    <div className="mt-1 text-xs text-slate-500">{r.review.risk_flags.length} flag(s)</div>
                  )}
                </td>
                <td className="px-4 py-3">
                  <StatusBadge status={r.status} />
                </td>
              </tr>
            ))}
            {shown.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-slate-500">
                  Nothing here.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
