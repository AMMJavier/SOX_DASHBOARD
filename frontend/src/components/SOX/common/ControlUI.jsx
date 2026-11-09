import { AlertTriangle, CheckCircle2, ClipboardList, Clock3, Info, FileText, CalendarDays, ShieldCheck } from "lucide-react";

export const FIELD = "mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-800 outline-none focus:border-blue-500";
export const PRIMARY = "inline-flex items-center justify-center gap-2 rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-blue-700";
export const SECONDARY = "inline-flex items-center justify-center gap-2 rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-sm font-medium text-slate-700 hover:bg-slate-50";

export function InfoBanner({ children, caution = false }) {
  return <div className={`flex items-start gap-3 rounded-xl border p-4 text-sm leading-6 ${caution ? "border-amber-200 bg-amber-50 text-amber-900" : "border-blue-200 bg-blue-50 text-blue-900"}`}>
    {caution ? <AlertTriangle size={19} className="mt-0.5 shrink-0"/> : <Info size={19} className="mt-0.5 shrink-0"/>}
    <div>{children}</div>
  </div>;
}

export function Panel({ title, description, action, children }) {
  return <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
    <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
      <div><h2 className="text-lg font-bold text-slate-900">{title}</h2>{description && <p className="mt-1 text-sm text-slate-500">{description}</p>}</div>
      {action}
    </div>{children}
  </section>;
}

const KPI = [
  { label: "Total evidencias", key: "total", icon: ClipboardList, color: "bg-blue-600" },
  { label: "Confirmadas", key: "confirmed", icon: CheckCircle2, color: "bg-green-600" },
  { label: "Pendientes", key: "pending", icon: Clock3, color: "bg-amber-500" },
  { label: "Vencidas", key: "expired", icon: AlertTriangle, color: "bg-red-600" },
];
export function EvidenceKpis({ metrics }) {
  return <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
    {KPI.map(({ label, key, icon: Icon, color }) => <div key={key} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className={`mb-3 flex h-12 w-12 items-center justify-center rounded-full ${color} text-white`}><Icon size={24}/></div>
      <p className="text-sm font-semibold text-slate-600">{label}</p><p className="mt-1 text-3xl font-bold text-slate-900">{metrics?.[key] ?? "—"}</p>
    </div>)}
  </div>;
}

export function ControlHeading({ number, title, description, frequency, responsible }) {
  return <header className="flex flex-wrap items-start justify-between gap-4">
    <div className="max-w-4xl">
      <p className="text-sm font-semibold text-blue-600">SOX / Control {number}</p>
      <h1 className="mt-1 text-3xl font-bold tracking-tight text-slate-900">{title}</h1>
      <p className="mt-2 text-sm leading-6 text-slate-600">{description}</p>
      <p className="mt-2 text-xs text-slate-500"><strong>Responsables:</strong> {responsible}</p>
    </div>
    <div className="flex items-center gap-2 rounded-full border border-blue-200 bg-blue-50 px-3 py-2 text-xs font-semibold text-blue-700"><CalendarDays size={15}/>{frequency}</div>
  </header>;
}

export function StepList({ steps }) {
  return <ol className="space-y-3">{steps.map((step, index) => <li key={`${index}-${step}`} className="flex items-start gap-3 text-sm leading-6 text-slate-700">
    <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-blue-100 font-bold text-blue-700">{index + 1}</span>
    <span>{step}</span>
  </li>)}</ol>;
}
export function FileTypes({ evidence }) {
  return <div className="grid gap-3 md:grid-cols-2">{evidence.map((type) => <div key={type.key} className="flex gap-3 rounded-xl border border-slate-200 bg-slate-50 p-4">
    <FileText size={20} className="mt-0.5 shrink-0 text-blue-600"/><div><p className="text-sm font-semibold text-slate-800">{type.label}</p><p className="mt-1 text-xs leading-5 text-slate-500">{type.help}</p></div>
  </div>)}</div>;
}
export function RequirementList({ items }) {
  return <div className="space-y-3">{items.map((item, i) => <div key={i} className="flex items-start gap-2 text-sm leading-6 text-slate-700"><ShieldCheck className="mt-0.5 shrink-0 text-blue-600" size={18}/><span>{item}</span></div>)}</div>;
}
