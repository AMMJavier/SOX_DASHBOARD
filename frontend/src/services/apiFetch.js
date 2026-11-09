import { getAccessToken, handleUnauthorized } from "./authSession";

export const API_BASE_URL = (import.meta.env.VITE_API_URL || "/api").replace(/\/+$/, "");

/** Fetch protegido para Assets. Preserva FormData sin forzar Content-Type. */
export async function authenticatedFetch(url, options = {}) {
  const token = getAccessToken();
  const headers = new Headers(options.headers || {});
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(url, { ...options, headers });
  handleUnauthorized(response.status, Boolean(token));
  return response;
}
