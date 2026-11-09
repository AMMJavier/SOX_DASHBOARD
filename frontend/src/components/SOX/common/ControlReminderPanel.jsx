import { useState } from "react";
import { readStoredUser } from "../../../services/authSession";
import { previewControlReminder, sendControlReminder } from "../../../services/sox/controlEvidence";
import { Panel, FIELD, PRIMARY, SECONDARY, InfoBanner } from "./ControlUI";

/** Previsualizacion y envio SOLO por accion expresa de un administrador SOX. */
export default function ControlReminderPanel({ control, anio, semestre = null }) {
  const [referencia, setReferencia] = useState("");
  const [preview, setPreview] = useState(null);
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState("");
  const isAdmin = readStoredUser()?.rol === "administrador";
  if (!isAdmin) return <InfoBanner caution>Los recordatorios solo pueden gestionarlos los administradores SOX.</InfoBanner>;

  const payload = () => ({ anio: Number(anio), semestre: semestre == null ? null : Number(semestre), referencia });
  async function handlePreview() {
    setBusy(true); setFeedback(""); setPreview(null);
    try { setPreview(await previewControlReminder(control, payload())); }
    catch (e) { setFeedback(e.message || "No se pudo preparar el correo."); }
    finally { setBusy(false); }
  }
  async function handleSend() {
    if (!preview || !window.confirm("¿Confirmas el envío REAL a los destinatarios autorizados? No se adjuntan archivos.")) return;
    setBusy(true); setFeedback("");
    try {
      const result = await sendControlReminder(control, { ...payload(), confirmar: true });
      setFeedback(`Microsoft Graph aceptó el correo. Registro de auditoría: ${result.auditoria_id}.`);
      setPreview(null);
    } catch (e) { setFeedback(e.message || "No se confirmó el envío. Revisa auditoría antes de reintentar."); }
    finally { setBusy(false); }
  }
  return (
    <Panel title="Correo de recordatorio" description="Microsoft Graph corporativo; primero revisar la plantilla y los destinatarios. Envíos deshabilitados por defecto.">
      <label className="block text-xs font-semibold text-slate-600">Referencia interna (opcional)
        <input className={FIELD} maxLength={150} value={referencia}
          onChange={(e) => { setReferencia(e.target.value); setPreview(null); }}
          placeholder="Solicitud, período o identificador" />
      </label>
      <div className="mt-4 flex flex-wrap gap-3">
        <button type="button" onClick={handlePreview} disabled={busy} className={SECONDARY}>Previsualizar correo</button>
        <button type="button" onClick={handleSend} disabled={busy || !preview?.envio_habilitado} className={PRIMARY}>Enviar correo aprobado</button>
      </div>
      {feedback && <p role="status" className="mt-3 rounded-xl bg-amber-50 p-3 text-sm text-amber-800">{feedback}</p>}
      {preview && (
        <div className="mt-4 space-y-2 rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm">
          <p><strong>De:</strong> {preview.mensaje.emisor}</p>
          <p><strong>Para:</strong> {preview.mensaje.destinatarios.join(", ")}</p>
          <p><strong>Asunto:</strong> {preview.mensaje.asunto}</p>
          <pre className="overflow-x-auto whitespace-pre-wrap rounded-lg bg-white p-3 text-slate-700">{preview.mensaje.cuerpo}</pre>
          {!preview.envio_habilitado && <InfoBanner caution>El envío sigue desactivado en el backend hasta que Infraestructura autorice su configuración.</InfoBanner>}
        </div>
      )}
    </Panel>
  );
}
