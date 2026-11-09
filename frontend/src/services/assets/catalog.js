import { authenticatedFetch, API_BASE_URL } from "../apiFetch";
const API_BASE = `${API_BASE_URL}/assets`;

async function request(path, params = {}) {
  const url = new URL(`${API_BASE}${path}`, window.location.origin);

  Object.entries(params).forEach(([key, value]) => {
    if (value !== "" && value !== null && value !== undefined) {
      url.searchParams.set(key, String(value));
    }
  });

  const response = await authenticatedFetch(url, {
    headers: { Accept: "application/json" },
  });

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    throw new Error(
      typeof data?.detail === "string"
        ? data.detail
        : `Error HTTP ${response.status} al consultar ${path}`
    );
  }

  return data;
}

export function getInventory(params = {}) {
  return request("/inventory", params);
}

export function getLocations(params = {}) {
  return request("/locations", params);
}

// Consultar el historial de cambios de los dispositivos.
export function getAssetLogs(params = {}) {
  return request("/logs", params);
}

// Opciones de filtros obtenidas de Oracle.
export function getInventoryOptions() {
  return request("/inventory/options");
}

// Edición del activo por ID, sin modificar otros registros del inventario.
export async function updateInventoryDevice(deviceId, changes) {
  const url = new URL(`${API_BASE}/inventory/${encodeURIComponent(deviceId)}`, window.location.origin);
  const response = await authenticatedFetch(url, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(changes),
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(typeof body.detail === "string" ? body.detail : `Error HTTP ${response.status}`);
  return body;
}

// Resumen paginado: un activo por fila, aunque tenga varios cambios.
export function getAssetLogSummary(params = {}) {
  return request("/logs/summary", params);
}

// Detalle histórico del activo seleccionado (para desplegable).
export function getAssetLogDevice(deviceId, params = {}) {
  return request(`/logs/device/${encodeURIComponent(deviceId)}`, params);
}

// Descarga TODOS los cambios que cumplan los filtros, no solo página actual.
// Utiliza la API existente paginada de a 100 para no cambiar límites del backend.
export async function getAllAssetLogs(params = {}, onProgress = () => {}) {
  const pageSize = 100;
  const first = await getAssetLogs({ ...params, page: 1, page_size: pageSize });
  const result = [...(first.items || [])];
  const total = Number(first.total || 0);
  const pages = Number(first.total_pages || 0);
  onProgress(result.length, total);
  for (let page = 2; page <= pages; page += 1) {
    const next = await getAssetLogs({ ...params, page, page_size: pageSize });
    result.push(...(next.items || []));
    onProgress(result.length, total);
  }
  return result;
}
