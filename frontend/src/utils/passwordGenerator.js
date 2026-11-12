/*
 * Generador de claves seguras para usuarios locales.
 * Misma regla que el proyecto "claves" (generar_clave.py / generador.js):
 * 8–12 caracteres, al menos una minúscula, una mayúscula, un número y un símbolo,
 * mezcla final con aleatoriedad criptográfica (crypto.getRandomValues).
 * Se ejecuta solo en el navegador: la clave no viaja hasta que el admin guarda.
 */

export const LONGITUD_MINIMA = 8;
export const LONGITUD_MAXIMA = 12;

const MINUSCULAS = "abcdefghijklmnopqrstuvwxyz";
const MAYUSCULAS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ";
const DIGITOS = "0123456789";
const SIMBOLOS = "!@#$%&*-_=+?";
const GRUPOS = [MINUSCULAS, MAYUSCULAS, DIGITOS, SIMBOLOS];
const TODOS = GRUPOS.join("");

/** Entero uniforme en [0, max) sin sesgo de módulo (muestreo por rechazo). */
function randomInt(max) {
  const limite = Math.floor(0x100000000 / max) * max;
  const buffer = new Uint32Array(1);
  let valor;
  do {
    window.crypto.getRandomValues(buffer);
    valor = buffer[0];
  } while (valor >= limite);
  return valor % max;
}

const elegir = (texto) => texto[randomInt(texto.length)];

export function generarClave(longitud = LONGITUD_MAXIMA) {
  if (!Number.isInteger(longitud) || longitud < LONGITUD_MINIMA || longitud > LONGITUD_MAXIMA) {
    throw new Error(`La longitud debe estar entre ${LONGITUD_MINIMA} y ${LONGITUD_MAXIMA} caracteres.`);
  }
  const caracteres = GRUPOS.map(elegir);
  while (caracteres.length < longitud) caracteres.push(elegir(TODOS));
  // Fisher-Yates con aleatoriedad segura.
  for (let i = caracteres.length - 1; i > 0; i--) {
    const j = randomInt(i + 1);
    [caracteres[i], caracteres[j]] = [caracteres[j], caracteres[i]];
  }
  return caracteres.join("");
}

/** Fortaleza estimada en bits (alfabeto de 74 caracteres). */
export function fortaleza(longitud) {
  const bits = Math.round(longitud * Math.log2(TODOS.length));
  if (bits >= 72) return { bits, nivel: 4, texto: "Muy fuerte" };
  if (bits >= 60) return { bits, nivel: 3, texto: "Fuerte" };
  if (bits >= 45) return { bits, nivel: 2, texto: "Aceptable" };
  return { bits, nivel: 1, texto: "Débil" };
}

/**
 * Copia al portapapeles. navigator.clipboard solo existe en HTTPS o localhost;
 * el servidor se usa por http://IP, así que se usa execCommand como respaldo.
 */
export async function copiarTexto(texto) {
  if (window.isSecureContext && navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(texto);
    return;
  }
  const area = document.createElement("textarea");
  area.value = texto;
  area.setAttribute("readonly", "");
  area.style.position = "fixed";
  area.style.opacity = "0";
  document.body.appendChild(area);
  area.select();
  const ok = document.execCommand("copy");
  document.body.removeChild(area);
  if (!ok) throw new Error("No se pudo copiar al portapapeles.");
}
