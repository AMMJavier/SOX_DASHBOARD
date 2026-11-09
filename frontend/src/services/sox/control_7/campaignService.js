import { api } from "../../api";


export async function getCampaignValidations(){
    const response = await api.get(
        "/sox/campaign/validations"
    );
    return response.data.data || [];
}

export async function getActiveCampaign(){
    const response = await api.get(
        "/sox/campaign/active"
    );
    const data = response.data;
    if (!data.nombre_campana) {
        return null;
    }
    return {
        id: data.id_campana,
        name: data.nombre_campana
            .replace("CONTROL 7 -",""),
        period:
            `${data.fecha_inicio} - ${data.fecha_fin}`
    };
}
export async function startCampaign(){
    const response = await api.post(
        "/sox/campaign/start"
    );
    return response.data;
}

export async function syncCampaign(){
    const response = await api.post(
        "/sox/campaign/sync"
    );
    return response.data;
}

export async function getCampaignStatus(){
    const response =
        await api.get("/sox/campaign/status");
    return response.data;
}

export async function getCampaignNotifications() {
  const response = await api.get("/sox/campaign/notifications");
  return response.data;
}

export async function sendCampaignNotifications(claves = null) {
  const response = await api.post("/sox/campaign/notifications/send", { confirmar: true, claves });
  return response.data;
}

export async function closeActiveCampaign(data) {
  const response = await api.post("/sox/campaign/close", data);
  return response.data;
}