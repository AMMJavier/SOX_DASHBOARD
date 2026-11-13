import { authenticatedFetch, API_BASE_URL } from "../../apiFetch";

const BASE = `${API_BASE_URL}/sox/controls/6/ldap/cortes`;

async function parse(res) {
  if (res.ok) return res.json();
  const data = await res.json().catch(() => ({}));
  throw new Error(typeof data.detail === "string" ? data.detail : `Error HTTP ${res.status}`);
}

export async function getLatestC6Cut() {
  return parse(await authenticatedFetch(`${BASE}/ultimo`));
}

export async function getC6CutAccounts(id, { offset = 0, limite = 25, buscar = "", grupo = "" } = {}) {
  const qs = new URLSearchParams({ offset: String(offset), limite: String(limite), buscar, grupo });
  return parse(await authenticatedFetch(`${BASE}/${id}/usuarios?${qs}`));
}

export async function syncC6Ldap() {
  return parse(await authenticatedFetch(`${BASE}/sincronizar`, { method: "POST" }));
}
