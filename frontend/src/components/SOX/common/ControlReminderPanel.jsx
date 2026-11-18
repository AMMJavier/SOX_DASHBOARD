import { useState } from "react";
import { Bell, Eye, Paperclip, X } from "lucide-react";
import { readStoredUser } from "../../../services/authSession";
import { previewControlReminder, sendControlReminder } from "../../../services/sox/common/controlEvidence";
import { Panel, FIELD, PRIMARY, SECONDARY, InfoBanner } from "./ControlUI";
import RepositoryFilePicker from "./RepositoryFilePicker";

const MAX_FILES = 5;
const MAX_MB = 3;
const ACCEPT = ".pdf,.doc,.docx,.xlsx,.png,.jpg,.jpeg,.msg,.eml";

/**
 * Notificación / recordatorio del control. Previsualización y envío SOLO por acción expresa
 * de un administrador SOX. Destinatarios, copias y texto: backend/config/correos.json.
 * Se pueden adjuntar archivos del equipo o del repositorio (repositoryFiles).
 * En los controles con código (backend/config/formatos.json) el asunto lleva "[SOX 001-1]"
 * y la copia enviada queda como evidencia a la espera de la respuesta "OK".
 */
export default function ControlReminderPanel({
  control, anio, semestre = null,
  title = "Correo de recordatorio",
  description = "Microsoft Graph corporativo; primero revisar la plantilla y los destinatarios. Envíos deshabilitados por defecto.",
  sendLabel = "Enviar correo aprobado",
  hideIfNotAdmin = false,
  repositoryFiles = [],
  onSent,
}) {
  const [referencia, setReferencia] = useState("");
  const [preview, setPreview] = useState(null);
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState(null);
  const [files, setFiles] = useState([]);
  const [repoSelected, setRepoSelected] = useState([]);
  const isAdmin = readStoredUser()?.rol === "administrador";
  if (!isAdmin && hideIfNotAdmin) return null;
  if (!isAdmin) return <InfoBanner caution>Los recordatorios solo pueden gestionarlos los administradores SOX.</InfoBanner>;

  const selectedRepo = repositoryFiles.filter((f) => repoSelected.includes(f.id));
  const totalCount = files.length + selectedRepo.length + (preview?.mensaje?.adjuntos?.length || 0);
  const totalBytes = files.reduce((s, f) => s + f.file.size, 0) + selectedRepo.reduce((s, f) => s + (f.bytes || 0), 0);
  const overLimit = totalCount > MAX_FILES || totalBytes > MAX_MB * 1024 * 1024;
  const toggleRepo = (id) => setRepoSelected((c) => (c.includes(id) ? c.filter((x) => x !== id) : [...c, id]));
  const addFiles = (e) => {
    const next = Array.from(e.target.files || []).map((file) => ({ id: `${Date.now()}-${Math.random()}`, file }));
    setFiles((c) => [...c, ...next]);
    e.target.value = "";
  };

  const payload = () => ({ anio: Number(anio), semestre: semestre == null ? null : Number(semestre), referencia });
  async function handlePreview() {
    setBusy(true); setFeedback(null); setPreview(null);
    try { setPreview(await previewControlReminder(control, payload())); }
    catch (e) { setFeedback({ error: true, text: e.message || "No se pudo preparar el correo." }); }
    finally { setBusy(false); }
  }
  async function handleSend() {
    const m = preview?.mensaje;
    if (!m) return;
    const names = [...(m.adjuntos || []).map((a) => a.nombre), ...selectedRepo.map((f) => f.nombre), ...files.map((f) => f.file.name)];
    const summary = `¿Confirmas el envío REAL?\n\nPara: ${m.destinatarios.join(", ")}${m.cc?.length ? `\nCC: ${m.cc.join(", ")}` : ""}`
      + `\nAsunto: ${m.asunto}\nAdjuntos: ${names.length ? names.join(", ") : "ninguno"}`;
    if (!window.confirm(summary)) return;
    setBusy(true); setFeedback(null);
    try {
      const result = await sendControlReminder(control, {
        ...payload(), confirmar: true, adjuntos: files.map((f) => f.file), evidenciasIds: selectedRepo.map((f) => f.id),
      });
      const code = result.codigo ? ` Código ${result.codigo}.` : "";
      const archived = result.codigo
        ? (result.estado === "ARCHIVADO" ? " La copia quedó como evidencia en estado Pendiente hasta que respondan con OK." : " La copia aún no se archivó; se reintentará en la próxima búsqueda de respuestas.")
        : "";
      setFeedback({ error: false, text: `Microsoft Graph aceptó el correo.${code} Registro de auditoría: N${control}-${result.auditoria_id}.${archived}` });
      setPreview(null); setFiles([]); setRepoSelected([]);
      onSent?.();
    } catch (e) { setFeedback({ error: true, text: e.message || "No se confirmó el envío. Revisa auditoría antes de reintentar." }); }
    finally { setBusy(false); }
  }
  return (
    <Panel title={title} description={description}>
      <label className="block text-xs font-semibold text-slate-600">Referencia interna (opcional)
        <input className={FIELD} maxLength={150} value={referencia}
          onChange={(e) => { setReferencia(e.target.value); setPreview(null); }}
          placeholder="Solicitud, período o identificador" />
      </label>
      <RepositoryFilePicker files={repositoryFiles} selected={repoSelected} onToggle={toggleRepo}
        legend="Adjuntar evidencia del repositorio"/>
      <label className="mt-4 block text-xs font-semibold text-slate-600">Adjuntar desde tu equipo (máximo {MAX_FILES} en total, {MAX_MB} MB)
        <input type="file" multiple accept={ACCEPT} onChange={addFiles}
          className="mt-2 block w-full text-sm text-slate-600 file:mr-3 file:rounded-xl file:border-0 file:bg-blue-100 file:px-4 file:py-2.5 file:font-semibold file:text-blue-800"/>
      </label>
      {files.length > 0 && <ul className="mt-3 space-y-2">{files.map(({ id, file }) => <li key={id} className="flex items-center gap-3 rounded-xl border border-slate-200 bg-slate-50 p-3">
        <Paperclip size={18} className="text-blue-600"/><div className="min-w-0 flex-1"><p className="truncate text-sm font-semibold text-slate-700">{file.name}</p><p className="text-xs text-slate-500">{(file.size / 1024).toFixed(1)} KB</p></div>
        <button type="button" title="Quitar adjunto" className="rounded-lg p-2 hover:bg-slate-200" onClick={() => setFiles((c) => c.filter((x) => x.id !== id))}><X size={17}/></button>
      </li>)}</ul>}
      {overLimit && <p className="mt-2 text-xs font-semibold text-red-700">Los adjuntos superan el máximo permitido ({MAX_FILES} archivos o {MAX_MB} MB).</p>}
      <div className="mt-4 flex flex-wrap gap-3">
        <button type="button" onClick={handlePreview} disabled={busy} className={SECONDARY}><Eye size={16}/>Previsualizar correo</button>
        <button type="button" onClick={handleSend} disabled={busy || !preview?.envio_habilitado || overLimit} className={PRIMARY}
          title={preview ? "" : "Primero previsualiza el correo"}><Bell size={16}/>{busy ? "Enviando..." : sendLabel}</button>
      </div>
      {feedback && <p role="status" className={`mt-3 rounded-xl p-3 text-sm ${feedback.error ? "bg-amber-50 text-amber-800" : "bg-emerald-50 text-emerald-800"}`}>{feedback.text}</p>}
      {preview && (
        <div className="mt-4 space-y-2 rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm">
          <p><strong>De:</strong> {preview.mensaje.emisor}</p>
          <p><strong>Para:</strong> {preview.mensaje.destinatarios.join(", ")}</p>
          {preview.mensaje.cc?.length > 0 && <p><strong>CC:</strong> {preview.mensaje.cc.join(", ")}</p>}
          <p><strong>Asunto:</strong> {preview.mensaje.asunto}</p>
          {preview.mensaje.codigo && <p><strong>Código del correo:</strong> {preview.mensaje.codigo} <span className="text-xs text-slate-500">(la respuesta "OK" a este correo lo marca como Aprobado)</span></p>}
          {(preview.mensaje.adjuntos?.length > 0 || selectedRepo.length > 0 || files.length > 0) && <p><strong>Adjuntos:</strong> {[
            ...preview.mensaje.adjuntos.map((a) => `${a.nombre} (último archivo subido en Control ${a.control}, ${a.fecha})`),
            ...selectedRepo.map((f) => f.nombre), ...files.map((f) => f.file.name),
          ].join(", ")}</p>}
          <pre className="overflow-x-auto whitespace-pre-wrap rounded-lg bg-white p-3 text-slate-700">{preview.mensaje.cuerpo}</pre>
          {!preview.envio_habilitado && <InfoBanner caution>El envío sigue desactivado en el backend hasta que Infraestructura autorice su configuración.</InfoBanner>}
        </div>
      )}
    </Panel>
  );
}
