import { api } from "../../api";

export async function getManagers() {
  const response = await api.get("/sox/managers");
  return response.data;
}

