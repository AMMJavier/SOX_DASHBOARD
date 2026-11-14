import { api } from "../../api";

/** Gerentes (nombre de Check Point) vinculados al usuario en sesión vía SOX_GERENTES_CONTACTO.LDAP_CN. */
export async function getMyManagers() {
  const response = await api.get("/sox/managers/mine");
  return response.data?.gerentes || [];
}

export async function getManagers() {
  const response = await api.get("/sox/managers");
  return response.data;
}

