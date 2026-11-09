import { api } from "../../api";

export async function getHistory(filters = {}) {
  const response = await api.get("/sox/history", {
    params: filters,
  });

  return response.data;
}

export async function getHistoryFilters() {
  const response = await api.get("/sox/history/filters");
  return response.data;
}

export function registerExport({ type, module, description, records, filters }) {
  const saved = JSON.parse(localStorage.getItem("exportsHistory")) || [];
  const user = JSON.parse(localStorage.getItem("soxUser"));

  const newExport = {
    id: Date.now(),
    type,
    module,
    description,
    records,
    filters,
    user: user?.name || "Usuario",
    date: new Date().toLocaleString(),
  };

  const updated = [newExport, ...saved];
  localStorage.setItem("exportsHistory", JSON.stringify(updated));
}