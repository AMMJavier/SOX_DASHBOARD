import { api } from "../../api";

/** Control 7 - VPN internas (LDAP RDP / APLICACIONES). */

// Gerente: cuentas a su cargo en la campaña activa.
export async function getMyInternalAccounts() {
  return (await api.get("/sox/internas/mine")).data;
}

export async function saveInternalDecision(id, { decision, observation }) {
  return (await api.patch(`/sox/internas/${id}`, { decision, observation })).data;
}

export async function confirmAllInternal(validations) {
  return (await api.patch("/sox/internas/confirm-all", { validations })).data;
}

// Administración: listado con filtros, resumen y carga desde LDAP.
export async function getInternalAdmin(params = {}) {
  return (await api.get("/sox/campaign/internas", { params })).data;
}

export async function getInternalDashboard(gerente = "") {
  return (await api.get("/sox/campaign/internas/dashboard", { params: { gerente } })).data;
}

export async function getInternalCampaignRows() {
  return (await api.get("/sox/campaign/internas/todas")).data;
}

export async function getInternalHistoryFilters() {
  return (await api.get("/sox/campaign/internas/historial/filtros")).data;
}

export async function getInternalHistory(params = {}) {
  return (await api.get("/sox/campaign/internas/historial", { params })).data;
}

export async function loadInternalFromLdap() {
  return (await api.post("/sox/campaign/internas/cargar")).data;
}

export const errorText = (error, fallback) => error?.response?.data?.detail || error?.message || fallback;
