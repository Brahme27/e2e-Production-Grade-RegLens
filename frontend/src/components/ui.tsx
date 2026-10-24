import type { ReactNode } from "react";

export function PageHeader({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <header className="mb-6">
      <h1 className="text-2xl font-semibold text-slate-900">{title}</h1>
      {subtitle && <p className="mt-1 text-sm text-slate-600">{subtitle}</p>}
    </header>
  );
}

export function Card({ title, children, className = "" }: { title?: string; children: ReactNode; className?: string }) {
  return (
    <section className={`rounded-xl border border-slate-200 bg-white p-5 shadow-sm ${className}`}>
      {title && <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">{title}</h2>}
      {children}
    </section>
  );
}

export function Stat({ label, value, hint }: { label: string; value: ReactNode; hint?: string }) {
  return (
    <div className="rounded-lg bg-slate-50 p-3">
      <div className="text-xs text-slate-500">{label}</div>
      <div className="mt-1 text-xl font-semibold text-slate-900">{value}</div>
      {hint && <div className="mt-0.5 text-xs text-slate-500">{hint}</div>}
    </div>
  );
}

const REGULATOR_STYLE: Record<string, string> = {
  RBI: "bg-orange-100 text-orange-800",
  SEBI: "bg-violet-100 text-violet-800",
  FCA: "bg-sky-100 text-sky-800",
  PRA: "bg-emerald-100 text-emerald-800",
  INTERNAL: "bg-slate-200 text-slate-800",
};

export function RegulatorBadge({ regulator }: { regulator: string }) {
  return (
    <span className={`rounded px-1.5 py-0.5 text-xs font-semibold ${REGULATOR_STYLE[regulator] ?? "bg-slate-100"}`}>
      {regulator}
    </span>
  );
}

const STATUS_STYLE: Record<string, string> = {
  current: "bg-emerald-100 text-emerald-800",
  superseded: "bg-rose-100 text-rose-800",
  future: "bg-amber-100 text-amber-800",
  covered: "bg-emerald-100 text-emerald-800",
  partially_covered: "bg-amber-100 text-amber-800",
  not_covered: "bg-rose-100 text-rose-800",
};

export function StatusBadge({ status }: { status: string }) {
  return (
    <span className={`rounded px-2 py-0.5 text-xs font-semibold ${STATUS_STYLE[status] ?? "bg-slate-100 text-slate-700"}`}>
      {status.replace("_", " ")}
    </span>
  );
}

export function Table({ headers, rows }: { headers: string[]; rows: ReactNode[][] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-slate-200 text-left text-slate-500">
            {headers.map((h) => (
              <th key={h} className="px-2 py-2 font-medium">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className="border-b border-slate-100 align-top last:border-0">
              {row.map((cell, j) => (
                <td key={j} className="px-2 py-2 text-slate-800">
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function Loading({ label = "Loading…" }: { label?: string }) {
  return <p className="text-sm text-slate-500">{label}</p>;
}

export function ErrorBox({ message }: { message: string }) {
  return (
    <div data-testid="error-box" className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">
      {message}
    </div>
  );
}

export function Note({ children }: { children: ReactNode }) {
  return <p className="mt-3 rounded-lg bg-brand-light p-3 text-xs text-slate-700">{children}</p>;
}
