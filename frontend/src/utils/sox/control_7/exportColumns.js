/*
 * Columnas de exportación (Excel y PDF) de cada pantalla del Control 7.
 * Cada columna: { header, value(item), width } — value toma el dato con el nombre
 * de campo real que devuelve el backend para ESA pantalla.
 */

const text = (v) => (v === null || v === undefined || v === "" ? "-" : String(v));
const date = (v) => (v ? String(v).replace("T", " ").slice(0, 19) : "-");

/** Campañas > Validaciones de campaña activa (/sox/campaign/validations). */
export const CAMPAIGN_COLUMNS = [
  { header: "REQ", value: (i) => text(i.req), width: 22 },
  { header: "Nombre VPN", value: (i) => text(i.nombre_vpn), width: 34 },
  { header: "Solicitante", value: (i) => text(i.solicitante), width: 28 },
  { header: "Gerente", value: (i) => text(i.manager), width: 30 },
  { header: "Decisión", value: (i) => text(i.status), width: 14 },
  { header: "Confirmado", value: (i) => (i.confirmed === 1 ? "Sí" : "No"), width: 12 },
  { header: "Observación", value: (i) => text(i.observation), width: 44 },
  { header: "Fecha límite", value: (i) => date(i.fecha_limite), width: 20 },
  { header: "Última modificación", value: (i) => date(i.fecha_modificacion), width: 20 },
];

/** Histórico de campañas cerradas (/sox/history). */
export const HISTORY_COLUMNS = [
  { header: "Campaña", value: (i) => text(i.campaign_name), width: 30 },
  { header: "REQ", value: (i) => text(i.req), width: 22 },
  { header: "Nombre VPN", value: (i) => text(i.vpn ?? i.nombre_vpn), width: 34 },
  { header: "Gerente", value: (i) => text(i.manager), width: 30 },
  { header: "Estado", value: (i) => text(i.status), width: 14 },
  { header: "Decisión", value: (i) => text(i.decision), width: 14 },
  { header: "Observación", value: (i) => text(i.observation), width: 44 },
  { header: "Fecha límite", value: (i) => date(i.deadline), width: 20 },
  { header: "Cierre", value: (i) => date(i.closed_at), width: 20 },
];

/** Logs de auditoría del Control 7. */
export const AUDIT_COLUMNS = [
  { header: "Fecha", value: (i) => date(i.fecha_evento), width: 20 },
  { header: "Usuario", value: (i) => text(i.usuario), width: 20 },
  { header: "Acción", value: (i) => text(i.accion), width: 22 },
  { header: "REQ", value: (i) => text(i.req), width: 22 },
  { header: "Nombre VPN", value: (i) => text(i.nombre_vpn), width: 34 },
  { header: "Gerente", value: (i) => text(i.gerente), width: 30 },
  { header: "Estado anterior", value: (i) => text(i.estado_anterior), width: 16 },
  { header: "Estado nuevo", value: (i) => text(i.estado_nuevo), width: 16 },
  { header: "Observación", value: (i) => text(i.observacion_nueva), width: 44 },
];
