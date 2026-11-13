import { useCallback, useEffect, useState } from "react";
import { Bell } from "lucide-react";
import { getActiveCampaign, startCampaign, syncCampaign } from "../../../services/sox/control_7/campaignService";
import { readStoredUser, logout } from "../../../services/authSession";
import { useLocation } from "react-router-dom";
import ControlSelector from "./ControlSelector";
import controlConfig from "../../../constants/controlConfig";

export default function Navbar({ module }) {
  const [campaign, setCampaign] = useState(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [loadingCampaign, setLoadingCampaign] = useState(true);
  const [error, setError] = useState("");
  const location = useLocation();
  const match = location.pathname.match(/Control_(\d+)/);
  const control = controlConfig[match?.[1]];
  const isCampaignControl = Boolean(control?.hasCampaign);
  const user = readStoredUser();
  const canManageCampaign = ["administrador", "desarrollador"].includes(user?.rol);
  const name = user?.name || user?.username || "Usuario";
  const roleMap = { administrador: "Administrador", desarrollador: "Desarrollador", gerencial: "Gerente" };
  const role = roleMap[user?.rol] || user?.rol || "Usuario";
  const initials = name.split(" ").filter(Boolean).map((word) => word[0]).join("").slice(0, 2).toUpperCase();

  const loadCampaign = useCallback(async () => {
    try {
      const data = await getActiveCampaign();
      setCampaign(data);
      setError("");
    } catch (err) {
      setError(err.response?.data?.detail || "No se pudo consultar la campaña");
    } finally {
      setLoadingCampaign(false);
    }
  }, []);

  useEffect(() => {
    if (!isCampaignControl) return undefined;
    loadCampaign();
    const interval = setInterval(loadCampaign, 30000);
    return () => clearInterval(interval);
  }, [isCampaignControl, loadCampaign]);

  const handleCampaignAction = async (action) => {
    setActionLoading(true);
    setError("");
    try {
      const result = await action();
      await loadCampaign();
      // El backend responde success=false si, por ejemplo, falló la sincronización con Check Point.
      if (result && result.success === false) setError(result.message || "No se pudo completar la operación de campaña");
    } catch (err) {
      setError(err.response?.data?.detail || "No se pudo completar la operación de campaña");
    } finally {
      setActionLoading(false);
    }
  };

  return (
    <header className="flex min-h-20 flex-wrap items-center justify-between gap-4 border-b border-slate-200 bg-white px-6 py-3">
      <div className="flex flex-wrap items-center gap-4">
        {module === "SOX" && <div className="flex items-center gap-3"><span className="text-sm font-bold">Control activo:</span><ControlSelector /></div>}
        {isCampaignControl && <>
          <span className="text-sm font-bold">Campaña activa:</span>
          <div className="min-w-[220px] rounded-md border bg-white px-4 py-2">{loadingCampaign ? "Cargando campaña" : error ? "No disponible" : campaign?.name || "Sin campaña activa"}</div>
          {canManageCampaign && (campaign ?
            <button onClick={() => handleCampaignAction(syncCampaign)} disabled={actionLoading} className="rounded-md bg-blue-600 px-4 py-2 text-sm text-white disabled:opacity-60">{actionLoading ? "Actualizando..." : "Actualizar campaña"}</button> :
            <button onClick={() => handleCampaignAction(startCampaign)} disabled={actionLoading} className="rounded-md bg-green-600 px-4 py-2 text-sm text-white disabled:opacity-60">{actionLoading ? "Iniciando..." : "Iniciar campaña"}</button>
          )}
        </>}
        {error && <span role="alert" className="max-w-xs text-sm text-red-700">{String(error)}</span>}
        <Bell size={22} />
      </div>
      <div className="flex items-center gap-3">
        <div className="flex h-11 w-11 items-center justify-center rounded-full bg-blue-600 text-sm font-bold text-white">{initials}</div>
        <div><p className="text-sm font-bold">{name}</p><p className="text-xs text-slate-500">{role}</p></div>
        <button type="button" onClick={logout} className="rounded-md border border-slate-300 px-3 py-2 text-sm hover:bg-slate-100">Salir</button>
      </div>
    </header>
  );
}
