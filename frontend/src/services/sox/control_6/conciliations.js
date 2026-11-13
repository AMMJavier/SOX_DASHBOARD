import { authenticatedFetch, API_BASE_URL } from "../../apiFetch";
const BASE = `${API_BASE_URL}/sox/controls/6/conciliaciones`;

async function parse(response) {
  if (response.ok) return response.json();
  const data = await response.json().catch(() => ({}));
  throw new Error(typeof data.detail === "string" ? data.detail : `Error HTTP ${response.status}`);
}
function buildForm({ corteId, archivo, anio, semestre, referencia }) {
  const form = new FormData();
  form.append("corte_id", String(corteId));
  form.append("archivo_rrhh", archivo);
  if (anio) form.append("anio", String(anio));
  if (semestre) form.append("semestre", String(semestre));
  if (referencia) form.append("referencia_rrhh", referencia);
  return form;
}
export function previewC6Conciliation(input) {
  return authenticatedFetch(`${BASE}/previsualizar`, { method: "POST", body: buildForm(input) }).then(parse);
}
export function saveC6Conciliation(input) {
  return authenticatedFetch(`${BASE}/guardar`, { method: "POST", body: buildForm(input) }).then(parse);
}
export function listC6Conciliations() {
  return authenticatedFetch(`${BASE}/historial`).then(parse);
}
