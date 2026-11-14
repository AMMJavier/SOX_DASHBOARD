import { useEffect, useRef, useState } from "react";
import { Mail, Paperclip, RotateCcw, Send, X } from "lucide-react";
import { archiveControlMail, getMailConfig, listControlMails, newIdempotencyKey, sendControlMail } from "../../../services/sox/common/controlMail";
import { downloadControlEvidence } from "../../../services/sox/common/controlEvidence";
import { FIELD, InfoBanner, Panel, PRIMARY, SECONDARY } from "./ControlUI";

const STATUS = {
  PENDIENTE: { label: "Sin confirmar", className: "text-amber-700", help: "Graph no confirmó el envío; revisar el buzón antes de reenviar." },
  ACEPTADO: { label: "Enviado · archivo pendiente", className: "text-amber-700", help: "El correo salió; falta guardar su copia como evidencia." },
  ARCHIVANDO: { label: "Archivando...", className: "text-blue-700" },
  ARCHIVADO: { label: "Archivado como evidencia", className: "text-emerald-700" },
  FALLIDO: { label: "Fallido", className: "text-red-700", help: "Graph rechazó el envío; no salió ningún correo." },
};

const emptyDraft = (defaultType, asunto = "", cuerpo = "") => ({ para: "", cc: "", asunto, cuerpo, tipo: defaultType });

// Plantillas de backend/config/correos.json: reemplaza {variable}; las desconocidas quedan igual.
const renderTemplate = (text, vars) => String(text || "").replace(/\{(\w+)\}/g, (match, key) => (key in vars ? String(vars[key] ?? "") : match));

/**
 * Correo formal a Gerencia/Jefatura enviado desde SOX por el buzón corporativo.
 * Tras el envío, la copia de Elementos enviados se guarda como evidencia (EML + PDF).
 * Control 5: recibe eventId y el correo queda dentro del expediente de ese evento.
 */
export default function ControlMailPanel({
  control, year, semester = null, evidenceTypes, defaultType, canWrite, onArchived, repositoryFiles = [],
  eventId = null, defaultSubject = "", defaultBody = "", templateVars = null,
  title = "Enviar correo formal",
  description = "Solicitud de revisión o aprobación a Gerencia/Jefatura desde el buzón corporativo. La copia enviada se guarda automáticamente como evidencia.",
}) {
  const [config, setConfig] = useState(null);
  const [configError, setConfigError] = useState("");
  // Si correos.json define "correo_formal" para el control y hay variables, el borrador usa esa plantilla.
  const draftTexts = (cfg) => {
    const tpl = cfg?.plantilla_borrador;
    if (!tpl || !templateVars) return { asunto: defaultSubject, cuerpo: defaultBody };
    return { asunto: renderTemplate(tpl.asunto, templateVars).slice(0, 200), cuerpo: renderTemplate(tpl.cuerpo, templateVars) };
  };
  const initialDraft = (cfg = config) => ({ ...emptyDraft(defaultType || evidenceTypes[0]?.key), ...draftTexts(cfg) });
  const [draft, setDraft] = useState(initialDraft);
  const [files, setFiles] = useState([]);
  const [repoSelected, setRepoSelected] = useState([]);
  const [items, setItems] = useState([]);
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState(null);
  const [refresh, setRefresh] = useState(0);
  // Una clave por borrador: un doble clic o un reintento de red no envía dos veces.
  const idempotencyKey = useRef(newIdempotencyKey());

  useEffect(() => {
    if (!canWrite) return;
    getMailConfig(control).then((cfg) => {
      setConfig(cfg);
      // Aplica la plantilla solo si el usuario todavía no modificó el borrador.
      setDraft((d) => (d.asunto === defaultSubject && d.cuerpo === defaultBody ? { ...d, ...draftTexts(cfg) } : d));
    }).catch((e) => setConfigError(e.message));
  }, [control, canWrite]);

  useEffect(() => {
    if (!canWrite) return;
    let live = true;
    listControlMails(control, Number(year), semester, eventId)
      .then((data) => { if (live) setItems(data.items || []); })
      .catch((e) => { if (live) setFeedback({ caution: true, text: `No se pudo consultar los correos: ${e.message}` }); });
    return () => { live = false; };
  }, [control, year, semester, eventId, refresh, canWrite]);

  if (!canWrite) return null;

  const update = (field) => (e) => setDraft((d) => ({ ...d, [field]: e.target.value }));
  const selectedRepo = repositoryFiles.filter((f) => repoSelected.includes(f.id));
  const totalBytes = files.reduce((sum, f) => sum + f.file.size, 0) + selectedRepo.reduce((sum, f) => sum + (f.bytes || 0), 0);
  const maxBytes = (config?.max_adjuntos_mb ?? 3) * 1024 * 1024;
  const maxCount = config?.max_adjuntos ?? 5;
  const totalCount = files.length + selectedRepo.length;
  const canSend = config?.envio_habilitado && config?.control_habilitado && !busy
    && draft.para.trim() && draft.asunto.trim() && draft.cuerpo.trim() && totalBytes <= maxBytes && totalCount <= maxCount;
  const toggleRepo = (id) => setRepoSelected((current) => current.includes(id) ? current.filter((x) => x !== id) : [...current, id]);

  const addFiles = (e) => {
    const next = Array.from(e.target.files || []).map((file) => ({ id: `${Date.now()}-${Math.random()}`, file }));
    setFiles((current) => [...current, ...next].slice(0, Math.max(0, maxCount - selectedRepo.length)));
    e.target.value = "";
  };

  const resetDraft = () => {
    setDraft(initialDraft());
    setFiles([]);
    setRepoSelected([]);
    idempotencyKey.current = newIdempotencyKey();
  };

  async function handleSend() {
    const fixedCc = config.copias_fijas?.length ? `\nCopia automática: ${config.copias_fijas.join("; ")}` : "";
    const summary = `Se enviará un correo REAL desde ${config.emisor}\n\nPara: ${draft.para}${draft.cc ? `\nCC: ${draft.cc}` : ""}${fixedCc}\nAsunto: ${draft.asunto}\nAdjuntos: ${totalCount}\n\nLuego se archivará como evidencia del Control ${control}. ¿Confirmas el envío?`;
    if (!window.confirm(summary)) return;
    setBusy(true);
    setFeedback(null);
    // Traza en la consola del navegador (F12): qué se envía al servidor.
    console.info(`[SOX CORREO] Control ${control}: enviando`, {
      anio: Number(year), semestre: semester, tipo: draft.tipo, para: draft.para, cc: draft.cc,
      asunto: draft.asunto, adjuntosEquipo: files.length, adjuntosRepositorio: selectedRepo.map((f) => f.id), evento: eventId,
    });
    try {
      // Antes: "semestre" (variable inexistente) -> ReferenceError "semestre is not defined"
      // y el correo nunca llegaba al servidor. El prop del componente es "semester".
      const result = await sendControlMail(control, {
        anio: Number(year), semestre: semester, tipo: draft.tipo, para: draft.para, cc: draft.cc,
        asunto: draft.asunto, cuerpo: draft.cuerpo, adjuntos: files.map((f) => f.file), evidenciasIds: selectedRepo.map((f) => f.id), eventoId: eventId,
        idempotencyKey: idempotencyKey.current,
      });
      console.info(`[SOX CORREO] Control ${control}: respuesta del servidor`, result);
      if (result.repetido) {
        setFeedback({ caution: true, text: `Esta solicitud ya había sido procesada (correo #${result.id}, ${STATUS[result.estado]?.label || result.estado}). No se envió de nuevo.` });
      } else if (result.estado === "ARCHIVADO") {
        setFeedback({ caution: false, text: `Correo #${result.id} enviado y archivado como evidencia (EML + PDF). Queda pendiente de verificación interna.` });
      } else {
        setFeedback({ caution: true, text: `Correo #${result.id} enviado. ${result.detalle || "La copia aún no se archivó; usa \"Reintentar archivado\"."}` });
      }
      resetDraft();
      onArchived?.();
    } catch (e) {
      console.error(`[SOX CORREO] Control ${control}: error al enviar (HTTP ${e.status ?? "sin respuesta"})`, e);
      // 502: Graph rechazó el envío (no salió). Se permite un nuevo intento con otra clave.
      if (e.status === 502) idempotencyKey.current = newIdempotencyKey();
      setFeedback({ caution: true, text: e.message || "No se pudo enviar el correo." });
    } finally {
      setBusy(false);
      setRefresh((n) => n + 1);
    }
  }

  async function handleArchive(id) {
    setBusy(true);
    setFeedback(null);
    try {
      console.info(`[SOX CORREO] Control ${control}: reintentando archivado del correo #${id}`);
      const result = await archiveControlMail(control, id);
      console.info(`[SOX CORREO] Control ${control}: archivado #${id} ->`, result.estado, result.detalle || "");
      setFeedback({ caution: result.estado !== "ARCHIVADO", text: result.estado === "ARCHIVADO" ? `Correo #${id} archivado como evidencia.` : (result.detalle || "Archivado pendiente.") });
      onArchived?.();
    } catch (e) {
      console.error(`[SOX CORREO] Control ${control}: error al archivar #${id} (HTTP ${e.status ?? "sin respuesta"})`, e);
      setFeedback({ caution: true, text: e.message });
    }
    finally { setBusy(false); setRefresh((n) => n + 1); }
  }

  const download = (id, name) => downloadControlEvidence(control, id, name).catch((e) => setFeedback({ caution: true, text: e.message }));

  return <div className="space-y-5">
    <Panel title={title} description={description}>
      {configError && <InfoBanner caution>No se pudo leer la configuración de correo: {configError}</InfoBanner>}
      {config && !config.control_habilitado && <InfoBanner caution>El envío de correos aún no está habilitado para este control.</InfoBanner>}
      {config && config.control_habilitado && !config.envio_habilitado && <InfoBanner caution>El envío está desactivado en el servidor (SOX_MAIL_ENABLED) hasta completar la autorización del buzón.</InfoBanner>}
      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        <label className="text-xs font-semibold text-slate-600">Para
          <input value={draft.para} onChange={update("para")} placeholder="gerencia@dominio.com; jefatura@dominio.com" className={FIELD}/>
        </label>
        <label className="text-xs font-semibold text-slate-600">CC (opcional)
          <input value={draft.cc} onChange={update("cc")} placeholder="Tu correo u otros responsables" className={FIELD}/>
        </label>
        <label className="text-xs font-semibold text-slate-600">Asunto
          <input value={draft.asunto} onChange={update("asunto")} maxLength={200} className={FIELD}/>
        </label>
        <label className="text-xs font-semibold text-slate-600">Registrar como evidencia de tipo
          <select value={draft.tipo} onChange={update("tipo")} className={FIELD}>
            {evidenceTypes.map((t) => <option key={t.key} value={t.key}>{t.label}</option>)}
          </select>
        </label>
      </div>
      <label className="mt-4 block text-xs font-semibold text-slate-600">Mensaje
        <textarea value={draft.cuerpo} onChange={update("cuerpo")} rows={7} maxLength={10000} className={FIELD}
          placeholder="Describe la revisión o los cambios realizados y la solicitud a Gerencia."/>
      </label>
      <p className="mt-1 text-xs text-slate-500">Al final del mensaje se agrega automáticamente quién lo envió desde SOX y su referencia.
        {config?.dominios_permitidos?.length ? ` Dominios permitidos: ${config.dominios_permitidos.join(", ")}.` : ""}
        {config?.copias_fijas?.length ? ` Copia automática (correos.json): ${config.copias_fijas.join(", ")}.` : ""}</p>
      {repositoryFiles.length > 0 && <fieldset className="mt-4">
        <legend className="text-xs font-semibold text-slate-600">Adjuntar desde el repositorio (sin volver a subir el archivo)</legend>
        <ul className="mt-2 space-y-2">{repositoryFiles.map((f) => <li key={f.id}>
          <label className="flex cursor-pointer items-center gap-3 rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm hover:bg-slate-100">
            <input type="checkbox" checked={repoSelected.includes(f.id)} onChange={() => toggleRepo(f.id)} className="h-4 w-4"/>
            <span className="min-w-0 flex-1"><span className="block truncate font-semibold text-slate-700">{f.nombre}</span>
              <span className="text-xs text-slate-500">{f.origen}{f.bytes ? ` · ${(f.bytes / 1024).toFixed(1)} KB` : ""}</span></span>
          </label>
        </li>)}</ul>
      </fieldset>}
      <label className="mt-4 block text-xs font-semibold text-slate-600">Adjuntos desde tu equipo (máximo {maxCount} en total, {config?.max_adjuntos_mb ?? 3} MB)
        <input type="file" multiple accept={(config?.extensiones || [".pdf", ".docx"]).join(",")} onChange={addFiles}
          className="mt-2 block w-full text-sm text-slate-600 file:mr-3 file:rounded-xl file:border-0 file:bg-blue-100 file:px-4 file:py-2.5 file:font-semibold file:text-blue-800"/>
      </label>
      {files.length > 0 && <ul className="mt-4 space-y-2">{files.map(({ id, file }) => <li key={id} className="flex items-center gap-3 rounded-xl border border-slate-200 bg-slate-50 p-3">
        <Paperclip size={18} className="text-blue-600"/><div className="min-w-0 flex-1"><p className="truncate text-sm font-semibold text-slate-700">{file.name}</p><p className="text-xs text-slate-500">{(file.size / 1024).toFixed(1)} KB</p></div>
        <button type="button" title="Quitar adjunto" className="rounded-lg p-2 hover:bg-slate-200" onClick={() => setFiles((c) => c.filter((x) => x.id !== id))}><X size={17}/></button>
      </li>)}</ul>}
      {(totalBytes > maxBytes || totalCount > maxCount) && <p className="mt-2 text-xs font-semibold text-red-700">Los adjuntos superan el máximo permitido.</p>}
      <div className="mt-4 flex flex-wrap justify-end gap-3">
        <button type="button" onClick={resetDraft} disabled={busy} className={SECONDARY}><RotateCcw size={16}/>Limpiar</button>
        <button type="button" onClick={handleSend} disabled={!canSend} className={PRIMARY}><Send size={16}/>{busy ? "Procesando..." : "Enviar y archivar"}</button>
      </div>
      {feedback && <div className="mt-4"><InfoBanner caution={feedback.caution}>{feedback.text}</InfoBanner></div>}
    </Panel>

    <Panel title="Correos enviados desde SOX" description={eventId ? `Correos de este evento (#${eventId}) y su archivado en el expediente.` : "Estado del envío y de su archivado como evidencia del período seleccionado."}>
      {items.length === 0
        ? <p className="text-sm text-slate-500">No hay correos enviados desde SOX en este período.</p>
        : <div className="overflow-x-auto"><table className="w-full min-w-[760px] text-left text-sm"><thead className="bg-slate-100 text-slate-600"><tr>
            <th className="px-3 py-3">Fecha (UTC)</th><th className="px-3 py-3">Asunto / destinatarios</th><th className="px-3 py-3">Estado</th><th className="px-3 py-3">Evidencia</th>
          </tr></thead><tbody>{items.map((item) => {
            const status = STATUS[item.estado] || { label: item.estado, className: "text-slate-700" };
            return <tr key={item.id} className="border-t border-slate-100 align-top">
              <td className="whitespace-nowrap px-3 py-3 text-slate-600">{(item.fecha_envio || item.fecha_solicitud)?.replace("T", " ").slice(0, 19)}<p className="text-xs text-slate-500">#{item.id} · {item.solicitado_por}</p></td>
              <td className="px-3 py-3"><p className="flex items-center gap-2 font-semibold text-slate-800"><Mail size={15} className="shrink-0 text-blue-600"/>{item.asunto}</p>
                <p className="text-xs text-slate-500">Para: {item.destinatarios}{item.cc ? ` · CC: ${item.cc}` : ""}</p>
                {item.adjuntos && <p className="text-xs text-slate-500">Adjuntos: {item.adjuntos}</p>}</td>
              <td className="px-3 py-3"><span className={`font-semibold ${status.className}`}>{status.label}</span>
                {(item.detalle || status.help) && <p className="mt-1 max-w-xs text-xs text-slate-500">{item.detalle || status.help}</p>}</td>
              <td className="px-3 py-3"><div className="flex flex-wrap gap-2">
                {item.evidencia_eml_id && <button type="button" className={SECONDARY} onClick={() => download(item.evidencia_eml_id, item.eml_nombre)}>EML</button>}
                {item.evidencia_pdf_id && <button type="button" className={SECONDARY} onClick={() => download(item.evidencia_pdf_id, item.pdf_nombre)}>PDF</button>}
                {item.estado === "ACEPTADO" && <button type="button" disabled={busy} className={PRIMARY} onClick={() => handleArchive(item.id)}>Reintentar archivado</button>}
              </div></td>
            </tr>;
          })}</tbody></table></div>}
    </Panel>
  </div>;
}
