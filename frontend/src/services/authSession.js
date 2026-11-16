
const USER_KEY = "soxUser";
export const LAST_ACTIVITY_KEY = "soxLastActivity";

// Debe coincidir con SESSION_TIMEOUT_MINUTES del backend (auth/session_service.py).
export const IDLE_TIMEOUT_MS = 15 * 60 * 1000;

const API_BASE_URL = (
  import.meta.env.VITE_API_URL || "/api"
).replace(/\/+$/, "");

// Leer el usuario y su token almacenado.
export function readStoredUser() {
  try {
    const parsed = JSON.parse(
      localStorage.getItem(USER_KEY) || "null"
    );

    return parsed && typeof parsed === "object"
      ? parsed
      : null;
  } catch {
    return null;
  }
}

// Obtener el token JWT.
export function getAccessToken() {
  const token = readStoredUser()?.token;

  return typeof token === "string" && token.trim()
    ? token
    : null;
}

// Guardar una sesión nueva después del login.
export function saveSession(token, profile) {
  if (!token || !profile?.username || !profile?.rol) {
    throw new Error(
      "Respuesta de autenticación incompleta"
    );
  }

  const user = {
    username: profile.username,
    name: profile.username,
    rol: profile.rol,
    auth_provider: profile.auth_provider,
    modulos: profile.modulos || [],
    token,
  };

  localStorage.setItem(
    USER_KEY,
    JSON.stringify(user)
  );

  // Cada nuevo login comienza con su propio contador.
  localStorage.setItem(
    LAST_ACTIVITY_KEY,
    String(Date.now())
  );

  return user;
}

// Actualizar el perfil sin reiniciar el contador.
export function updateSessionProfile(profile) {
  const token = getAccessToken();

  if (!token) return null;

  const user = readStoredUser();

  if (!user) return null;

  if (!profile?.username || !profile?.rol) {
    throw new Error("Perfil de usuario incompleto");
  }

  const updatedUser = {
    ...user,
    username: profile.username,
    name: profile.username,
    rol: profile.rol,
    auth_provider: profile.auth_provider,
    modulos: profile.modulos || [],
  };

  localStorage.setItem(
    USER_KEY,
    JSON.stringify(updatedUser)
  );

  return updatedUser;
}

// Eliminar la sesión del navegador.
export function clearSession() {
  localStorage.removeItem(USER_KEY);
  localStorage.removeItem(LAST_ACTIVITY_KEY);
}

// Revocar la sesión en el backend.
export async function revokeRemoteSession(token) {
  if (!token) return false;

  try {
    const response = await fetch(
      `${API_BASE_URL}/auth/logout`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
        },
        cache: "no-store",
      }
    );

    return response.ok;
  } catch {
    return false;
  }
}

// Cerrar sesión manualmente.
export async function logout() {
  const token = getAccessToken();

  // Impedir acceso local inmediatamente.
  clearSession();

  try {
    await revokeRemoteSession(token);
  } finally {
    window.location.replace("/login");
  }
}

// Última interacción del usuario (compartida entre pestañas).
export function readLastActivity() {
  const value = Number(localStorage.getItem(LAST_ACTIVITY_KEY));
  return Number.isFinite(value) && value > 0 ? value : null;
}

export function markActivity(now = Date.now()) {
  localStorage.setItem(LAST_ACTIVITY_KEY, String(now));
}

// true si pasaron 15 minutos sin interacción.
export function isSessionIdleExpired(now = Date.now()) {
  const last = readLastActivity();
  if (last === null) {
    // Sesión guardada sin marca: se empieza a contar desde ahora.
    markActivity(now);
    return false;
  }
  return now - last >= IDLE_TIMEOUT_MS;
}

// true si el JWT superó su vencimiento absoluto (8 horas desde el login).
export function isTokenExpired(now = Date.now()) {
  const token = getAccessToken();
  if (!token) return false;
  try {
    const part = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    const payload = JSON.parse(atob(part));
    return typeof payload.exp === "number" && now >= payload.exp * 1000;
  } catch {
    return false;
  }
}

// Cerrar la sesión por inactividad o vencimiento.
export function expireSession() {
  const token = getAccessToken();
  clearSession();
  revokeRemoteSession(token).finally(() => {
    if (window.location.pathname !== "/login") {
      window.location.replace("/login?expired=1");
    }
  });
}

// Gestionar tokens inválidos o sesiones vencidas.
export function handleUnauthorized(
  responseStatus,
  hadToken
) {
  // 401: sesión inválida o vencida.
  // 403: usuario autenticado sin permisos.
  if (responseStatus === 401 && hadToken) {
    clearSession();

    if (window.location.pathname !== "/login") {
      window.location.replace(
        "/login?expired=1"
      );
    }
  }
}
