import { api } from "../../api";

export async function getAllValidations() {
  const response = await api.get("/sox/validations");
  return response.data;
}


export async function getValidationsByManager(managerName) {
  const response = await api.get(
    `/sox/validations/manager/${encodeURIComponent(managerName)}`
  );
  return response.data;
}

export async function updateValidation(checkpointUid, data){
  const response = await api.patch(
    `/sox/validations/${checkpointUid}`,
    data
  );
  return response.data;
}

export async function confirmAllValidations(data){
  const response = await api.patch(
    "/sox/validations/confirm-all",
    data
  );
  return response.data;
}