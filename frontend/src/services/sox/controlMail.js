import { authenticatedFetch, API_BASE_URL } from "../apiFetch";

const BASE = `${API_BASE_URL}/sox/controls`;

async function parse(response) {
  if (response.ok) return response.json();
  const body = await response.json().catch(() => ({}));
  const error = new Error(typeof body.detail === "string" ? body.detail : `Error HTTP ${response.status}`);
  error.status = response.status;
  throw error;
}

export function newIdempotencyKey() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}-${Math.random().toString(36).slice(2)}`;
}

export function getMailConfig(control) {
  return authenticatedFetch(`${BASE}/${control}/correos/config`).then(parse);
}

export function listControlMails(control, anio, semestre = null, eventoId = null) {
  const qs = new URLSearchParams({ anio: String(anio) });
  if (semestre != null) qs.set("semestre", String(semestre));
  if (eventoId != null) qs.set("evento_id", String(eventoId));
  return authenticatedFetch(`${BASE}/${control}/correos?${qs}`).then(parse);
}

export async function sendControlMail(control, { anio, semestre, tipo, para, cc, asunto, cuerpo, adjuntos, evidenciasIds = [], eventoId = null, idempotencyKey }) {
  const form = new FormData();
  form.append("anio", String(anio));
  if (semestre != null) form.append("semestre", String(semestre));
  form.append("tipo", tipo);
  form.append("para", para);
  form.append("cc", cc || "");
  form.append("asunto", asunto);
  form.append("cuerpo", cuerpo);
  form.append("idempotency_key", idempotencyKey);
  form.append("evidencias_ids", evidenciasIds.join(","));
  if (eventoId != null) form.append("evento_id", String(eventoId));
  for (const file of adjuntos || []) form.append("adjuntos", file);
  return parse(await authenticatedFetch(`${BASE}/${control}/correos`, { method: "POST", body: form }));
}

export async function archiveControlMail(control, id) {
  return parse(await authenticatedFetch(`${BASE}/${control}/correos/${id}/archivar`, { method: "POST" }));
}
