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

export async function getInternalAuditLog() {
  return (await api.get("/sox/campaign/internas/seguimiento")).data;
}

// Notificación a gerentes de VPN internas (mismo formato que la de externas).
export async function getInternalNotifications() {
  return (await api.get("/sox/campaign/internas/notificaciones")).data;
}

export async function sendInternalNotifications(claves = null) {
  return (await api.post("/sox/campaign/internas/notificaciones/enviar", { confirmar: true, claves })).data;
}

export async function loadInternalFromLdap(reemplazar = false) {
  return (await api.post("/sox/campaign/internas/cargar", null, { params: { reemplazar } })).data;
}

// Gerente asignado a mano a cuentas sin gerente en AD (casos especiales).
export async function getInternalManagers() {
  return (await api.get("/sox/campaign/internas/gerentes")).data;
}

export async function lookupInternalManager(usuario) {
  return (await api.get(`/sox/campaign/internas/gerentes/ad/${encodeURIComponent(usuario)}`)).data;
}

// Búsqueda en AD por cuenta o por nombre.
export async function searchInternalManagersAd(q) {
  return (await api.get("/sox/campaign/internas/gerentes/buscar-ad", { params: { q } })).data;
}

export async function assignInternalManager({ ids, usuario, nombre = null, correo = null }) {
  return (await api.post("/sox/campaign/internas/asignar-gerente", { ids, usuario, nombre, correo })).data;
}

export const errorText = (error, fallback) => error?.response?.data?.detail || error?.message || fallback;
