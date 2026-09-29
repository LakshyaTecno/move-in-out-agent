import type { HistoryEvent, RuleResult, Status } from "@/lib/api";

export const STATUS_LABEL: Record<Status, string> = {
  draft: "Draft",
  submitted: "Submitted",
  under_review: "Under review",
  needs_info: "Needs info",
  approved: "Approved",
  scheduled: "Scheduled",
  completed: "Completed",
  rejected: "Rejected",
  cancelled: "Cancelled",
};

const STATUS_STYLE: Record<Status, string> = {
  draft: "bg-slate-100 text-slate-700",
  submitted: "bg-blue-100 text-blue-800",
  under_review: "bg-amber-100 text-amber-800",
  needs_info: "bg-orange-100 text-orange-800",
  approved: "bg-emerald-100 text-emerald-800",
  scheduled: "bg-emerald-600 text-white",
  completed: "bg-slate-700 text-white",
  rejected: "bg-red-100 text-red-800",
  cancelled: "bg-slate-200 text-slate-500",
};

export function StatusBadge({ status }: { status: Status }) {
  return (
    <span className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-semibold ${STATUS_STYLE[status]}`}>
      {STATUS_LABEL[status]}
    </span>
  );
}

export const FIELD_LABEL: Record<string, string> = {
  resident_name: "Name",
  phone: "Phone",
  unit: "Flat / unit",
  resident_type: "Owner or tenant",
  move_date: "Move date",
  slot: "Time slot",
  household_size: "People moving",
  vehicle_count: "Vehicles",
  notes: "Notes",
};

export const RULE_LABEL: Record<string, string> = {
  required_fields: "Details complete",
  documents_complete: "Documents complete",
  document_validity: "Documents valid",
  lead_time: "Advance booking",
  notice_period: "Notice period",
  slot_allowed: "Allowed moving window",
  slot_available: "Slot capacity",
  unit_available_for_move_in: "Unit available",
  requester_is_occupant: "Requester is occupant",
  dues_cleared: "Dues cleared",
};

const RULE_ICON: Record<RuleResult["status"], string> = {
  pass: "✓",
  fail: "✕",
  warn: "!",
  pending: "…",
};

const RULE_STYLE: Record<RuleResult["status"], string> = {
  pass: "bg-emerald-100 text-emerald-700",
  fail: "bg-red-100 text-red-700",
  warn: "bg-amber-100 text-amber-700",
  pending: "bg-slate-100 text-slate-500",
};

export function RuleList({ results }: { results: RuleResult[] }) {
  return (
    <ul className="space-y-2">
      {results.map((r) => (
        <li key={r.rule} className="flex gap-3 text-sm">
          <span
            className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-xs font-bold ${RULE_STYLE[r.status]}`}
          >
            {RULE_ICON[r.status]}
          </span>
          <div>
            <div className="font-medium text-slate-800">
              {RULE_LABEL[r.rule] ?? r.rule}
              {!r.blocking && <span className="ml-2 text-xs font-normal text-slate-500">(advisory)</span>}
            </div>
            <div className="text-slate-600">{r.message}</div>
          </div>
        </li>
      ))}
    </ul>
  );
}

const ACTOR_STYLE: Record<HistoryEvent["actor"], string> = {
  resident: "bg-blue-500",
  admin: "bg-violet-600",
  agent: "bg-fuchsia-500",
  system: "bg-slate-400",
};

export function Timeline({ events }: { events: HistoryEvent[] }) {
  return (
    <ol className="space-y-3">
      {[...events].reverse().map((e, i) => (
        <li key={i} className="flex gap-3 text-sm">
          <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${ACTOR_STYLE[e.actor]}`} />
          <div>
            <div className="text-slate-800">
              <span className="font-medium capitalize">{e.actor}</span>{" "}
              {e.to_status ? `→ ${STATUS_LABEL[e.to_status]}` : e.action.replaceAll("_", " ")}
            </div>
            {e.note && <div className="text-slate-600">{e.note}</div>}
            <div className="text-xs text-slate-400">{new Date(e.at).toLocaleString()}</div>
          </div>
        </li>
      ))}
    </ol>
  );
}

export function Card({ title, children, className = "" }: { title?: string; children: React.ReactNode; className?: string }) {
  return (
    <section className={`rounded-xl border border-slate-200 bg-white p-4 shadow-sm ${className}`}>
      {title && <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">{title}</h2>}
      {children}
    </section>
  );
}

export function Button({
  variant = "primary",
  className = "",
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "danger" }) {
  const styles = {
    primary: "bg-brand text-white hover:bg-brand-dark",
    secondary: "border border-slate-300 bg-white text-slate-700 hover:bg-slate-50",
    danger: "bg-red-600 text-white hover:bg-red-700",
  };
  return (
    <button
      {...props}
      className={`rounded-lg px-3.5 py-2 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-50 ${styles[variant]} ${className}`}
    />
  );
}

export function formatDate(iso?: string | null) {
  if (!iso) return "—";
  return new Date(iso + "T00:00:00").toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short" });
}

export const requestLabel = (t: string) => (t === "move_in" ? "Move-in" : "Move-out");
