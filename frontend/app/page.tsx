import Link from "next/link";

const SCENARIOS = [
  ["Green Valley · A-101", "Owner move-in on a weekend → auto-approved and gate pass issued by the agent"],
  ["Green Valley · B-302", "Tenant move-in → needs police verification + owner NOC; admin reviews"],
  ["Green Valley · A-202 (Priya Nair)", "Move-out with Rs 8,200 dues → blocked; admin asks for info"],
  ["Sunrise Heights · 201 (Neha Kapoor)", "Same dues situation → only a warning here; committee approves manually"],
  ["Green Valley · B-301", "Move-in to an occupied flat → policy flags the conflict"],
];

export default function Home() {
  return (
    <div className="space-y-8">
      <section className="space-y-3">
        <h1 className="text-3xl font-semibold tracking-tight">Move-in / move-out, handled by an agent</h1>
        <p className="max-w-2xl text-slate-600">
          Residents describe their move in plain language and an assistant turns it into a complete request, following
          each community&apos;s own rules. Admins get a reviewed request with a recommendation, risks, and the
          checks behind it. Clean cases can be approved and scheduled automatically where a community allows it.
        </p>
      </section>

      <div className="grid gap-4 md:grid-cols-3">
        <Link href="/resident" className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm hover:border-brand">
          <div className="text-lg font-semibold">I&apos;m a resident →</div>
          <p className="mt-1 text-sm text-slate-600">Start a move-in or move-out, upload documents, track status.</p>
        </Link>
        <Link href="/admin" className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm hover:border-brand">
          <div className="text-lg font-semibold">I&apos;m an admin →</div>
          <p className="mt-1 text-sm text-slate-600">Review the queue with AI briefs and act on requests.</p>
        </Link>
        <Link
          href="/communities"
          className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm hover:border-brand"
        >
          <div className="text-lg font-semibold">Community rules →</div>
          <p className="mt-1 text-sm text-slate-600">See how two communities configure the same workflow differently.</p>
        </Link>
      </div>

      <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="mb-3 font-semibold">Try these demo scenarios</h2>
        <ul className="space-y-2 text-sm">
          {SCENARIOS.map(([who, what]) => (
            <li key={who} className="flex flex-col gap-0.5 sm:flex-row sm:gap-3">
              <span className="font-medium text-slate-800 sm:w-72 sm:shrink-0">{who}</span>
              <span className="text-slate-600">{what}</span>
            </li>
          ))}
        </ul>
        <p className="mt-4 text-xs text-slate-500">
          Moves need a date at least a few days out. Green Valley allows weekends only; Sunrise Heights allows any day.
        </p>
      </section>
    </div>
  );
}
