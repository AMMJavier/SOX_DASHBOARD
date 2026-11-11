import { api } from "./api";

export async function getUserPermissions() {
  const { data } = await api.get("/usuarios/permisos");
  return data;
}

export async function listUsers() {
  const { data } = await api.get("/usuarios");
  return data;
}

export async function createUser(payload) {
  const { data } = await api.post("/usuarios", payload);
  return data;
}

export async function setUserActive(id, activo) {
  const { data } = await api.patch(`/usuarios/${id}/estado`, { activo });
  return data;
}

export async function deleteUser(id) {
  await api.delete(`/usuarios/${id}`);
}

export async function resetUserPassword(id, password_nueva) {
  await api.patch(`/usuarios/${id}/contrasena`, { password_nueva });
}

export function userApiError(error) {
  const detail = error?.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((item) => item.msg || "Dato inválido").join("; ");
  return error.message || "Error al conectar con el servidor";
}
