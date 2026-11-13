import { useEffect, useState } from "react";
import { Panel, InfoBanner, FIELD, PRIMARY, SECONDARY } from "../common/ControlUI";
import { readStoredUser } from "../../../services/authSession";
import {
  getControlEvidences, getControlHistory, uploadControlEvidence,
  downloadControlEvidence, verifyControlEvidence,
} from "../../../services/sox/common/controlEvidence";

const TYPES = [
  ["rrhh", "Correo / matriz de RR. HH."],
  ["accesos", "Corte de accesos internos LDAP/SASE"],
  ["conciliacion", "Informe de conciliación"],
  ["baja", "Evidencia de baja aprobada"],
  ["informe", "Informe a Jefatura"],
];

export default function Control6Repository({ historyOnly = false }) {
  const [year, setYear] = useState(String(new Date().getFullYear()));
  const [semester, setSemester] = useState("1");
  const [tipo, setTipo] = useState("rrhh");
  const [reference, setReference] = useState("");
  const [file, setFile] = useState(null);
  const [items, setItems] = useState([]);
  const [history, setHistory] = useState([]);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const isAdmin = readStoredUser()?.rol === "administrador";

  useEffect(() => {
    let live = true;
    setError("");
    Promise.all([
      getControlEvidences(6, year, semester),
      getControlHistory(6, year, semester),
    ]).then(([ev, hist]) => {
      if (live) { setItems(ev.items || []); setHistory(hist.items || []); }
    }).catch((e) => { if (live) setError(e.message); });
    return () => { live = false; };
  }, [year, semester, refresh]);

  async function send() {
    if (!file) return;
    setSaving(true); setError("");
    try {
      await uploadControlEvidence(6, { file, anio: year, semestre: semester, tipo, referencia: reference });
      setFile(null); setReference(""); setRefresh((v) => v + 1);
    } catch (e) { setError(e.message); }
    finally { setSaving(false); }
  }

  async function verify(id) {
    if (!window.confirm("¿Has revisado este documento? La verificación interna no demuestra una baja real en LDAP o SASE.")) return;
    try { await verifyControlEvidence(6, id); setRefresh((v) => v + 1); }
    catch (e) { setError(e.message); }
  }

  const date = (value) => String(value || "—").replace("T", " ").slice(0, 19);
  return <div className="space-y-5">
    <Panel title={historyOnly ? "Historial documental" : "Evidencias del Control 6"}
      description="Los documentos se organizan por año y semestre; no se comparten con el Control 7.">
      <div className="grid gap-4 sm:grid-cols-2">
        <label className="text-xs font-semibold text-slate-600">Año
          <input className={FIELD} type="number" min="2020" max="2100" value={year} onChange={(e) => setYear(e.target.value)}/>
        </label>
        <label className="text-xs font-semibold text-slate-600">Semestre
          <select className={FIELD} value={semester} onChange={(e) => setSemester(e.target.value)}>
            <option value="1">Primer semestre</option><option value="2">Segundo semestre</option>
          </select>
        </label>
      </div>
    </Panel>
    {error && <InfoBanner caution>{error}</InfoBanner>}
    {historyOnly ? <Panel title="Acciones registradas" description="Fechas almacenadas en UTC; registro de cargas, descargas y revisiones.">
      <div className="overflow-x-auto"><table className="w-full min-w-[600px] text-left text-sm"><thead className="bg-slate-100"><tr><th className="p-3">Fecha (UTC)</th><th className="p-3">Acción</th><th className="p-3">Documento</th><th className="p-3">Usuario</th></tr></thead><tbody>
        {history.map((h) => <tr className="border-t" key={h.id}><td className="p-3">{date(h.fecha)}</td><td className="p-3">{h.accion}</td><td className="p-3">{h.archivo}</td><td className="p-3">{h.usuario}</td></tr>)}
        {!history.length && <tr><td colSpan={4} className="p-7 text-center text-slate-500">No hay acciones registradas.</td></tr>}
      </tbody></table></div>
    </Panel> : <>
      <InfoBanner caution>Los documentos pueden contener datos personales de RR. HH. La carga y descarga están limitadas al equipo SOX autorizado. No se realiza ninguna eliminación automática de accesos.</InfoBanner>
      <Panel title="Documentos guardados">
        <div className="overflow-x-auto"><table className="w-full min-w-[680px] text-left text-sm"><thead className="bg-slate-100"><tr><th className="p-3">Fecha (UTC)</th><th className="p-3">Documento</th><th className="p-3">Tipo</th><th className="p-3">Revisión</th><th className="p-3">Acciones</th></tr></thead><tbody>
          {items.map((e) => <tr key={e.id} className="border-t"><td className="p-3">{date(e.creado_en)}</td><td className="p-3"><strong>{e.nombre_archivo}</strong><p className="text-xs text-slate-500">{e.creado_por}</p></td><td className="p-3">{TYPES.find((x) => x[0] === e.tipo)?.[1] || e.tipo}</td><td className="p-3">{e.estado}</td><td className="p-3"><div className="flex gap-2"><button type="button" className={SECONDARY} onClick={() => downloadControlEvidence(6, e.id, e.nombre_archivo).catch((x) => setError(x.message))}>Descargar</button>{isAdmin && e.estado === "CARGADA" && <button type="button" className={PRIMARY} onClick={() => verify(e.id)}>Verificar</button>}</div></td></tr>)}
          {!items.length && <tr><td colSpan={5} className="p-7 text-center text-slate-500">No hay documentos para el período.</td></tr>}
        </tbody></table></div>
      </Panel>
      <Panel title="Agregar evidencia al repositorio">
        <div className="grid gap-3 md:grid-cols-2">
          <label className="text-xs font-semibold text-slate-600">Tipo
            <select className={FIELD} value={tipo} onChange={(e) => setTipo(e.target.value)}>{TYPES.map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select>
          </label>
          <label className="text-xs font-semibold text-slate-600">Referencia
            <input className={FIELD} value={reference} onChange={(e) => setReference(e.target.value)} placeholder="Correo / ticket / corte"/>
          </label>
          <label className="text-xs font-semibold text-slate-600 md:col-span-2">Archivo
            <input className="mt-2 block w-full text-sm" type="file" key={refresh} accept=".pdf,.eml,.msg,.doc,.docx,.png,.jpg,.jpeg,.xlsx" onChange={(e) => setFile(e.target.files?.[0] || null)}/>
          </label>
        </div>
        <div className="mt-4 flex justify-end"><button type="button" disabled={!file || saving} onClick={send} className={PRIMARY}>{saving ? "Guardando..." : "Guardar evidencia"}</button></div>
      </Panel>
    </>}
  </div>;
}
