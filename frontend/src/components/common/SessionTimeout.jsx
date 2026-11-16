import { useEffect } from "react";
import { api } from "../../services/api";
import {
  LAST_ACTIVITY_KEY,
  expireSession,
  getAccessToken,
  isSessionIdleExpired,
  isTokenExpired,
  markActivity,
} from "../../services/authSession";

// Cada cuánto se avisa al backend que el usuario sigue activo (como máximo).
const SYNC_INTERVAL_MS = 30 * 1000;
// Evita escribir en localStorage en cada movimiento del mouse.
const MARK_INTERVAL_MS = 5 * 1000;
const ACTIVITY_EVENTS = ["pointerdown", "pointermove", "keydown", "wheel", "scroll", "touchstart"];

/**
 * Sesión por inactividad.
 *  - 15 minutos SIN interacción (mouse, teclado, scroll, toque) -> cierra sesión.
 *  - Mientras el usuario interactúa, renueva la sesión en Oracle (POST /auth/actividad).
 *  - Límite absoluto: el JWT vence 8 horas después del login (JWT_EXPIRE_MINUTES) aunque
 *    haya actividad.
 *  - Las consultas automáticas (p. ej. la Navbar cada 30 s) NO cuentan como actividad.
 */
export default function SessionTimeout() {
  useEffect(() => {
    let lastSync = 0;
    let lastMark = 0;
    let pending = false;
    let closing = false;
    let active = true;

    function close() {
      if (closing) return;
      closing = true;
      expireSession();
    }

    function checkSession() {
      if (closing || !getAccessToken()) return;
      if (isSessionIdleExpired() || isTokenExpired()) close();
    }

    async function registerActivity() {
      if (closing || !getAccessToken()) return;
      // Verificar ANTES de registrar actividad para no reanimar una sesión vencida.
      if (isSessionIdleExpired() || isTokenExpired()) {
        close();
        return;
      }
      const now = Date.now();
      if (now - lastMark >= MARK_INTERVAL_MS) {
        lastMark = now;
        markActivity(now);
      }
      if (pending || now - lastSync < SYNC_INTERVAL_MS) return;

      pending = true;
      lastSync = now;
      const tokenAtStart = getAccessToken();
      try {
        await api.post("/auth/actividad");
      } catch (error) {
        // No cerrar una sesión nueva por la respuesta tardía de una sesión anterior.
        if (active && tokenAtStart === getAccessToken() && error.response?.status === 401) close();
      } finally {
        pending = false;
      }
    }

    function onStorage(event) {
      if (event.key !== "soxUser" && event.key !== LAST_ACTIVITY_KEY) return;
      if (!getAccessToken()) {
        if (window.location.pathname !== "/login") window.location.replace("/login");
      } else {
        checkSession();
      }
    }

    function onVisibility() {
      if (document.visibilityState === "visible") checkSession();
    }

    for (const event of ACTIVITY_EVENTS) window.addEventListener(event, registerActivity, { passive: true });
    document.addEventListener("visibilitychange", onVisibility);
    window.addEventListener("storage", onStorage);
    const interval = window.setInterval(checkSession, 5000);
    checkSession();

    return () => {
      active = false;
      for (const event of ACTIVITY_EVENTS) window.removeEventListener(event, registerActivity);
      document.removeEventListener("visibilitychange", onVisibility);
      window.removeEventListener("storage", onStorage);
      window.clearInterval(interval);
    };
  }, []);

  return null;
}
