import type { ReviewBrief } from "@/lib/api";

const STYLE = {
  approve: "bg-emerald-100 text-emerald-800",
  request_info: "bg-orange-100 text-orange-800",
  reject: "bg-red-100 text-red-800",
};

const LABEL = { approve: "Approve", request_info: "Ask for info", reject: "Reject" };

export function RecommendationBadge({ review }: { review?: ReviewBrief | null }) {
  if (!review) return <span className="text-xs text-slate-400">—</span>;
  if (review.auto_approved)
    return <span className="rounded-full bg-fuchsia-100 px-2.5 py-0.5 text-xs font-semibold text-fuchsia-800">Auto-approved</span>;
  return (
    <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${STYLE[review.recommendation]}`}>
      AI: {LABEL[review.recommendation]}
    </span>
  );
}
