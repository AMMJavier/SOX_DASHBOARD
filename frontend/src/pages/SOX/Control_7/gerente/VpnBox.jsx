import { useState } from "react";
import { Briefcase, Globe, Lock, Network, Save, Users } from "lucide-react";
import Pagination from "../../../../components/common/Pagination";
import { CONFIRMED, DECISIONS, PENDING, REPORTED, summarize } from "./vpnRows";

const ROWS_PER_PAGE = 30;
const TH = "border-b p-4";
// Color de cada cuadro para distinguir externas (azul) de internas (violeta).
const TONES = {
  externas: {
    Icon: Globe, label: "Externa", section: "border-sky-200 border-l-sky-500", badge: "bg-sky-100 text-sky-700",
    title: "text-sky-900", head: "bg-sky-50 text-sky-900 [&_th]:border-sky-200", hover: "hover:bg-sky-50/60",
  },
  internas: {
    Icon: Network, label: "Interna", section: "border-violet-200 border-l-violet-500", badge: "bg-violet-100 text-violet-700",
    title: "text-violet-900", head: "bg-violet-50 text-violet-900 [&_th]:border-violet-200", hover: "hover:bg-violet-50/60",
  },
  // Vista del aprobador de directores (David Álava): un solo cuadro "VPN de directores".
  directores: {
    Icon: Briefcase, label: null, section: "border-red-200 border-l-red-600", badge: "bg-red-100 text-red-800",
    title: "text-red-900", head: "bg-red-50 text-red-900 [&_th]:border-red-200", hover: "hover:bg-red-50/60",
  },
  // Mismo aprobador: VPN de colaboradores (no directores) que se le asignaron a mano.
  colaboradores: {
    Icon: Users, label: null, section: "border-rose-200 border-l-rose-400", badge: "bg-rose-100 text-rose-800",
    title: "text-rose-900", head: "bg-rose-50 text-rose-900 [&_th]:border-rose-200", hover: "hover:bg-rose-50/60",
  },
};
const TD = "border-b border-slate-100 p-4";

function Status({ status }) {
  if (status === CONFIRMED) return <span className="font-semibold text-emerald-700">Confirmado</span>;
  return <span className="font-semibold text-amber-700">Pendiente
    {status === REPORTED && <span className="block text-xs font-normal text-slate-500">En revisión del administrador</span>}</span>;
}

/** Cuadro de VPN del gerente (externas o internas). Lo guardado queda bloqueado. */
export default function VpnBox({ tone, title, headers, rows, loading, error, expired, busy, emptyText, deadline, onChange, onSave, onTouch }) {
  const [page, setPage] = useState(1);
  const pages = Math.ceil(rows.length / ROWS_PER_PAGE);
  const current = Math.min(page, Math.max(pages, 1));
  const visible = rows.slice((current - 1) * ROWS_PER_PAGE, current * ROWS_PER_PAGE);
  const { pending } = summarize(rows);
  const confirmed = rows.filter((r) => r.status === CONFIRMED).length;
  const reported = rows.filter((r) => r.status === REPORTED).length;

  // Cualquier clic o cambio dentro del cuadro cuenta como interacción, salvo el botón individual.
  const touch = (e) => { if (!e.target.closest("[data-individual]")) onTouch(); };
  const t = TONES[tone];
  const Icon = t.Icon;

  return (
    <section className={`mt-6 rounded-2xl border border-l-[6px] bg-white p-6 shadow-sm ${t.section}`} onClickCapture={touch} onChangeCapture={touch}>
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <h3 className={`flex items-center gap-3 text-lg font-bold ${t.title}`}>
          <span className={`flex h-9 w-9 items-center justify-center rounded-xl ${t.badge}`}><Icon size={18}/></span>
          {title}
          {t.label && <span className={`rounded-full px-2.5 py-0.5 text-xs font-bold uppercase tracking-wide ${t.badge}`}>{t.label}</span>}
        </h3>
        {rows.length > 0 && <p className="text-sm text-slate-500">
          <b className="text-slate-800">{rows.length}</b> en total · <b className="text-emerald-700">{confirmed}</b> confirmadas ·{" "}
          <b className="text-amber-700">{pending}</b> por validar{reported > 0 && <> · <b className="text-slate-700">{reported}</b> en revisión</>}
        </p>}
      </div>

      {error ? <p className="rounded-xl bg-red-50 p-4 text-sm text-red-700">{error}</p>
        : loading ? <p className="rounded-xl bg-slate-50 p-8 text-center text-slate-500">Cargando...</p>
        : rows.length === 0 ? <p className="rounded-xl bg-slate-50 p-8 text-center text-slate-500">{emptyText}</p>
        : <div className="overflow-x-auto">
          <table className="w-full min-w-[1000px] border-collapse text-sm">
            <thead><tr className={`text-left ${t.head}`}>
              {[...headers, "Decisión", "Observación", "Confirmación", "Fecha Límite", "Guardar"].map((h) => <th key={h} className={TH}>{h}</th>)}
            </tr></thead>
            <tbody>{visible.map((r) => {
              const locked = expired || busy || r.status !== PENDING;
              const other = r.decision === "Otro";
              const writing = other && !locked; // "Otro" sin guardar: el cuadro se pone blanco para escribir
              return (
                <tr key={r.id} className={t.hover}>
                  {r.cells.map((value, i) => <td key={headers[i]} className={`${TD} ${i === 0 ? "font-semibold" : ""}`}>{value}
                    {i === 1 && r.note && <p className="text-xs text-red-600">{r.note}</p>}</td>)}
                  <td className={TD}>
                    <select value={r.decision} disabled={locked} onChange={(e) => onChange(r.id, "decision", e.target.value)}
                      className="h-10 rounded-lg border border-slate-300 bg-white px-3 outline-none disabled:bg-slate-100 disabled:text-slate-500">
                      <option value="">Seleccionar</option>
                      {(DECISIONS.includes(r.decision) || !r.decision ? DECISIONS : [...DECISIONS, r.decision]).map((d) => <option key={d}>{d}</option>)}
                    </select>
                  </td>
                  <td className={TD}>
                    <input value={r.observation} disabled={locked || !other} maxLength={1000}
                      onChange={(e) => onChange(r.id, "observation", e.target.value)}
                      placeholder={writing ? "Escriba aquí su comentario (obligatorio)" : other ? "" : "Bloqueado"}
                      className={`h-10 w-56 rounded-lg border px-3 outline-none ${writing
                        ? `bg-white text-slate-900 focus:ring-2 focus:ring-amber-200 ${r.observation.trim() ? "border-slate-400" : "border-amber-500"}`
                        : "cursor-not-allowed border-slate-300 bg-slate-100 text-slate-500"}`}/>
                  </td>
                  <td className={TD}><Status status={r.status}/></td>
                  <td className={TD}>{deadline || "-"}</td>
                  <td className={TD}>
                    {r.status === PENDING
                      ? <button type="button" data-individual disabled={locked} onClick={() => onSave(r)}
                          className="flex items-center gap-2 rounded-lg bg-amber-500 px-4 py-2 font-bold text-white hover:bg-amber-600 disabled:cursor-not-allowed disabled:bg-slate-400">
                          <Save size={16}/>{expired ? "Bloqueado" : "Guardar"}</button>
                      : <span className="flex items-center gap-2 text-sm font-semibold text-slate-500"><Lock size={15}/>Guardada</span>}
                  </td>
                </tr>
              );
            })}</tbody>
          </table>
        </div>}
      <Pagination currentPage={current} totalPages={pages} onPageChange={setPage}/>
    </section>
  );
}
