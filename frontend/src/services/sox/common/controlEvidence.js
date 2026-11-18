import { authenticatedFetch, API_BASE_URL } from "../../apiFetch";

const BASE = `${API_BASE_URL}/sox/controls`;

async function parse(response) {
  if (response.ok) return response.json();
  const body = await response.json().catch(() => ({}));
  throw new Error(typeof body.detail === "string" ? body.detail : `Error HTTP ${response.status}`);
}

export function getControlEvidences(control, anio, semestre = null) {
  const qs = new URLSearchParams({ anio: String(anio) });
  if (semestre != null) qs.set("semestre", String(semestre));
  return authenticatedFetch(`${BASE}/${control}/evidencias?${qs}`).then(parse);
}

export function getControlHistory(control, anio, semestre = null) {
  const qs = new URLSearchParams({ anio: String(anio) });
  if (semestre != null) qs.set("semestre", String(semestre));
  return authenticatedFetch(`${BASE}/${control}/historial?${qs}`).then(parse);
}

export function getPlanReference(anio) {
  return authenticatedFetch(`${BASE}/3/plan-referencia?anio=${encodeURIComponent(anio)}`).then(parse);
}

export async function uploadControlEvidence(control, { file, anio, semestre, tipo, referencia, observaciones, eventoId = null }) {
  const form = new FormData();
  form.append("file", file);
  form.append("anio", String(anio));
  if (semestre != null) form.append("semestre", String(semestre));
  form.append("tipo", tipo);
  if (eventoId != null) form.append("evento_id", String(eventoId));
  form.append("referencia", referencia || "");
  form.append("observaciones", observaciones || "");
  return parse(await authenticatedFetch(`${BASE}/${control}/evidencias`, { method: "POST", body: form }));
}

export async function verifyControlEvidence(control, id) {
  return parse(await authenticatedFetch(`${BASE}/${control}/evidencias/${id}/verificar`, { method: "POST" }));
}

export async function downloadControlEvidence(control, id, filename) {
  const response = await authenticatedFetch(`${BASE}/${control}/evidencias/${id}/descargar`);
  if (!response.ok) throw new Error(`Error HTTP ${response.status} al descargar`);
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = String(filename || `evidencia-${id}`).replace(/[\\/]/g, "_");
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

export async function reconcileInternalAccess(rrhh, accesos) {
  return parse(await authenticatedFetch(`${BASE}/6/conciliar`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ rrhh, accesos, fuente: "CORTE_MANUAL" }),
  }));
}

export function getControl5Events(anio) {
  return authenticatedFetch(`${BASE}/5/eventos?anio=${encodeURIComponent(anio)}`).then(parse);
}

export function createControl5Event(data) {
  return authenticatedFetch(`${BASE}/5/eventos`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  }).then(parse);
}


/** Fecha tope del período, días restantes y si venció (correos.json > controles.<n>.calendario). */
export function getControlCalendar(control, anio, semestre = null) {
  const qs = new URLSearchParams({ anio: String(anio) });
  if (semestre != null) qs.set("semestre", String(semestre));
  return authenticatedFetch(`${BASE}/${control}/calendario?${qs}`).then(parse);
}

export function previewControlReminder(control, data) {
  return authenticatedFetch(`${BASE}/${control}/recordatorios/previsualizar`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  }).then(parse);
}

/** Envía la notificación; adjuntos: archivos del equipo; evidenciasIds: documentos del repositorio. */
export function sendControlReminder(control, { anio, semestre, referencia, confirmar, adjuntos = [], evidenciasIds = [] }) {
  const form = new FormData();
  form.append("anio", String(anio));
  if (semestre != null) form.append("semestre", String(semestre));
  form.append("referencia", referencia || "");
  form.append("confirmar", confirmar ? "true" : "false");
  form.append("evidencias_ids", evidenciasIds.join(","));
  for (const file of adjuntos) form.append("adjuntos", file);
  return authenticatedFetch(`${BASE}/${control}/recordatorios/enviar`, { method: "POST", body: form }).then(parse);
}

/** Busca ahora en el buzón las respuestas a los correos con código del control. */
export function searchMailReplies(control) {
  return authenticatedFetch(`${BASE}/${control}/correos/respuestas/buscar`, { method: "POST" }).then(parse);
}

/** Aprobación manual de un correo respondido sin "OK" (administrador). */
export function approveMailReply(control, correoId) {
  return authenticatedFetch(`${BASE}/${control}/correos/${correoId}/aprobar`, { method: "POST" }).then(parse);
}

export function getInternalLdapAccess() {
  return authenticatedFetch(`${BASE}/6/ldap/accesos`).then(parse);
}
