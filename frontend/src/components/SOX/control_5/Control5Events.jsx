import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, CheckCircle2, ChevronDown, ChevronUp, FileText, Plus, RefreshCw, Upload } from "lucide-react";
import {
  createControl5Event, getControl5Events, uploadControlEvidence,
  downloadControlEvidence, verifyControlEvidence,
} from "../../../services/sox/common/controlEvidence";
import { FIELD, PRIMARY, SECONDARY, Panel } from "../common/ControlUI";
import ControlMailPanel from "../common/ControlMailPanel";

// Un correo SALIENTE no es la aprobación (la emite Jefatura); por eso no se ofrece ese tipo.
const MAIL_TYPES = [
  { key: "solicitud", label: "Solicitud de autorización del cambio" },
  { key: "ejecucion", label: "Aviso de modificación ejecutada" },
];
const OPERATION_LABEL = { ALTA: "Alta", MODIFICACION: "Modificación", BAJA: "Baja" };

function eventMailDraft(event) {
  const operation = OPERATION_LABEL[event.operacion] || event.operacion;
  const subject = `SOX Control 5 · ${operation} de administrador firewall: ${event.cuenta}${event.ticket ? ` · ${event.ticket}` : ""}`;
  const body = [
    "Estimado(a):",
    "",
    `Se solicita su autorización para el siguiente cambio en cuentas administradoras de firewall:`,
    "",
    `- Operación: ${operation}`,
    `- Cuenta: ${event.cuenta}`,
    `- Grupo / perfil: ${event.perfil || "No especificado"}`,
    `- Fecha del evento: ${String(event.fecha_evento).slice(0, 10)}`,
    `- Ticket / referencia: ${event.ticket || "No especificado"}`,
    ...(event.descripcion ? [`- Observaciones: ${event.descripcion}`] : []),
    "",
    "Quedo atento a su aprobación.",
    "",
    "Saludos.",
  ].join("\n");
  return { subject: subject.slice(0, 200), body };
}

const TYPES = [
  ["aprobacion", "Correo de aprobación de Jefatura"],
  ["ejecucion", "Evidencia de cambio ejecutado"],
  ["solicitud", "Correo o requerimiento de cambio"],
];
const fmt = (v) => v ? String(v).replace("T", " ").slice(0, 19) : "—";
const today = () => new Date().toLocaleDateString("en-CA");

function Notice({ children, error = false }) {
  return <div className={`rounded-xl border p-3 text-sm ${error ? "border-red-200 bg-red-50 text-red-700" : "border-blue-200 bg-blue-50 text-blue-800"}`}>{children}</div>;
}

export default function Control5Events({ year, evidences = [], canWrite, canVerify, onChanged }) {
  const [events, setEvents] = useState([]);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [selection, setSelection] = useState(null);
  const [form, setForm] = useState({ cuenta: "", operacion: "ALTA", fecha_evento: today(), perfil: "", ticket: "", descripcion: "" });
  const [file, setFile] = useState(null);
  const [type, setType] = useState("aprobacion");
  const [notes, setNotes] = useState("");
  const [consolidatedFile, setConsolidatedFile] = useState(null);
  const [reference, setReference] = useState("");
  const [consolidatedSemester, setConsolidatedSemester] = useState("1");
  const [refresh, setRefresh] = useState(0);

  useEffect(() => { setSelection(null); }, [year]);
  useEffect(() => {
    let live = true;
    setLoading(true);
    getControl5Events(year).then((data) => {
      if (live) setEvents(data.items || []);
    }).catch((err) => {
      if (live) setError(err.message || "No fue posible consultar los eventos de firewall.");
    }).finally(() => { if (live) setLoading(false); });
    return () => { live = false; };
  }, [year, refresh]);

  const selected = events.find((event) => event.id === selection) || null;
  const eventFiles = useMemo(() => evidences.filter((item) => item.evento_id === selection && selection != null), [evidences, selection]);
  const annualFiles = evidences.filter((item) => item.tipo === "consolidado" && item.evento_id == null);
  const change = (key, value) => setForm((old) => ({ ...old, [key]: value }));
  const notifyChanges = () => { setRefresh((n) => n + 1); onChanged?.(); };

  async function createEvent(event) {
    event.preventDefault();
    if (!canWrite || busy) return;
    if (String(form.fecha_evento).slice(0, 4) !== String(year)) {
      setError(`La fecha del evento debe corresponder al año seleccionado (${year}).`);
      return;
    }
    setBusy(true); setError(""); setMessage("");
    try {
      const result = await createControl5Event(form);
      setMessage(`Evento #${result.id} registrado. Adjunta ahora su aprobación y soporte de ejecución.`);
      setSelection(result.id);
      setForm({ cuenta: "", operacion: "ALTA", fecha_evento: "", perfil: "", ticket: "", descripcion: "" });
      notifyChanges();
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  async function attach(event, annual = false) {
    event.preventDefault();
    const uploadFile = annual ? consolidatedFile : file;
    if (!canWrite || !uploadFile || busy || (!annual && !selected)) return;
    setBusy(true); setError(""); setMessage("");
    try {
      await uploadControlEvidence(5, {
        file: uploadFile, anio: year, semestre: annual ? Number(consolidatedSemester) : null,
        tipo: annual ? "consolidado" : type,
        eventoId: annual ? null : selected.id,
        referencia: annual ? reference : (selected.ticket || ""),
        observaciones: notes,
      });
      setMessage(annual ? "Consolidado semestral guardado; no sustituye las evidencias individuales." : "Evidencia asociada al evento y guardada en el repositorio privado.");
      if (annual) setConsolidatedFile(null);
      else setFile(null);
      setNotes("");
      notifyChanges();
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  async function verify(doc) {
    if (!canVerify || !window.confirm("¿Verificaste este documento? No reemplaza la aprobación formal de Jefatura.")) return;
    setBusy(true); setError("");
    try { await verifyControlEvidence(5, doc.id); notifyChanges(); setMessage("Documento marcado como verificado internamente."); }
    catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  function EvidenceList({ items }) {
    return items.length ? <div className="overflow-x-auto"><table className="w-full min-w-[640px] text-left text-sm">
      <thead className="bg-slate-100 text-slate-600"><tr><th className="p-3">Documento</th><th className="p-3">Tipo</th><th className="p-3">Fecha carga (UTC)</th><th className="p-3">Estado</th><th className="p-3">Acciones</th></tr></thead>
      <tbody>{items.map((doc) => <tr key={doc.id} className="border-t border-slate-100"><td className="p-3"><span className="font-medium">{doc.nombre_archivo}</span><p className="text-xs text-slate-500">Cargado por {doc.creado_por}</p></td><td className="p-3">{doc.tipo}{doc.tipo === "consolidado" && <p className="text-xs text-slate-500">Semestre {doc.semestre}</p>}</td><td className="whitespace-nowrap p-3">{fmt(doc.creado_en)}</td><td className="p-3">{doc.estado}</td><td className="p-3"><div className="flex flex-wrap gap-2">
        <button type="button" className={SECONDARY} onClick={() => downloadControlEvidence(5, doc.id, doc.nombre_archivo).catch((err) => setError(err.message))}>Descargar</button>
        {canVerify && doc.estado === "CARGADA" && <button type="button" disabled={busy} className={SECONDARY} onClick={() => verify(doc)}>Verificar</button>}
      </div></td></tr>)}</tbody></table></div>
      : <p className="p-4 text-sm text-amber-700">Sin archivos registrados en este expediente.</p>;
  }

  return <div className="space-y-5">
    <Notice>Cada alta, modificación o baja de administradores debe registrarse como un evento distinto con su correo de aprobación. Un consolidado anual es solo complementario. La plataforma no modifica cuentas de firewall.</Notice>
    {error && <Notice error><AlertTriangle className="mr-1 inline" size={16}/>{error}</Notice>}
    {message && <Notice><CheckCircle2 className="mr-1 inline" size={16}/>{message}</Notice>}
    {canWrite && <Panel title="1. Registrar evento de administrador" description="La fecha corresponde a la ejecución del cambio; no a la carga de la evidencia.">
      <form onSubmit={createEvent} className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <label className="text-xs font-semibold text-slate-600">Cuenta administradora *
          <input className={FIELD} required minLength={2} maxLength={100} value={form.cuenta} onChange={(e) => change("cuenta", e.target.value)} placeholder="Usuario administrador"/></label>
        <label className="text-xs font-semibold text-slate-600">Operación *
          <select className={FIELD} value={form.operacion} onChange={(e) => change("operacion", e.target.value)}><option value="ALTA">Alta</option><option value="MODIFICACION">Modificación</option><option value="BAJA">Baja</option></select></label>
        <label className="text-xs font-semibold text-slate-600">Fecha del evento *
          <input className={FIELD} type="date" required value={form.fecha_evento} onChange={(e) => change("fecha_evento", e.target.value)}/></label>
        <label className="text-xs font-semibold text-slate-600">Grupo / perfil afectado
          <input className={FIELD} maxLength={150} value={form.perfil} onChange={(e) => change("perfil", e.target.value)}/></label>
        <label className="text-xs font-semibold text-slate-600">Ticket / referencia de autorización
          <input className={FIELD} maxLength={150} value={form.ticket} onChange={(e) => change("ticket", e.target.value)}/></label>
        <label className="text-xs font-semibold text-slate-600">Observaciones
          <input className={FIELD} maxLength={1000} value={form.descripcion} onChange={(e) => change("descripcion", e.target.value)}/></label>
        <div className="sm:col-span-2 lg:col-span-3 flex justify-end"><button disabled={busy} type="submit" className={PRIMARY}><Plus size={16}/>Registrar evento</button></div>
      </form>
    </Panel>}
    <Panel title="2. Eventos registrados" description={`Expedientes por cuenta en ${year}; no se fusionan eventos por usuario.`}>
      <div className="mb-3 flex justify-end"><button type="button" className={SECONDARY} onClick={() => setRefresh((n) => n + 1)}><RefreshCw size={15}/>Actualizar</button></div>
      {loading ? <p className="p-4 text-sm text-slate-500">Consultando Oracle...</p> : !events.length ? <p className="p-4 text-sm text-slate-500">No hay cambios de administradores registrados en el año.</p>
        : <div className="overflow-x-auto"><table className="w-full min-w-[760px] text-left text-sm"><thead className="bg-slate-100 text-slate-600"><tr><th className="p-3">Fecha evento</th><th className="p-3">Cuenta / perfil</th><th className="p-3">Operación</th><th className="p-3">Ticket</th><th className="p-3">Respaldo</th><th className="p-3">Expediente</th></tr></thead>
          <tbody>{events.map((item) => <tr key={item.id} className="border-t"><td className="whitespace-nowrap p-3">{String(item.fecha_evento).slice(0, 10)}</td><td className="p-3"><p className="font-semibold">{item.cuenta}</p><p className="text-xs text-slate-500">{item.perfil || "Sin perfil especificado"}</p></td><td className="p-3">{item.operacion}</td><td className="p-3">{item.ticket || "—"}</td><td className="p-3"><span className={item.aprobaciones ? "text-emerald-700" : "font-semibold text-amber-700"}>{item.aprobaciones ? "Aprobación adjunta" : "Falta aprobación"}</span><p className="text-xs text-slate-500">{item.total_archivos} documentos</p></td><td className="p-3"><button type="button" className={SECONDARY} onClick={() => setSelection(selection === item.id ? null : item.id)}>{selection === item.id ? <ChevronUp size={15}/> : <ChevronDown size={15}/>} {selection === item.id ? "Cerrar" : "Abrir"}</button></td></tr>)}</tbody></table></div>}
    </Panel>
    {selected && <Panel title={`3. Evidencias del evento #${selected.id} — ${selected.cuenta}`} description="Los soportes se vinculan a este evento, no a otros cambios de la misma cuenta.">
      <EvidenceList items={eventFiles}/>
      {canWrite && <form className="mt-5 space-y-3 rounded-xl border border-slate-200 bg-slate-50 p-4" onSubmit={(e) => attach(e)}>
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="text-xs font-semibold text-slate-600">Tipo de evidencia
            <select className={FIELD} value={type} onChange={(e) => setType(e.target.value)}>{TYPES.map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>
          <label className="text-xs font-semibold text-slate-600">Archivo (máx. 15 MB)
            <input className={FIELD} required type="file" accept=".pdf,.eml,.msg,.doc,.docx,.png,.jpg,.jpeg,.xlsx" onChange={(e) => setFile(e.target.files?.[0] || null)}/></label>
        </div>
        <label className="block text-xs font-semibold text-slate-600">Observaciones internas
          <textarea className={FIELD} rows={2} value={notes} onChange={(e) => setNotes(e.target.value)}/></label>
        <div className="flex justify-end"><button type="submit" disabled={!file || busy} className={PRIMARY}><Upload size={16}/>Adjuntar evidencia</button></div>
      </form>}
    </Panel>}
    {selected && canWrite && <ControlMailPanel key={selected.id} control={5} year={year} semester={null} eventId={selected.id}
      title={`3.1 Correo del evento #${selected.id} — ${selected.cuenta}`}
      description="Solicita la autorización o informa la modificación desde el buzón corporativo. La copia enviada queda en el expediente de este evento (EML + PDF). La aprobación de Jefatura se adjunta aparte cuando responda."
      evidenceTypes={MAIL_TYPES} defaultType="solicitud" canWrite={canWrite} onArchived={notifyChanges}
      defaultSubject={eventMailDraft(selected).subject} defaultBody={eventMailDraft(selected).body}
      repositoryFiles={eventFiles.map((doc) => ({ id: doc.id, nombre: doc.nombre_archivo, bytes: doc.bytes, origen: `${doc.tipo} · ${doc.estado}` }))}/>}
    <Panel title="4. Consolidado semestral (complementario)" description="Puede incluir un resumen de las autorizaciones, pero no sustituye los correos y cambios por evento.">
      <EvidenceList items={annualFiles}/>
      {canWrite && <form className="mt-4 grid gap-3 sm:grid-cols-3" onSubmit={(e) => attach(e, true)}>
        <label className="text-xs font-semibold text-slate-600">Semestre del consolidado
          <select className={FIELD} value={consolidatedSemester} onChange={(e) => setConsolidatedSemester(e.target.value)}><option value="1">Primer semestre</option><option value="2">Segundo semestre</option></select></label>
        <label className="text-xs font-semibold text-slate-600">Archivo consolidado
          <input required type="file" className={FIELD} accept=".pdf,.doc,.docx,.xlsx,.eml,.msg" onChange={(e) => setConsolidatedFile(e.target.files?.[0] || null)}/></label>
        <label className="text-xs font-semibold text-slate-600">Referencia
          <input className={FIELD} maxLength={250} value={reference} onChange={(e) => setReference(e.target.value)}/></label>
        <div className="sm:col-span-2 flex justify-end"><button type="submit" className={PRIMARY} disabled={!consolidatedFile || busy}><FileText size={16}/>Guardar consolidado</button></div>
      </form>}
    </Panel>
  </div>;
}
