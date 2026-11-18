import { useCallback, useEffect, useMemo, useState } from "react";
import { RefreshCw, Save, Search } from "lucide-react";
import { readStoredUser } from "../../../services/authSession";
import { FIELD, InfoBanner, Panel, PRIMARY, SECONDARY } from "../../../components/SOX/common/ControlUI";
import {
  confirmAllInternal, errorText, getInternalAdmin, getMyInternalAccounts, loadInternalFromLdap, saveInternalDecision,
} from "../../../services/sox/control_7/internalVpnService";
import { formatDateTime } from "../../../utils/dateTime";

const DECISIONS = ["Mantener", "Eliminar", "No pertenece", "Otro"];
const LABEL = { mantener: "Mantener", eliminar: "Eliminar", "no pertenece": "No pertenece", otro: "Otro" };
const PAGE = 30;

function Pager({ page, pages, onPage }) {
  if (pages <= 1) return null;
  return <div className="mt-4 flex items-center justify-end gap-2 text-sm text-slate-600">
    <button type="button" className={SECONDARY} disabled={page <= 1} onClick={() => onPage(page - 1)}>Anterior</button>
    <span className="px-2 font-semibold">Página {page} de {pages}</span>
    <button type="button" className={SECONDARY} disabled={page >= pages} onClick={() => onPage(page + 1)}>Siguiente</button>
  </div>;
}

const accessBadge = (tipo) => <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${tipo === "RDP" ? "bg-violet-100 text-violet-800" : "bg-sky-100 text-sky-800"}`}>{tipo === "RDP" ? "RDP" : "Aplicaciones"}</span>;

/** Vista del gerente: confirma SOLO las cuentas que tiene a cargo según Active Directory. */
function ManagerView() {
  const [data, setData] = useState(null);
  const [rows, setRows] = useState([]);
  const [page, setPage] = useState(1);
  const [editing, setEditing] = useState(null);
  const [feedback, setFeedback] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    getMyInternalAccounts().then((d) => {
      setData(d);
      setRows((d.items || []).map((x) => ({ ...x, decision: x.confirmacion ? LABEL[x.estado] : "", observation: x.observacion || "" })));
    }).catch((e) => setFeedback({ error: true, text: errorText(e, "No se pudo cargar tus cuentas.") }));
  }, []);
  useEffect(load, [load]);

  const expired = !!data?.campana?.vencida;
  const change = (id, field, value) => setRows((c) => c.map((r) => (r.id === id ? { ...r, [field]: value } : r)));
  const valid = (r) => r.decision && (r.decision !== "Otro" || r.observation.trim());

  async function saveOne(row) {
    if (!valid(row)) { setFeedback({ error: true, text: row.decision === "Otro" ? "La decisión Otro requiere una observación." : "Selecciona una decisión." }); return; }
    setBusy(true); setFeedback(null);
    try { await saveInternalDecision(row.id, row); setEditing(null); load(); setFeedback({ error: false, text: `Cuenta ${row.usuario} (${row.tipo_acceso}) confirmada.` }); }
    catch (e) { setFeedback({ error: true, text: errorText(e, "No se pudo guardar.") }); }
    finally { setBusy(false); }
  }

  async function saveAll() {
    const pending = rows.filter((r) => !r.confirmacion || editing === r.id);
    const chosen = pending.filter((r) => r.decision);
    if (!chosen.length) { setFeedback({ error: true, text: "Selecciona la decisión de al menos una cuenta pendiente." }); return; }
    const invalid = chosen.find((r) => !valid(r));
    if (invalid) { setFeedback({ error: true, text: `La cuenta ${invalid.usuario} tiene "Otro" sin observación.` }); return; }
    if (!window.confirm(`¿Confirmas ${chosen.length} cuenta(s)?`)) return;
    setBusy(true); setFeedback(null);
    try {
      await confirmAllInternal(chosen.map((r) => ({ id: r.id, decision: r.decision, observation: r.observation })));
      setEditing(null); load(); setFeedback({ error: false, text: `${chosen.length} cuenta(s) confirmada(s).` });
    } catch (e) { setFeedback({ error: true, text: errorText(e, "No se pudieron confirmar las cuentas.") }); }
    finally { setBusy(false); }
  }

  const pages = Math.max(1, Math.ceil(rows.length / PAGE));
  const visible = rows.slice((page - 1) * PAGE, page * PAGE);
  const confirmed = rows.filter((r) => r.confirmacion).length;

  return <div className="space-y-5">
    <div><h1 className="text-2xl font-bold">VPN internas · Dashboard gerente</h1>
      <p className="mt-1 text-slate-500">Cuentas con VPN interna (RDP o Aplicaciones) que tienes a cargo según Active Directory.</p></div>
    <div className="rounded-2xl border border-amber-200 bg-amber-50 p-5 text-sm text-amber-800">
      <h3 className="text-base font-bold">Instrucciones para la validación</h3>
      <ul className="mt-3 list-disc space-y-1 pl-5">
        <li>Solo ves las cuentas de las personas que dependen de ti en Active Directory.</li>
        <li>En <b>Decisión</b> elige Mantener, Eliminar, No pertenece u Otro.</li>
        <li>Si eliges <b>Otro</b>, la observación es obligatoria.</li>
      </ul>
    </div>
    {!data ? <p className="text-sm text-slate-500">Cargando...</p> : !data.campana
      ? <InfoBanner caution>No hay una campaña activa.</InfoBanner>
      : <Panel title={`Cuentas con VPN interna · ${data.campana.nombre}`} description={`Fecha límite: ${formatDateTime(data.campana.fecha_limite, { seconds: false })}${expired ? " · vencida" : ""} · ${confirmed} de ${rows.length} confirmada(s)`}>
        <div className="mb-4 flex justify-end">
          <button type="button" disabled={expired || busy || !rows.length} onClick={saveAll} className={PRIMARY}><Save size={16}/>{expired ? "Campaña vencida" : "Guardar todas"}</button>
        </div>
        {feedback && <div className="mb-4"><InfoBanner caution={feedback.error}>{feedback.text}</InfoBanner></div>}
        {rows.length === 0 ? <p className="rounded-xl bg-slate-50 p-8 text-center text-slate-500">No tienes cuentas con VPN interna a cargo en esta campaña.</p>
          : <div className="overflow-x-auto"><table className="w-full min-w-[900px] text-left text-sm"><thead className="bg-slate-100 text-slate-600"><tr>
              <th className="p-3">Cuenta</th><th className="p-3">Nombre</th><th className="p-3">Acceso</th><th className="p-3">Decisión</th><th className="p-3">Observación</th><th className="p-3">Estado</th><th className="p-3">Acción</th>
            </tr></thead><tbody>{visible.map((r) => {
              const locked = expired || (r.confirmacion && editing !== r.id);
              return <tr key={r.id} className="border-t border-slate-100">
                <td className="p-3 font-semibold">{r.usuario}</td>
                <td className="p-3">{r.nombre || "—"}{r.activo_ad === 0 && <p className="text-xs text-red-600">Deshabilitada en AD</p>}</td>
                <td className="p-3">{accessBadge(r.tipo_acceso)}</td>
                <td className="p-3"><select value={r.decision} disabled={locked} onChange={(e) => change(r.id, "decision", e.target.value)} className="h-10 rounded-lg border border-slate-300 bg-white px-3">
                  <option value="">Seleccionar</option>{DECISIONS.map((d) => <option key={d}>{d}</option>)}</select></td>
                <td className="p-3"><input value={r.observation} disabled={locked || r.decision !== "Otro"} onChange={(e) => change(r.id, "observation", e.target.value)} maxLength={1000}
                  placeholder={r.decision === "Otro" ? "Ingrese observación" : "Bloqueado"} className="h-10 w-56 rounded-lg border border-slate-300 px-3 disabled:bg-slate-100"/></td>
                <td className="p-3">{r.confirmacion ? <span className="font-semibold text-emerald-700">Confirmado</span> : <span className="font-semibold text-amber-700">Pendiente</span>}</td>
                <td className="p-3"><button type="button" disabled={expired || busy} className={r.confirmacion && editing !== r.id ? SECONDARY : PRIMARY}
                  onClick={() => (r.confirmacion && editing !== r.id ? setEditing(r.id) : saveOne(r))}><Save size={15}/>{r.confirmacion && editing !== r.id ? "Modificar" : "Guardar"}</button></td>
              </tr>;
            })}</tbody></table></div>}
        <Pager page={page} pages={pages} onPage={setPage}/>
      </Panel>}
  </div>;
}

/** Vista de administración: avance por gerente, filtros y carga desde LDAP. */
function AdminView() {
  const [filters, setFilters] = useState({ search: "", gerente: "", estado: "", tipo: "" });
  const [page, setPage] = useState(1);
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState(null);
  const limit = 50;

  const load = useCallback(() => {
    getInternalAdmin({ ...filters, offset: (page - 1) * limit, limit })
      .then(setData).catch((e) => setFeedback({ error: true, text: errorText(e, "No se pudo consultar las VPN internas.") }));
  }, [filters, page]);
  useEffect(load, [load]);

  async function loadLdap() {
    if (!window.confirm("¿Volver a leer los grupos LDAP RDP y APLICACIONES para la campaña activa? Las cuentas ya confirmadas conservan su decisión.")) return;
    setBusy(true); setFeedback(null);
    try {
      const r = await loadInternalFromLdap();
      setFeedback({ error: false, text: `LDAP leído: ${r.membresias} acceso(s), ${r.gerentes} gerente(s), ${r.sin_gerente} sin jefe en AD.` });
      load();
    } catch (e) { setFeedback({ error: true, text: errorText(e, "No se pudo leer LDAP.") }); }
    finally { setBusy(false); }
  }

  const setFilter = (key) => (e) => { setFilters((f) => ({ ...f, [key]: e.target.value })); setPage(1); };
  const r = data?.resumen || {};
  const pages = Math.max(1, Math.ceil((data?.total || 0) / limit));
  const percent = (a, b) => (b ? Math.round((a / b) * 100) : 0);
  const managers = useMemo(() => data?.gerentes || [], [data]);

  return <div className="space-y-5">
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div><h1 className="text-2xl font-bold">VPN internas · RDP y Aplicaciones</h1>
        <p className="mt-1 text-slate-500">Confirmación por gerente de las cuentas en los grupos LDAP del Control 6, en la misma campaña que las VPN externas.</p></div>
      <button type="button" onClick={loadLdap} disabled={busy || !data?.campana} className={SECONDARY}><RefreshCw size={16} className={busy ? "animate-spin" : ""}/>{busy ? "Leyendo LDAP..." : "Cargar desde LDAP"}</button>
    </div>
    {feedback && <InfoBanner caution={feedback.error}>{feedback.text}</InfoBanner>}
    {data && !data.campana && <InfoBanner caution>No hay una campaña activa. Las VPN internas se cargan al iniciar la campaña en Campañas.</InfoBanner>}
    {data?.campana && <>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[["Accesos", r.total || 0, "text-slate-900"], ["Confirmados", `${r.confirmadas || 0} (${percent(r.confirmadas, r.total)}%)`, "text-emerald-700"],
          ["Marcados para eliminar", r.eliminar || 0, "text-red-700"], ["Sin jefe en AD", r.sin_gerente || 0, "text-amber-700"]].map(([label, value, tone]) =>
          <div key={label} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"><p className="text-sm text-slate-500">{label}</p><p className={`mt-1 text-2xl font-bold ${tone}`}>{value}</p></div>)}
      </div>
      {r.sin_gerente > 0 && <InfoBanner caution>{r.sin_gerente} acceso(s) no tienen jefe ("manager") en Active Directory: ningún gerente puede confirmarlos. Corrige el jefe en AD y vuelve a "Cargar desde LDAP".</InfoBanner>}
      <Panel title="Avance por gerente" description={`${data.campana.nombre} · fecha límite ${formatDateTime(data.campana.fecha_limite, { seconds: false })}`}>
        {managers.length === 0 ? <p className="text-sm text-slate-500">Sin gerentes cargados.</p>
          : <ul className="grid gap-2 md:grid-cols-2">{managers.map((m) => <li key={m.usuario}>
              <button type="button" onClick={() => { setFilters((f) => ({ ...f, gerente: m.usuario })); setPage(1); }}
                className="w-full rounded-xl border border-slate-200 p-3 text-left hover:bg-slate-50">
                <div className="flex justify-between text-sm"><span className="font-semibold">{m.nombre}</span><span className="text-slate-500">{m.confirmadas}/{m.total}</span></div>
                <div className="mt-2 h-2 rounded-full bg-slate-100"><div className="h-2 rounded-full bg-emerald-500" style={{ width: `${percent(m.confirmadas, m.total)}%` }}/></div>
              </button></li>)}</ul>}
      </Panel>
      <Panel title="Detalle de accesos">
        <div className="grid gap-3 md:grid-cols-4">
          <label className="text-xs font-semibold text-slate-600">Buscar<div className="relative"><Search size={15} className="absolute left-3 top-1/2 mt-1 -translate-y-1/2 text-slate-400"/>
            <input value={filters.search} onChange={setFilter("search")} placeholder="Cuenta, nombre o gerente" className={`${FIELD} pl-9`}/></div></label>
          <label className="text-xs font-semibold text-slate-600">Gerente<select value={filters.gerente} onChange={setFilter("gerente")} className={FIELD}>
            <option value="">Todos</option><option value="__sin__">Sin jefe en AD</option>{managers.map((m) => <option key={m.usuario} value={m.usuario}>{m.nombre}</option>)}</select></label>
          <label className="text-xs font-semibold text-slate-600">Estado<select value={filters.estado} onChange={setFilter("estado")} className={FIELD}>
            <option value="">Todos</option><option value="pendiente">Pendiente</option><option value="confirmado">Confirmado</option>
            <option value="mantener">Mantener</option><option value="eliminar">Eliminar</option><option value="no pertenece">No pertenece</option><option value="otro">Otro</option></select></label>
          <label className="text-xs font-semibold text-slate-600">Acceso<select value={filters.tipo} onChange={setFilter("tipo")} className={FIELD}>
            <option value="">Todos</option><option value="RDP">RDP</option><option value="APLICACIONES">Aplicaciones</option></select></label>
        </div>
        <div className="mt-4 overflow-x-auto"><table className="w-full min-w-[900px] text-left text-sm"><thead className="bg-slate-100 text-slate-600"><tr>
          <th className="p-3">Cuenta</th><th className="p-3">Nombre</th><th className="p-3">Acceso</th><th className="p-3">Gerente (AD)</th><th className="p-3">Decisión</th><th className="p-3">Confirmó</th>
        </tr></thead><tbody>{(data.items || []).map((x) => <tr key={x.id} className="border-t border-slate-100 align-top">
          <td className="p-3 font-semibold">{x.usuario}</td>
          <td className="p-3">{x.nombre || "—"}{x.activo_ad === 0 && <p className="text-xs text-red-600">Deshabilitada en AD</p>}</td>
          <td className="p-3">{accessBadge(x.tipo_acceso)}</td>
          <td className="p-3">{x.gerente || <span className="font-semibold text-amber-700">Sin jefe en AD</span>}</td>
          <td className="p-3">{x.confirmacion ? <span className={`font-semibold ${x.estado === "eliminar" ? "text-red-700" : "text-emerald-700"}`}>{LABEL[x.estado]}</span> : <span className="font-semibold text-amber-700">Pendiente</span>}
            {x.observacion && <p className="text-xs text-slate-500">{x.observacion}</p>}</td>
          <td className="p-3 text-xs text-slate-500">{x.confirmado_por ? `${x.confirmado_por} · ${formatDateTime(x.fecha_modificacion, { seconds: false })}` : "—"}</td>
        </tr>)}</tbody></table></div>
        <p className="mt-3 text-xs text-slate-500">{data.total} acceso(s) con los filtros aplicados.</p>
        <Pager page={page} pages={pages} onPage={setPage}/>
      </Panel>
    </>}
  </div>;
}

export default function InternalVpns() {
  const role = String(readStoredUser()?.rol || "").toLowerCase();
  return ["administrador", "desarrollador"].includes(role) ? <AdminView/> : <ManagerView/>;
}
