import axios from "axios";
import { getAccessToken, handleUnauthorized } from "./authSession";

// La configuración Nginx actual expone FastAPI bajo /api.
export const api = axios.create({
  baseURL: (import.meta.env.VITE_API_URL || "/api").replace(/\/+$/, ""),
  timeout: 60000,
});

api.interceptors.request.use((config) => {
  const token = getAccessToken();
  if (token && !config.headers.Authorization) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const isLogin = error.config?.url?.includes("/auth/login");
    if (!isLogin) {
      handleUnauthorized(error.response?.status, Boolean(getAccessToken()));
    }
    return Promise.reject(error);
  }
);
