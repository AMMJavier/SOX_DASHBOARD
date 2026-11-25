import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, Archive, Bell, Play, RefreshCw, X } from "lucide-react";
import { closeActiveCampaign, getActiveCampaign, startCampaign, syncCampaign } from "../../../services/sox/control_7/campaignService";
import { readStoredUser, logout } from "../../../services/authSession";
import { useLocation } from "react-router-dom";
import ControlSelector from "./ControlSelector";
import controlConfig from "../../../constants/controlConfig";
import ConfirmModal from "../../common/ConfirmModal";

export default function Navbar({ module }) {
  const [campaign, setCampaign] = useState(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [loadingCampaign, setLoadingCampaign] = useState(true);
  const [error, setError] = useState("");
  const [confirmSync, setConfirmSync] = useState(false);
  // "start" | "close": ventana de confirmación de Iniciar / Cerrar campaña.
  const [confirmAction, setConfirmAction] = useState(null);
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

  const handleCampaignAction = async (action, reload = false) => {
    setActionLoading(true);
    setError("");
    try {
      const result = await action();
      await loadCampaign();
      // El backend responde success=false si, por ejemplo, falló la sincronización con Check Point.
      if (result && result.success === false) setError(result.message || "No se pudo completar la operación de campaña");
      // Iniciar / cerrar cambian los datos de toda la página (externas e internas): se recarga.
      else if (reload) window.location.reload();
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
            <>
              <button onClick={() => setConfirmSync(true)} disabled={actionLoading} className="rounded-md bg-blue-600 px-4 py-2 text-sm text-white disabled:opacity-60">{actionLoading ? "Procesando..." : "Actualizar campaña"}</button>
              <button onClick={() => setConfirmAction("close")} disabled={actionLoading} className="rounded-md bg-slate-900 px-4 py-2 text-sm text-white hover:bg-slate-800 disabled:opacity-60">Cerrar campaña</button>
            </> :
            <button onClick={() => setConfirmAction("start")} disabled={actionLoading || loadingCampaign} className="rounded-md bg-green-600 px-4 py-2 text-sm text-white disabled:opacity-60">{actionLoading ? "Iniciando..." : "Iniciar campaña"}</button>
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
      {confirmSync && <SyncCampaignModal name={campaign?.name} onClose={() => setConfirmSync(false)}
        onConfirm={() => { setConfirmSync(false); handleCampaignAction(syncCampaign); }}/>}
      {confirmAction === "start" && <ConfirmModal title="¿Está seguro de iniciar una nueva campaña?" icon={Play} tone="green"
        confirmLabel="Sí, iniciar campaña" onClose={() => setConfirmAction(null)}
        onConfirm={() => { setConfirmAction(null); handleCampaignAction(startCampaign, true); }}>
        <p>Se creará la campaña del semestre actual y se cargarán las VPN externas (Check Point) y las VPN internas (LDAP).</p>
        <p className="rounded-lg bg-blue-50 p-3 font-semibold text-blue-800">No se enviará ningún correo a los gerentes. Los avisos se envían
          después, desde Campañas con el botón "Notificar pendientes".</p>
      </ConfirmModal>}
      {confirmAction === "close" && <ConfirmModal title="¿Está seguro de cerrar la campaña activa?" icon={Archive} tone="slate"
        confirmLabel="Sí, cerrar campaña" onClose={() => setConfirmAction(null)}
        onConfirm={() => { setConfirmAction(null); handleCampaignAction(closeActiveCampaign, true); }}>
        <p>La campaña <b>{campaign?.name || "activa"}</b> se cerrará y sus registros pasarán al histórico.</p>
        <p className="rounded-lg bg-amber-50 p-3 font-semibold text-amber-800">Esta acción no se puede deshacer.</p>
      </ConfirmModal>}
    </header>
  );
}

/** Advertencia antes de "Actualizar campaña": vuelve a leer Check Point sobre la campaña activa. */
function SyncCampaignModal({ name, onClose, onConfirm }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4" role="dialog" aria-modal="true" aria-label="Actualizar campaña">
      <div className="w-full max-w-lg rounded-2xl bg-white p-6 shadow-xl">
        <div className="mb-4 flex items-start justify-between gap-4">
          <h3 className="flex items-center gap-2 text-lg font-bold"><AlertTriangle size={20} className="text-amber-500"/>¿Realmente desea actualizar la campaña?</h3>
          <button type="button" onClick={onClose} className="rounded-lg p-1 text-slate-500 hover:bg-slate-100" aria-label="Cerrar"><X size={20}/></button>
        </div>
        <div className="space-y-3 text-sm text-slate-700">
          <p>Se volverán a leer las VPN de Check Point para la campaña <b>{name || "activa"}</b>.</p>
          <ul className="list-disc space-y-1 pl-5">
            <li>Pueden aparecer VPN nuevas y cambiar el gerente de las que aún están pendientes.</li>
            <li>Las VPN ya confirmadas (Mantener / Eliminar), la Fecha VPN y la Fecha Vencimiento <b>no cambian</b>.</li>
          </ul>
          <p className="rounded-lg bg-amber-50 p-3 font-semibold text-amber-800">Esta acción no se puede deshacer.</p>
        </div>
        <div className="mt-6 flex justify-end gap-3">
          <button type="button" onClick={onClose} className="h-11 rounded-lg border border-slate-300 px-5 text-sm font-bold">Cancelar</button>
          <button type="button" onClick={onConfirm} className="flex h-11 items-center gap-2 rounded-lg bg-blue-600 px-5 text-sm font-bold text-white hover:bg-blue-700">
            <RefreshCw size={16}/>Sí, actualizar campaña</button>
        </div>
      </div>
    </div>
  );
}
