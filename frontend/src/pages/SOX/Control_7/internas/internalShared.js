/** Utilidades compartidas de las pantallas de VPN internas (mismas etiquetas que VPN externas). */

export const DECISION_LABEL = { mantener: "Mantener", eliminar: "Eliminar", "no pertenece": "No pertenece", otro: "Otro" };
export const ACCESS_LABEL = { RDP: "RDP", APLICACIONES: "Aplicaciones" };

/** Estado para StatusBadge: Sin Responsable, Confirmado, Vencido o Pendiente. */
export function internalStatus(item, campaignExpired) {
  if (!item.gerente) return "Sin Responsable";
  if (item.confirmacion === 1) return "Confirmado";
  return campaignExpired ? "Vencido" : "Pendiente";
}

const text = (v) => (v === null || v === undefined || v === "" ? "-" : String(v));
const date = (v) => (v ? String(v).replace("T", " ").slice(0, 19) : "-");

export const INTERNAL_CAMPAIGN_COLUMNS = [
  { header: "Cuenta", value: (i) => text(i.usuario), width: 18 },
  { header: "Nombre", value: (i) => text(i.nombre), width: 32 },
  { header: "Acceso", value: (i) => text(ACCESS_LABEL[i.tipo_acceso]), width: 14 },
  { header: "Gerente", value: (i) => text(i.gerente), width: 30 },
  { header: "Confirmado", value: (i) => (i.confirmacion === 1 ? "Sí" : "No"), width: 12 },
  { header: "Decisión", value: (i) => (i.confirmacion === 1 ? DECISION_LABEL[i.estado] : "-"), width: 14 },
  { header: "Observación", value: (i) => text(i.observacion), width: 40 },
  { header: "Confirmó", value: (i) => text(i.confirmado_por), width: 16 },
  { header: "Última modificación", value: (i) => date(i.fecha_modificacion), width: 20 },
];

export const INTERNAL_AUDIT_COLUMNS = [
  { header: "Fecha", value: (i) => date(i.fecha_evento), width: 20 },
  { header: "Usuario", value: (i) => text(i.usuario), width: 18 },
  { header: "Gerente", value: (i) => text(i.gerente), width: 30 },
  { header: "Cuenta", value: (i) => text(i.cuenta), width: 18 },
  { header: "Acceso", value: (i) => text(ACCESS_LABEL[i.tipo_acceso]), width: 14 },
  { header: "Acción", value: (i) => text(i.accion), width: 24 },
  { header: "Estado anterior", value: (i) => text(DECISION_LABEL[i.estado_anterior] || i.estado_anterior), width: 16 },
  { header: "Estado nuevo", value: (i) => text(DECISION_LABEL[i.estado_nuevo] || i.estado_nuevo), width: 16 },
  { header: "Observación", value: (i) => text(i.observacion_nueva), width: 40 },
];

export const INTERNAL_HISTORY_COLUMNS = [
  { header: "Campaña", value: (i) => text(i.campaign_name), width: 30 },
  ...INTERNAL_CAMPAIGN_COLUMNS,
  { header: "Fecha límite", value: (i) => date(i.deadline), width: 20 },
];
