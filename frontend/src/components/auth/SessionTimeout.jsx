
import { useEffect } from "react";
import {
  getAccessToken,
  isSessionIdleExpired,
  expireSession,
  LAST_ACTIVITY_KEY,
} from "../../services/authSession";
import { api } from "../../services/api";

const SYNC_INTERVAL_MS = 30 * 1000;

export default function SessionTimeout() {
  useEffect(() => {
    let lastSync = 0;
    let pending = false;
    let closing = false;
    let active = true;

    function checkSession() {
      if (closing || !getAccessToken()) return;
      if (isSessionIdleExpired()) {
        closing = true;
        expireSession();
      }
    }

    async function registerActivity() {
      if (closing || !getAccessToken()) return;
      // Verificar ANTES de registrar actividad para impedir reanimar sesiones vencidas.
      if (isSessionIdleExpired()) {
        checkSession();
        return;
      }
      const now = Date.now();
      localStorage.setItem(LAST_ACTIVITY_KEY, String(now));
      if (pending || now - lastSync < SYNC_INTERVAL_MS) return;

      pending = true;
      lastSync = now;
      const tokenAtStart = getAccessToken();
      try {
        await api.post("/auth/actividad");
      } catch (error) {
        // No cerrar una sesión nueva por la respuesta tardía de una sesión antigua.
        if (active && tokenAtStart === getAccessToken() && error.response?.status === 401) {
          closing = true;
          expireSession();
        }
      } finally {
        pending = false;
      }
    }

    function onStorage(event) {
      if (event.key === "soxUser" || event.key === LAST_ACTIVITY_KEY) {
        if (!getAccessToken()) {
          if (window.location.pathname !== "/login") window.location.replace("/login");
        } else {
          checkSession();
        }
      }
    }

    const events = ["pointerdown", "keydown", "scroll", "touchstart"];
    for (const event of events) window.addEventListener(event, registerActivity, { passive: true });
    const interval = window.setInterval(checkSession, 1000);
    const onVisibility = () => {
      if (document.visibilityState === "visible") checkSession();
    };
    document.addEventListener("visibilitychange", onVisibility);
    window.addEventListener("storage", onStorage);
    checkSession();

    return () => {
      active = false;
      for (const event of events) window.removeEventListener(event, registerActivity);
      document.removeEventListener("visibilitychange", onVisibility);
      window.removeEventListener("storage", onStorage);
      window.clearInterval(interval);
    };
  }, []);
  return null;
}
