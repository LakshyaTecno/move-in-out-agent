"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Button, Card, StatusBadge, formatDate, requestLabel } from "@/components/ui";
import { api, myRequestIds, rememberRequest, type Community, type MoveRequest, type RequestType } from "@/lib/api";

export default function ResidentHome() {
  const router = useRouter();
  const [communities, setCommunities] = useState<Community[]>([]);
  const [communityId, setCommunityId] = useState("");
  const [mine, setMine] = useState<MoveRequest[]>([]);
  const [busy, setBusy] = useState<RequestType | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .communities()
      .then((cs) => {
        setCommunities(cs);
        setCommunityId(cs[0]?.id ?? "");
      })
      .catch((e) => setError(e.message));
    Promise.all(myRequestIds().map((id) => api.getRequest(id).catch(() => null))).then((rs) =>
      setMine(rs.filter((r): r is MoveRequest => r !== null)),
    );
  }, []);

  async function start(type: RequestType) {
    setBusy(type);
    try {
      const req = await api.createRequest(communityId, type);
      rememberRequest(req.id);
      router.push(`/resident/requests/${req.id}`);
    } catch (e) {
      setError((e as Error).message);
      setBusy(null);
    }
  }

  const community = communities.find((c) => c.id === communityId);

  return (
    <div className="grid gap-6 md:grid-cols-[1fr_1fr]">
      <Card title="Start a request">
        <label className="mb-1 block text-sm font-medium text-slate-700">Your community</label>
        <select
          className="mb-4 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
          value={communityId}
          onChange={(e) => setCommunityId(e.target.value)}
        >
          {communities.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
        <div className="grid grid-cols-2 gap-3">
          <Button onClick={() => start("move_in")} disabled={!communityId || busy !== null}>
            {busy === "move_in" ? "Starting…" : "I'm moving in"}
          </Button>
          <Button onClick={() => start("move_out")} disabled={!communityId || busy !== null}>
            {busy === "move_out" ? "Starting…" : "I'm moving out"}
          </Button>
        </div>
        {community && (
          <p className="mt-4 text-xs text-slate-500">
            Moves at {community.name}: {community.slots.days.join(", ")} · {community.slots.windows.join(", ")}
          </p>
        )}
        {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
      </Card>

      <Card title="My requests">
        {mine.length === 0 ? (
          <p className="text-sm text-slate-500">No requests yet from this browser.</p>
        ) : (
          <ul className="divide-y divide-slate-100">
            {mine.map((r) => (
              <li key={r.id}>
                <Link href={`/resident/requests/${r.id}`} className="flex items-center justify-between gap-3 py-2.5 hover:bg-slate-50">
                  <div className="text-sm">
                    <div className="font-medium">
                      {requestLabel(r.request_type)} · {r.unit ?? "unit not set"}
                    </div>
                    <div className="text-slate-500">
                      {communities.find((c) => c.id === r.community_id)?.name} · {formatDate(r.move_date)}
                    </div>
                  </div>
                  <StatusBadge status={r.status} />
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
