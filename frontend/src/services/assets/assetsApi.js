import { authenticatedFetch, API_BASE_URL } from "../apiFetch";



const ASSETS_BASE_URL = `${API_BASE_URL}/assets`;

async function request(endpoint, options = {}) {
  const response = await authenticatedFetch(`${ASSETS_BASE_URL}${endpoint}`, {
    ...options,
    headers: {
      Accept: "application/json",
      ...options.headers,
    },
  });

  if (!response.ok) {
    let detail = `Error HTTP ${response.status}`;

    try {
      const body = await response.json();
      detail = body.detail || detail;
    } catch {
      // La respuesta no contiene JSON.
    }

    throw new Error(detail);
  }

  return response.json();
}

function buildQuery(params = {}) {
  const query = new URLSearchParams();

  Object.entries(params).forEach(([key, value]) => {
    if (
      value !== undefined &&
      value !== null &&
      String(value).trim() !== ""
    ) {
      query.set(key, String(value));
    }
  });

  const result = query.toString();
  return result ? `?${result}` : "";
}

/**
 * Dashboard general de activos.
 * GET /assets/dashboard
 */
export function getAssetsDashboard(ciudad = "") {
  return request(
    `/dashboard${buildQuery({ ciudad })}`
  );
}

/**
 * Consulta paginada del inventario.
 * GET /assets/inventory
 */
export function getAssetsInventory({
  q = "",
  ciudad = "",
  estado = "",
  plataforma = "",
  tipo = "",
  fabricante = "",
  page = 1,
  page_size = 25,
} = {}) {
  return request(
    `/inventory${buildQuery({
      q,
      ciudad,
      estado,
      plataforma,
      tipo,
      fabricante,
      page,
      page_size,
    })}`
  );
}

/**
 * Ubicaciones agrupadas por ciudad, localidad, piso y lado.
 * GET /assets/locations
 */
export function getAssetsLocations(ciudad = "") {
  return request(
    `/locations${buildQuery({ ciudad })}`
  );
}
