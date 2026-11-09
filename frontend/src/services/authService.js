import { api } from "./api";

export async function loginUser(username, password) {
  const response = await api.post("/auth/login", { username, password });
  return response.data;
}

export async function getCurrentUser(token) {
  // El primer /auth/me se realiza antes de persistir la sesión recién creada.
  const response = await api.get("/auth/me", token ? {
    headers: { Authorization: `Bearer ${token}` },
  } : undefined);
  return response.data;
}
