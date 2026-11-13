import { useState } from "react";
import { Bell, Eye } from "lucide-react";
import { readStoredUser } from "../../../services/authSession";
import { previewControlReminder, sendControlReminder } from "../../../services/sox/common/controlEvidence";
import { Panel, FIELD, PRIMARY, SECONDARY, InfoBanner } from "./ControlUI";

/**
 * Notificación / recordatorio del control. Previsualización y envío SOLO por acción expresa
 * de un administrador SOX. Destinatarios, copias y texto: backend/config/correos.json.
 */
export default function ControlReminderPanel({
  control, anio, semestre = null,
  title = "Correo de recordatorio",
  description = "Microsoft Graph corporativo; primero revisar la plantilla y los destinatarios. Envíos deshabilitados por defecto.",
  sendLabel = "Enviar correo aprobado",
  hideIfNotAdmin = false,
}) {
  const [referencia, setReferencia] = useState("");
  const [preview, setPreview] = useState(null);
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState(null);
  const isAdmin = readStoredUser()?.rol === "administrador";
  if (!isAdmin && hideIfNotAdmin) return null;
  if (!isAdmin) return <InfoBanner caution>Los recordatorios solo pueden gestionarlos los administradores SOX.</InfoBanner>;

  const payload = () => ({ anio: Number(anio), semestre: semestre == null ? null : Number(semestre), referencia });
  async function handlePreview() {
    setBusy(true); setFeedback(null); setPreview(null);
    try { setPreview(await previewControlReminder(control, payload())); }
    catch (e) { setFeedback({ error: true, text: e.message || "No se pudo preparar el correo." }); }
    finally { setBusy(false); }
  }
  async function handleSend() {
    const to = preview?.mensaje?.destinatarios?.join(", ");
    if (!preview || !window.confirm(`¿Confirmas el envío REAL?\n\nPara: ${to}${preview.mensaje.cc?.length ? `\nCC: ${preview.mensaje.cc.join(", ")}` : ""}\n\nNo se adjuntan archivos.`)) return;
    setBusy(true); setFeedback(null);
    try {
      const result = await sendControlReminder(control, { ...payload(), confirmar: true });
      setFeedback({ error: false, text: `Microsoft Graph aceptó el correo. Registro de auditoría: N${control}-${result.auditoria_id}.` });
      setPreview(null);
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
      <div className="mt-4 flex flex-wrap gap-3">
        <button type="button" onClick={handlePreview} disabled={busy} className={SECONDARY}><Eye size={16}/>Previsualizar correo</button>
        <button type="button" onClick={handleSend} disabled={busy || !preview?.envio_habilitado} className={PRIMARY}
          title={preview ? "" : "Primero previsualiza el correo"}><Bell size={16}/>{busy ? "Enviando..." : sendLabel}</button>
      </div>
      {feedback && <p role="status" className={`mt-3 rounded-xl p-3 text-sm ${feedback.error ? "bg-amber-50 text-amber-800" : "bg-emerald-50 text-emerald-800"}`}>{feedback.text}</p>}
      {preview && (
        <div className="mt-4 space-y-2 rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm">
          <p><strong>De:</strong> {preview.mensaje.emisor}</p>
          <p><strong>Para:</strong> {preview.mensaje.destinatarios.join(", ")}</p>
          {preview.mensaje.cc?.length > 0 && <p><strong>CC:</strong> {preview.mensaje.cc.join(", ")}</p>}
          <p><strong>Asunto:</strong> {preview.mensaje.asunto}</p>
          <pre className="overflow-x-auto whitespace-pre-wrap rounded-lg bg-white p-3 text-slate-700">{preview.mensaje.cuerpo}</pre>
          {!preview.envio_habilitado && <InfoBanner caution>El envío sigue desactivado en el backend hasta que Infraestructura autorice su configuración.</InfoBanner>}
        </div>
      )}
    </Panel>
  );
}
