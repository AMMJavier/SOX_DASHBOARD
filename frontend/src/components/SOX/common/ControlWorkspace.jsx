import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { readStoredUser } from "../../../services/authSession";
import { downloadControlEvidence, getControlEvidences, getControlHistory, getPlanReference, uploadControlEvidence, verifyControlEvidence } from "../../../services/sox/common/controlEvidence";
import { CalendarDays, CheckCheck, Clock, FolderOpen, History, Mail, Paperclip, RotateCcw, Upload, X } from "lucide-react";
import { ControlHeading, EvidenceKpis, FileTypes, InfoBanner, Panel, RequirementList, StepList, FIELD, PRIMARY, SECONDARY } from "./ControlUI";
import Control5Events from "../control_5/Control5Events";
import ControlReminderPanel from "./ControlReminderPanel";
import ControlMailPanel from "./ControlMailPanel";

// Controles con correo formal + archivado automático.
const MAIL_CONTROLS = [1, 2, 3];
// Controles con botón "Enviar notificación" en la vista Evidencias (correos.json > controles.<n>.notificacion).
const NOTIFY_CONTROLS = [1];
// Tipo de evidencia propuesto para el correo enviado (el usuario puede cambiarlo).
const MAIL_DEFAULT_TYPE = { 1: "solicitud", 2: "revision", 3: "avance" };

const VIEWS = [
  { id: "resumen", label: "Resumen", icon: CheckCheck },
  { id: "campana", label: "Periodo / campaña", icon: CalendarDays },
  { id: "evidencias", label: "Evidencias", icon: FolderOpen },
  { id: "historial", label: "Historial", icon: History },
  { id: "alertas", label: "Recordatorios", icon: Clock },
];

function Empty({ title, description }) {
  return <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 px-5 py-12 text-center">
    <FolderOpen size={34} className="mx-auto text-slate-300"/><h3 className="mt-3 font-semibold text-slate-700">{title}</h3>
    <p className="mx-auto mt-2 max-w-2xl text-sm text-slate-500">{description}</p>
  </div>;
}

/** Control documental real, con navegación de escritorio en el sidebar compartido. */
export default function ControlWorkspace({ config }) {
  const [params, setParams] = useSearchParams();
  const currentView = VIEWS.some((x) => x.id === params.get("vista")) ? params.get("vista") : "resumen";
  const setView = (view) => setParams((previous) => { const next = new URLSearchParams(previous); next.set("vista", view); return next; });
  const [year, setYear] = useState(String(new Date().getFullYear()));
  const [semester, setSemester] = useState("1");
  const [files, setFiles] = useState([]);
  const [evidenceType, setEvidenceType] = useState(config.evidence[0]?.key ?? "");
  const [reference, setReference] = useState("");
  const [notes, setNotes] = useState("");
  const [account, setAccount] = useState("");
  const [eventDate, setEventDate] = useState("");
  const [operation, setOperation] = useState("alta");
  const [confirmedAt, setConfirmedAt] = useState("");
  const [affectedProfile, setAffectedProfile] = useState("");
  const periodLabel = `${year} · ${config.period === "semester" ? `Semestre ${semester}` : config.period === "event" ? "Por evento" : "Anual"}`;
  const selectedEvidence = useMemo(() => config.evidence.find((t) => t.key === evidenceType), [evidenceType, config.evidence]);
  const [evidences, setEvidences] = useState([]);
  const [history, setHistory] = useState([]);
  const [planReference, setPlanReference] = useState(null);
  const [loadingRecords, setLoadingRecords] = useState(false);
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState("");
  const [loadError, setLoadError] = useState("");
  const [refreshRecords, setRefreshRecords] = useState(0);
  const currentRole = readStoredUser()?.rol;
  const canWrite = ["administrador", "desarrollador"].includes(currentRole);
  const canVerify = currentRole === "administrador";
  const periodSemester = config.period === "semester" ? Number(semester) : null;
  const metrics = {
    total: evidences.length,
    confirmed: evidences.filter((x) => x.estado === "VERIFICADA").length,
    pending: evidences.filter((x) => x.estado === "CARGADA").length,
    expired: null, // No hay fecha de vencimiento oficial configurada.
  };

  useEffect(() => {
    let live = true;
    setLoadingRecords(true);
    setLoadError("");
    Promise.all([
      getControlEvidences(config.number, Number(year), periodSemester),
      getControlHistory(config.number, Number(year), periodSemester),
      config.number === 3 ? getPlanReference(Number(year)) : Promise.resolve(null),
    ]).then(([data, historyData, plan]) => {
      if (!live) return;
      setEvidences(data.items || []);
      setHistory(historyData.items || []);
      setPlanReference(plan?.plan || null);
    }).catch((error) => {
      if (live) { setLoadError(error.message || "No se pudo consultar Oracle."); setEvidences([]); setHistory([]); }
    }).finally(() => { if (live) setLoadingRecords(false); });
    return () => { live = false; };
  }, [config.number, year, periodSemester, refreshRecords]);

  async function submitEvidence() {
    if (!files.length) { setFeedback("Selecciona al menos un archivo."); return; }
    if (!canWrite) { setFeedback("No tienes permisos para cargar evidencias."); return; }
    setSaving(true);
    setFeedback("");
    try {
      for (const selected of files) {
        await uploadControlEvidence(config.number, {
          file: selected.file, anio: Number(year), semestre: periodSemester,
          tipo: evidenceType, referencia: reference, observaciones: notes,
        });
      }
      setFeedback(`${files.length} archivo(s) almacenado(s) en el repositorio privado. Pendiente(s) de verificación interna.`);
      clearDraft();
      setRefreshRecords((n) => n + 1);
    } catch (error) { setFeedback(`Error de carga: ${error.message}. Los archivos aceptados antes del error pueden haberse guardado.`); setRefreshRecords((n) => n + 1); }
    finally { setSaving(false); }
  }

  async function verifyEvidence(id) {
    if (!window.confirm("¿Confirmas que revisaste este documento? Esto NO equivale a la aprobación formal de Gerencia.")) return;
    try { await verifyControlEvidence(config.number, id); setRefreshRecords((n) => n + 1); }
    catch (error) { setFeedback(error.message); }
  }


  const addFiles = (e) => {
    const next = Array.from(e.target.files || []).map((file) => ({
      id: `${Date.now()}-${Math.random()}`, file, type: selectedEvidence?.label || "Evidencia",
    }));
    setFiles((current) => [...current, ...next]);
    e.target.value = "";
  };
  const clearDraft = () => { setFiles([]); setReference(""); setNotes(""); setAccount(""); setEventDate(""); setConfirmedAt(""); setAffectedProfile(""); };

  return <div className="space-y-6 pb-10">
    <ControlHeading {...config}/>
    <EvidenceKpis metrics={loadError ? null : metrics}/>
    {loadError && <InfoBanner caution>No se pudo cargar el expediente: {loadError}. Verifica que se hayan creado las tablas en Oracle.</InfoBanner>}
    <InfoBanner>Las evidencias se guardan en Oracle (metadatos y auditoría) y en un repositorio privado (archivo). <strong>Verificada</strong> significa revisión interna; no sustituye el correo formal de aprobación corporativa. Vencimientos: por definir con el área.</InfoBanner>

    {/* Solo móviles: en escritorio las secciones están en el sidebar SOX. */}
    <nav className="flex flex-wrap gap-2 rounded-2xl border border-slate-200 bg-white p-2 shadow-sm lg:hidden" aria-label={`Secciones del control ${config.number}`}>
      {VIEWS.map(({ id, icon: Icon, label }) => <button key={id} type="button" onClick={() => setView(id)} aria-current={id === currentView ? "page" : undefined}
        className={`flex items-center gap-2 rounded-xl px-3 py-2 text-xs font-semibold transition ${id === currentView ? "bg-blue-600 text-white" : "text-slate-600 hover:bg-slate-100"}`}>
        <Icon size={16}/>{label}</button>)}
    </nav>

    {currentView === "resumen" && <div className="grid gap-5 xl:grid-cols-5">
      <div className="space-y-5 xl:col-span-3">
        <Panel title="Actividad del control" description="Objetivo y procedimiento definido para este control SOX.">
          <p className="mb-5 text-sm leading-7 text-slate-700">{config.activity}</p>
          <StepList steps={config.steps}/>
        </Panel>
        <Panel title="Evidencias que debe conservar" description="Tipos documentales esperados; no significa que estén cargados."><FileTypes evidence={config.evidence}/></Panel>
        {config.linkedControl && <InfoBanner>El control {config.number} depende del <strong>Plan de Seguridad del control {config.linkedControl}</strong>. La referencia a la versión aprobada se resolverá mediante el backend.</InfoBanner>}
      </div>
      <div className="space-y-5 xl:col-span-2">
        <Panel title="Ficha de control">
          <dl className="space-y-4 text-sm">
            <div><dt className="text-slate-500">Control</dt><dd className="font-semibold">{config.number}</dd></div>
            <div><dt className="text-slate-500">Periodicidad</dt><dd className="font-semibold">{config.frequency}</dd></div>
            <div><dt className="text-slate-500">Responsables</dt><dd className="font-semibold">{config.responsible}</dd></div>
            <div><dt className="text-slate-500">Fecha límite</dt><dd className="font-semibold text-amber-700">Por definir con el área</dd></div>
            <div><dt className="text-slate-500">Estado de evidencia</dt><dd className="font-semibold text-slate-600">{metrics.total} cargada(s), {metrics.confirmed} verificada(s)</dd></div>
          </dl>
        </Panel>
        <Panel title="Reglas principales"><RequirementList items={config.rules}/></Panel>
      </div>
    </div>}

    {currentView === "campana" && <div className="space-y-5">
      <Panel title={config.period === "event" ? "Seguimiento por evento" : "Periodo de control"} description="El periodo permite preparar la evidencia sin mezclar campañas de años distintos.">
        <div className="grid gap-4 sm:grid-cols-3">
          <label className="text-xs font-semibold text-slate-600">Año
            <input type="number" min="2020" max="2100" value={year} onChange={(e) => setYear(e.target.value)} className={FIELD}/>
          </label>
          {config.period === "semester" && <label className="text-xs font-semibold text-slate-600">Semestre
            <select value={semester} onChange={(e) => setSemester(e.target.value)} className={FIELD}><option value="1">Primer semestre</option><option value="2">Segundo semestre</option></select>
          </label>}
          <div className="self-end rounded-xl bg-blue-50 px-4 py-3 text-sm font-semibold text-blue-800">Periodo: {periodLabel}</div>
        </div>
        <p className="mt-4 text-xs text-slate-500">El expediente se consulta en Oracle por año y, para Control 3, por semestre. Las fechas de corte y recordatorios aún requieren aprobación del área.</p>
      </Panel>
      <Panel title="Actividades programadas"><StepList steps={config.steps}/></Panel>
      {config.period === "year" && <InfoBanner>Este control tiene <strong>una sola obligación anual</strong>. Puede tener varias versiones o evidencias en el mismo año, pero no se duplicará como segunda campaña semestral.</InfoBanner>}
      {config.period === "semester" && <InfoBanner>El control debe contar con una revisión por semestre. Las fechas exactas de cada corte deben aprobarse antes de programar recordatorios.</InfoBanner>}
      {config.period === "event" && <InfoBanner caution>Se debe registrar un expediente por cada alta, modificación o baja de administrador. El consolidado semestral es complementario, no reemplaza la evidencia individual.</InfoBanner>}
    </div>}

    {currentView === "evidencias" && (config.number === 5
      ? <Control5Events year={Number(year)} evidences={evidences} canWrite={canWrite} canVerify={canVerify} onChanged={() => setRefreshRecords((n) => n + 1)}/>
      : <div className="space-y-5">
      {config.number === 3 && <InfoBanner>{planReference
        ? <>Plan anual verificado del Control 2: <strong>{planReference.nombre_archivo}</strong> (ID {planReference.id}). Úsalo como referencia para los avances del semestre.
            <button type="button" className={`${SECONDARY} ml-3 mt-2`} onClick={() => downloadControlEvidence(2, planReference.id, planReference.nombre_archivo).catch((e) => setFeedback(e.message))}>Descargar plan</button></>
        : <>Todavía no se encuentra un Plan de Seguridad verificado del Control 2 para {year}. Revísalo antes de cerrar la evidencia del semestre.</>}
      </InfoBanner>}
      <Panel title="Repositorio de evidencias" description="Documentación almacenada en el servidor, con su versión, autor y estado de revisión.">
        {loadingRecords ? <p className="text-sm text-slate-500">Consultando evidencias...</p> : evidences.length === 0
          ? <Empty title="Sin evidencias registradas" description="No existen documentos cargados en el período seleccionado."/>
          : <div className="overflow-x-auto"><table className="w-full min-w-[700px] text-left text-sm"><thead className="bg-slate-100 text-slate-600"><tr>
              <th className="px-3 py-3">Fecha de carga (UTC)</th><th className="px-3 py-3">Documento</th><th className="px-3 py-3">Tipo / referencia</th><th className="px-3 py-3">Revisión</th><th className="px-3 py-3">Acciones</th>
            </tr></thead><tbody>{evidences.map((item) => <tr key={item.id} className="border-t border-slate-100">
              <td className="whitespace-nowrap px-3 py-3 text-slate-600">{item.creado_en?.replace("T", " ").slice(0, 19)}</td>
              <td className="px-3 py-3"><p className="font-semibold text-slate-800">{item.nombre_archivo}</p><p className="text-xs text-slate-500">Subió: {item.creado_por}</p></td>
              <td className="px-3 py-3"><p>{config.evidence.find((x) => x.key === item.tipo)?.label || item.tipo}</p><p className="text-xs text-slate-500">{item.referencia || "Sin referencia"}</p></td>
              <td className="px-3 py-3"><span className={item.estado === "VERIFICADA" ? "font-semibold text-emerald-700" : "font-semibold text-amber-700"}>{item.estado}</span></td>
              <td className="px-3 py-3"><div className="flex flex-wrap gap-2"><button className={SECONDARY} type="button" onClick={() => downloadControlEvidence(config.number, item.id, item.nombre_archivo).catch((e) => setFeedback(e.message))}>Descargar</button>
              {canVerify && item.estado === "CARGADA" && <button type="button" className={PRIMARY} onClick={() => verifyEvidence(item.id)}>Verificar</button>}</div></td>
            </tr>)}</tbody></table></div>}
      </Panel>
      {canWrite && <Panel title="Cargar evidencia" description="Archivos PDF, EML, MSG, Word, Excel o imágenes; máximo 15 MB por archivo.">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <label className="text-xs font-semibold text-slate-600">Tipo de evidencia
            <select value={evidenceType} onChange={(e) => setEvidenceType(e.target.value)} className={FIELD}>
              {config.evidence.map((type) => <option value={type.key} key={type.key}>{type.label}</option>)}
            </select>
          </label>
          <label className="text-xs font-semibold text-slate-600">Referencia de correo / solicitud
            <input value={reference} onChange={(e) => setReference(e.target.value)} placeholder="Correo, REQ, versión..." className={FIELD}/>
          </label>
          <div className="self-end rounded-xl bg-blue-50 px-4 py-3 text-sm font-semibold text-blue-800">Periodo: {periodLabel}</div>
        </div>
        <div className="mt-4 grid gap-4 lg:grid-cols-2">
          <label className="text-xs font-semibold text-slate-600">Documentos
            <input type="file" multiple accept=".pdf,.eml,.msg,.doc,.docx,.png,.jpg,.jpeg,.xlsx" onChange={addFiles}
              className="mt-2 block w-full text-sm text-slate-600 file:mr-3 file:rounded-xl file:border-0 file:bg-blue-100 file:px-4 file:py-2.5 file:font-semibold file:text-blue-800" />
          </label>
          <label className="text-xs font-semibold text-slate-600">Observaciones internas
            <textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={2} className={FIELD}/>
          </label>
        </div>
        {files.length > 0 && <ul className="mt-4 space-y-2">{files.map(({ id, file, type }) => <li className="flex items-center gap-3 rounded-xl border border-slate-200 bg-slate-50 p-3" key={id}>
          <Paperclip size={18} className="text-blue-600"/><div className="min-w-0 flex-1"><p className="truncate text-sm font-semibold text-slate-700">{file.name}</p><p className="text-xs text-slate-500">{type} · {(file.size / 1024).toFixed(1)} KB · Pendiente de guardar</p></div>
          <button type="button" title="Quitar archivo" className="rounded-lg p-2 hover:bg-slate-200" onClick={() => setFiles((current) => current.filter((x) => x.id !== id))}><X size={17}/></button>
        </li>)}</ul>}
        <div className="mt-4 flex flex-wrap justify-end gap-3">
          <button type="button" onClick={clearDraft} disabled={saving} className={SECONDARY}><RotateCcw size={16}/>Limpiar</button>
          <button type="button" onClick={submitEvidence} disabled={saving || !files.length} className={PRIMARY}><Upload size={16}/>{saving ? "Guardando..." : "Guardar evidencias"}</button>
        </div>
      </Panel>}
      {feedback && <InfoBanner caution>{feedback}</InfoBanner>}
      {NOTIFY_CONTROLS.includes(config.number) && <ControlReminderPanel control={config.number} anio={year} semestre={periodSemester}
        title={`Enviar notificación del Control ${config.number}`}
        description="Notificación a los responsables del control. Destinatarios, copias y texto se configuran en backend/config/correos.json; revisa la vista previa antes de enviar."
        sendLabel="Enviar notificación" hideIfNotAdmin />}
      {MAIL_CONTROLS.includes(config.number) && <ControlMailPanel control={config.number} year={year} semester={periodSemester}
        evidenceTypes={config.evidence} defaultType={MAIL_DEFAULT_TYPE[config.number]} canWrite={canWrite} onArchived={() => setRefreshRecords((n) => n + 1)}
        repositoryFiles={[
          ...(config.number === 3 && planReference ? [{ id: planReference.id, nombre: planReference.nombre_archivo, origen: "Plan de Seguridad verificado · Control 2" }] : []),
          ...evidences.map((e) => ({ id: e.id, nombre: e.nombre_archivo, bytes: e.bytes,
            origen: `${config.evidence.find((t) => t.key === e.tipo)?.label || e.tipo} · ${e.estado}` })),
        ]}/>}
    </div>)}

    {currentView === "historial" && <Panel title="Historial de actividad" description="Registro auditado de cargas, consultas y revisiones; fecha y hora en UTC.">
      {history.length === 0 ? <Empty title="Sin eventos de auditoría" description="No hay cambios registrados para el período seleccionado."/>
        : <div className="overflow-x-auto"><table className="w-full min-w-[650px] text-left text-sm"><thead className="bg-slate-100"><tr><th className="px-3 py-3">Fecha (UTC)</th><th className="px-3 py-3">Acción</th><th className="px-3 py-3">Documento / cuenta</th><th className="px-3 py-3">Usuario</th></tr></thead>
            <tbody>{history.map((item) => <tr key={item.id} className="border-t"><td className="px-3 py-3">{item.fecha?.replace("T", " ").slice(0, 19)}</td><td className="px-3 py-3">{item.accion}</td><td className="px-3 py-3">{item.archivo}{item.cuenta_evento ? <p className="text-xs text-slate-500">Cuenta: {item.cuenta_evento} · Evento #{item.evento_id}</p> : null}</td><td className="px-3 py-3">{item.usuario}</td></tr>)}</tbody></table></div>}
    </Panel>}

    {currentView === "alertas" && <div className="space-y-5">
      <Panel title="Reglas de recordatorio" description="Configuración funcional prevista, pendiente de calendario oficial.">
        <RequirementList items={config.reminders}/>
        <div className="mt-5"><InfoBanner caution>Los correos todavía no están automatizados. La fecha límite, los destinatarios, la plantilla y el número de días de antelación deben confirmarse antes de activar los envíos.</InfoBanner></div>
      </Panel>
      <ControlReminderPanel control={config.number} anio={year} semestre={periodSemester} />
      <Panel title="Pendientes por definir con el responsable">
        <ul className="space-y-3">{config.openItems.map((item, index) => <li className="flex items-start gap-2 text-sm text-slate-700" key={index}><Mail size={17} className="mt-0.5 shrink-0 text-blue-600"/>{item}</li>)}</ul>
      </Panel>
    </div>}
  </div>;
}
