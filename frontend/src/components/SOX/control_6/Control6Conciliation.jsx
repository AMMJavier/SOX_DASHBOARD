import { useEffect, useState } from "react";
import { FileCheck2, FileSpreadsheet, RefreshCcw, GitCompareArrows, Download } from "lucide-react";
import { Panel, FIELD, PRIMARY, SECONDARY, InfoBanner } from "../common/ControlUI";
import { getLatestC6Cut } from "../../../services/sox/control_6/cortes";
import { previewC6Conciliation, saveC6Conciliation, listC6Conciliations } from "../../../services/sox/control_6/conciliations";
import { downloadControlEvidence } from "../../../services/sox/common/controlEvidence";

const currentYear = new Date().getFullYear();
const currentSemester = new Date().getMonth() < 6 ? "1" : "2";
const STATUS = { coincide: "Acceso encontrado — revisar", no_coincide: "No encontrado en grupos consultados", ambiguo: "Identificador para revisión" };

export default function Control6Conciliation({ onViewEvidences }) {
  const [cut, setCut] = useState(null);
  const [hrFile, setHrFile] = useState(null);
  const [reference, setReference] = useState("");
  const [year, setYear] = useState(String(currentYear));
  const [semester, setSemester] = useState(currentSemester);
  const [preview, setPreview] = useState(null);
  const [saved, setSaved] = useState(null);
  const [history, setHistory] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState("todos");
  const [rowPage, setRowPage] = useState(0);

  async function refreshCut() {
    try {
      const data = await getLatestC6Cut();
      setCut(data.corte || null);
      setPreview(null); setSaved(null); setError("");
    } catch (e) { setError(e.message); }
  }
  async function refreshHistory() {
    try { const data = await listC6Conciliations(); setHistory(data.items || []); }
    catch (e) { setError(e.message); }
  }
  useEffect(() => {
    let live = true;
    Promise.all([getLatestC6Cut(), listC6Conciliations()]).then(([c, h]) => {
      if (live) { setCut(c.corte || null); setHistory(h.items || []); }
    }).catch((e) => { if (live) setError(e.message); });
    return () => { live = false; };
  }, []);

  const input = { corteId: cut?.id, archivo: hrFile, anio: year, semestre: semester, referencia: reference.trim() };
  async function runPreview() {
    if (!cut || !hrFile) return;
    setBusy(true); setError(""); setSaved(null); setPreview(null);
    try { const result = await previewC6Conciliation(input); setPreview(result); setRowPage(0); setFilter("todos"); }
    catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }
  async function save() {
    if (!preview || !input.referencia || !cut || !hrFile) return;
    if (!window.confirm("¿Guardar este resultado como evidencia del Control 6? Se creará un informe PDF privado, vinculado al corte LDAP y al período seleccionado. No se darán de baja cuentas.")) return;
    setBusy(true); setError("");
    try {
      const result = await saveC6Conciliation(input);
      setSaved(result);
      await refreshHistory();
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }

  const filtered = (preview?.items || []).filter((row) => filter === "todos" || row.estado === filter);
  const rows = filtered.slice(rowPage * 25, (rowPage + 1) * 25);
  return <div className="space-y-5">
    <Panel title="Conciliar cesantes de RR. HH. contra LDAP" description="El corte LDAP ya está guardado en Oracle. Solo carga la lista oficial de cesantes de RR. HH.; no copies nuevamente usuarios LDAP.">
      {error && <div className="mb-4"><InfoBanner caution>{error}</InfoBanner></div>}
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-xl bg-blue-50 p-4 text-sm text-blue-900">
        <span><strong>Corte LDAP de referencia:</strong> {cut ? `#${cut.id} · ${cut.cuentas_unicas} cuentas únicas · RDP ${cut.rdp} / Aplicaciones ${cut.aplicaciones}` : "No existe corte sincronizado"}</span>
        <button type="button" className={SECONDARY} onClick={refreshCut}><RefreshCcw size={16}/>Actualizar referencia</button>
      </div>
      <InfoBanner caution>La comparación usa cuentas de dominio (por ejemplo, <strong>sAMAccountName</strong>), no nombres completos. Una coincidencia requiere revisión; nunca elimina usuarios. Los archivos de RR. HH. pueden contener datos personales y deben tratarse como información restringida.</InfoBanner>
      <div className="mt-5 grid gap-4 md:grid-cols-2">
        <label className="block text-sm font-semibold text-slate-700">Archivo oficial de RR. HH. (CSV o Excel .xlsx)
          <input type="file" accept=".csv,.xlsx" className="mt-2 block w-full text-sm" onChange={(e) => { setHrFile(e.target.files?.[0] || null); setPreview(null); setSaved(null); }}/>
          <span className="mt-1 block text-xs font-normal text-slate-500">Máx. 5 MB, 2000 registros. Se requiere una columna: usuario, usuario_ad, cuenta o sAMAccountName.</span>
        </label>
        <label className="text-sm font-semibold text-slate-700">Referencia o fecha del listado de RR. HH.
          <input value={reference} className={FIELD} maxLength={240} placeholder="Ej.: Reporte cesantes RRHH 2026-10-30" onChange={(e) => { setReference(e.target.value); setPreview(null); setSaved(null); }}/>
        </label>
        <label className="text-sm font-semibold text-slate-700">Año
          <input type="number" min="2020" max="2100" value={year} className={FIELD} onChange={(e) => { setYear(e.target.value); setPreview(null); }}/>
        </label>
        <label className="text-sm font-semibold text-slate-700">Semestre
          <select value={semester} className={FIELD} onChange={(e) => { setSemester(e.target.value); setPreview(null); }}>
            <option value="1">Primer semestre</option><option value="2">Segundo semestre</option>
          </select>
        </label>
      </div>
      <div className="mt-5 flex justify-end">
        <button className={PRIMARY} type="button" disabled={busy || !cut || !hrFile || !reference.trim()} onClick={runPreview}>
          <GitCompareArrows size={17}/>{busy ? "Procesando..." : "Previsualizar conciliación"}
        </button>
      </div>
    </Panel>

    {preview && <>
      <Panel title="Resultado de conciliación" description="El resultado todavía no está guardado como evidencia. Revisa los hallazgos antes de confirmar.">
        <div className="mb-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {[["Cuentas de RR. HH.", preview.resumen.rrhh],["Acceso encontrado",preview.resumen.coincidencias],["Sin coincidencia",preview.resumen.sin_coincidencia],["Ambiguos",preview.resumen.ambiguos]].map(([name, value]) =>
            <div key={name} className="rounded-xl bg-slate-50 p-4"><p className="text-xs text-slate-500">{name}</p><p className="text-2xl font-bold">{value}</p></div>)}
        </div>
        <label className="mb-3 block max-w-sm text-xs font-semibold text-slate-700">Filtrar hallazgos
          <select className={FIELD} value={filter} onChange={(e) => { setFilter(e.target.value); setRowPage(0); }}>
            <option value="todos">Todos</option><option value="coincide">Con accesos LDAP</option><option value="no_coincide">Sin coincidencia</option><option value="ambiguo">Ambiguos</option>
          </select>
        </label>
        <div className="overflow-x-auto"><table className="w-full min-w-[700px] text-left text-sm"><thead className="bg-slate-100"><tr>
          <th className="p-3">Cuenta RR. HH.</th><th className="p-3">Grupos LDAP</th><th className="p-3">Resultado</th></tr></thead><tbody>
          {rows.map((row, i) => <tr className="border-b border-slate-100" key={`${row.cuenta_rrhh}-${rowPage}-${i}`}>
            <td className="p-3 font-mono">{row.cuenta_rrhh || "—"}</td>
            <td className="p-3">{row.accesos.map((a) => `${a.grupo}${a.activo === 0 ? " (deshabilitada)" : ""}`).join(", ") || "—"}</td>
            <td className="p-3">{STATUS[row.estado]}{row.motivo ? ` · ${row.motivo}` : ""}</td>
          </tr>)}
          {!rows.length && <tr><td colSpan={3} className="p-5 text-center text-slate-500">No hay resultados para este filtro.</td></tr>}
        </tbody></table></div>
        <div className="mt-3 flex items-center justify-between text-xs text-slate-500">
          <span>{filtered.length} resultados · Página {rowPage + 1} de {Math.max(1, Math.ceil(filtered.length / 25))}</span>
          <div className="flex gap-2"><button type="button" className={SECONDARY} disabled={rowPage === 0} onClick={() => setRowPage((p) => p - 1)}>Anterior</button><button type="button" className={SECONDARY} disabled={(rowPage + 1) * 25 >= filtered.length} onClick={() => setRowPage((p) => p + 1)}>Siguiente</button></div>
        </div>
        {!saved && <div className="mt-5 flex justify-end"><button type="button" className={PRIMARY} disabled={busy} onClick={save}><FileCheck2 size={17}/>Guardar conciliación como evidencia PDF</button></div>}
        {saved && <div className="mt-5 space-y-3 rounded-xl border border-green-200 bg-green-50 p-4 text-sm text-green-900">
          <strong>Informe registrado como evidencia #{saved.evidencia_id} — Estado CARGADA.</strong>
          <p>Conciliación #{saved.conciliacion_id} · Corte LDAP #{saved.corte_id}. La verificación documental interna se realiza posteriormente.</p>
          <div className="flex flex-wrap gap-2">
            <button type="button" className={SECONDARY} onClick={() => downloadControlEvidence(6, saved.evidencia_id, saved.nombre_archivo).catch((e) => setError(e.message))}><Download size={16}/>Descargar informe</button>
            <button type="button" className={SECONDARY} onClick={onViewEvidences}><FileSpreadsheet size={16}/>Ver en Evidencias</button>
          </div>
        </div>}
      </Panel>
    </>}
    <Panel title="Conciliaciones registradas" description="Cada registro conserva el corte LDAP, el período, el responsable y un informe descargable en Evidencias del Control 6.">
      <div className="overflow-x-auto"><table className="w-full min-w-[700px] text-left text-sm"><thead className="bg-slate-100"><tr><th className="p-3">Fecha UTC</th><th className="p-3">Corte</th><th className="p-3">RR. HH.</th><th className="p-3">Hallazgos</th><th className="p-3">Estado</th><th className="p-3">Informe</th></tr></thead>
        <tbody>{history.map((h) => <tr className="border-b border-slate-100" key={h.id}>
          <td className="p-3">{h.creado_en?.replace("T", " ").slice(0, 19)}</td>
          <td className="p-3">#{h.corte_id} · {h.anio}/S{h.semestre}</td>
          <td className="p-3">{h.fuente_rrhh} · {h.total_rrhh} cuentas</td>
          <td className="p-3">{h.coincidencias} coincidencias · {h.ambiguos} ambiguos</td>
          <td className="p-3">{h.estado}</td>
          <td className="p-3"><button type="button" className={SECONDARY} onClick={() => downloadControlEvidence(6, h.evidencia_id, h.archivo).catch((e) => setError(e.message))}><Download size={15}/>PDF</button></td>
        </tr>)}{!history.length && <tr><td colSpan={6} className="p-5 text-center text-slate-500">Aún no hay conciliaciones guardadas.</td></tr>}</tbody>
      </table></div>
      <div className="mt-4 flex justify-end"><button type="button" className={SECONDARY} onClick={refreshHistory}><RefreshCcw size={16}/>Actualizar historial</button></div>
    </Panel>
  </div>;
}
