// Hora oficial de la plataforma: Ecuador continental (UTC-5, sin horario de verano).
export const APP_TIME_ZONE = "America/Guayaquil";

const FORMATTER = new Intl.DateTimeFormat("en-CA", {
  timeZone: APP_TIME_ZONE,
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  hourCycle: "h23",
});

const HAS_OFFSET = /(Z|[+-]\d{2}:?\d{2})$/i;
const DATE_ONLY = /^\d{4}-\d{2}-\d{2}$/;

function ecuadorParts(date) {
  const parts = {};
  for (const { type, value } of FORMATTER.formatToParts(date)) parts[type] = value;
  return parts;
}

// Convierte el valor a Date. Las fechas del backend sin zona se guardan en UTC.
function toDate(value, assumeUtc) {
  if (value instanceof Date) return value;
  const text = String(value).trim().replace(" ", "T");
  if (HAS_OFFSET.test(text)) return new Date(text);
  return assumeUtc ? new Date(`${text}Z`) : null;
}

/**
 * Fecha y hora en hora de Ecuador: "AAAA-MM-DD HH:MM:SS" (o sin segundos).
 * - assumeUtc: true para fechas del backend sin zona guardadas en UTC.
 * - Una fecha sin hora (AAAA-MM-DD) se devuelve tal cual.
 */
export function formatDateTime(value, { seconds = true, assumeUtc = true, fallback = "—" } = {}) {
  if (value === null || value === undefined || value === "") return fallback;
  if (typeof value === "string" && DATE_ONLY.test(value.trim())) return value.trim();
  const date = toDate(value, assumeUtc);
  if (!date || Number.isNaN(date.getTime())) return String(value).replace("T", " ").slice(0, seconds ? 19 : 16);
  const p = ecuadorParts(date);
  return `${p.year}-${p.month}-${p.day} ${p.hour}:${p.minute}${seconds ? `:${p.second}` : ""}`;
}

// Momento actual en hora de Ecuador (para reportes y exportaciones).
export function nowEcuador({ seconds = true } = {}) {
  return formatDateTime(new Date(), { seconds });
}

// Fecha de hoy en Ecuador: "AAAA-MM-DD".
export function todayEcuador() {
  const p = ecuadorParts(new Date());
  return `${p.year}-${p.month}-${p.day}`;
}
