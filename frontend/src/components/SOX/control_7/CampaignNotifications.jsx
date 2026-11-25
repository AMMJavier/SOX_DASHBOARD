import { useCallback, useEffect, useState } from "react";
import { Mail, RefreshCw, Search, Send } from "lucide-react";
import { readStoredUser } from "../../../services/authSession";
import { getCampaignNotifications, sendCampaignNotifications } from "../../../services/sox/control_7/campaignService";
import { formatDateTime } from "../../../utils/dateTime";
import Pagination from "../../common/Pagination";
import ConfirmModal from "../../common/ConfirmModal";

const CONTACT = {
  LISTO: { label: "Correo encontrado", className: "text-emerald-700" },
  SIN_CONTACTO: { label: "Sin correo registrado", className: "text-red-700" },
  AMBIGUO: { label: "Varios correos posibles", className: "text-amber-700" },
  DOMINIO_NO_PERMITIDO: { label: "Dominio no autorizado", className: "text-red-700" },
};
const NOTIFICATION = {
  ACEPTADO: { label: "Notificado", className: "text-emerald-700" },
  PENDIENTE: { label: "Sin confirmar (revisar buzón)", className: "text-amber-700" },
  FALLIDO: { label: "Fallido", className: "text-red-700" },
};
// Gerentes por página en "Ver detalles gerentes - envío individual".
const PAGE_SIZE = 10;
const plain = (v) => String(v || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
const errorText = (e) => e?.response?.data?.detail || e?.message || "Error inesperado";

function Kpi({ label, value, tone = "text-slate-900" }) {
  return <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
    <p className="text-xs font-semibold text-slate-500">{label}</p>
    <p className={`mt-1 text-2xl font-bold ${tone}`}>{value ?? "—"}</p>
  </div>;
}

/**
 * Aviso individual a los gerentes de la campaña activa (solo administración SOX).
 * Por defecto: VPN externas. VPN internas pasa sus propias funciones y textos.
 */
export default function CampaignNotifications({
  fetchData = getCampaignNotifications,
  sendData = sendCampaignNotifications,
  description = "Aviso individual de apertura a cada gerente con VPN en la campaña activa. El correo no reemplaza la validación en el portal.",
  itemLabel = "VPN",
  refreshKey = 0, // al cambiar, vuelve a leer (p. ej. tras asignar un gerente a mano)
}) {
  const isAdmin = readStoredUser()?.rol === "administrador";
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState(null);
  const [open, setOpen] = useState(false);
  const [page, setPage] = useState(1);
  const [managerFilter, setManagerFilter] = useState("");
  const [managerText, setManagerText] = useState("");
  // Envío pendiente de confirmar: null = todos los pendientes, [clave] = un gerente.
  const [confirmSend, setConfirmSend] = useState(undefined);

  const load = useCallback(async () => {
    setLoading(true);
    try { setData(await fetchData()); }
    catch (e) { setMessage({ error: true, text: errorText(e) }); }
    finally { setLoading(false); }
  }, [fetchData]);

  useEffect(() => { if (isAdmin) load(); }, [isAdmin, load, refreshKey]);
  // Mientras hay un envío en segundo plano, refrescar el avance cada 5 segundos.
  useEffect(() => {
    if (!data?.en_proceso) return undefined;
    const timer = setInterval(load, 5000);
    return () => clearInterval(timer);
  }, [data?.en_proceso, load]);

  if (!isAdmin) return null;
  if (data && !data.campana) return null;

  const summary = data?.resumen;
  const pending = (data?.gerentes || []).filter((x) => x.enviable);
  // Filtros del detalle: lista de gerentes y/o texto (nombre o correo, sin importar acentos).
  // Si el gerente elegido ya no está tras actualizar, la lista no filtra.
  const all = data?.gerentes || [];
  const byList = all.some((g) => g.clave === managerFilter) ? all.filter((g) => g.clave === managerFilter) : all;
  const words = plain(managerText).split(/\s+/).filter(Boolean);
  const shownManagers = byList.filter((g) => words.every((w) => plain(`${g.gerente} ${g.correo || ""}`).includes(w)));

  async function send(claves = null) {
    setConfirmSend(undefined);
    setMessage(null);
    try {
      const result = await sendData(claves);
      setMessage({ error: false, text: `${result.en_cola} aviso(s) en envío. ${result.mensaje}` });
    } catch (e) { setMessage({ error: true, text: errorText(e) }); }
    finally { load(); }
  }

  return (
    <div className="mt-6 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="flex items-center gap-2 text-lg font-bold"><Mail size={20} className="text-blue-600"/>Notificación a gerentes</h3>
          <p className="mt-1 text-sm text-slate-500">{description}</p>
        </div>
        <div className="flex flex-wrap gap-3">
          <button type="button" onClick={load} disabled={loading} className="flex h-11 items-center gap-2 rounded-lg border border-slate-300 px-4 text-sm font-semibold text-slate-700 hover:bg-slate-50">
            <RefreshCw size={16} className={loading ? "animate-spin" : ""}/>Actualizar
          </button>
          <button type="button" onClick={() => setConfirmSend(null)} disabled={!data?.envio_habilitado || data?.en_proceso || pending.length === 0}
            className="flex h-11 items-center gap-2 rounded-lg bg-blue-600 px-5 text-sm font-bold text-white hover:bg-blue-700 disabled:opacity-50">
            <Send size={16}/>{data?.en_proceso ? "Enviando..." : `Notificar pendientes (${pending.length})`}
          </button>
        </div>
      </div>

      {data?.modo_prueba && <p className="mb-4 rounded-lg border border-violet-200 bg-violet-50 p-3 text-sm text-violet-800"><strong>Modo prueba:</strong> los avisos no se envían a los gerentes ni se usan los correos de Oracle. Cada aviso llega a {data.correos_prueba.join(", ")} con asunto [PRUEBA] e indica a qué gerente correspondía. Se cambia en backend/config/correos.json (controles.7.aviso_gerentes.modo_prueba).</p>}
      {data?.copias?.length > 0 && <p className="mb-4 rounded-lg bg-slate-50 p-3 text-sm text-slate-700"><strong>Copia automática:</strong> {data.copias.join(", ")}</p>}
      {data && !data.envio_habilitado && <p className="mb-4 rounded-lg bg-amber-50 p-3 text-sm text-amber-800">El envío está desactivado en el servidor (SOX_MAIL_ENABLED). La vista previa sí está disponible.</p>}
      {message && <p className={`mb-4 rounded-lg p-3 text-sm ${message.error ? "bg-red-50 text-red-700" : "bg-blue-50 text-blue-800"}`}>{message.text}</p>}

      {summary && <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-7">
        <Kpi label="Gerentes en campaña" value={summary.gerentes}/>
        <Kpi label="Notificados" value={summary.notificados} tone="text-emerald-700"/>
        <Kpi label="Listos para enviar" value={summary.listos} tone="text-blue-700"/>
        <Kpi label="Sin confirmar / fallidos" value={`${summary.sin_confirmar} / ${summary.fallidos}`} tone="text-amber-700"/>
        <Kpi label="Sin correo / ambiguos" value={`${summary.sin_contacto} / ${summary.ambiguos}`} tone="text-red-700"/>
        <Kpi label="Dominio no permitido" value={summary.dominio_no_permitido} tone="text-red-700"/>
        <Kpi label="Registros sin gerente" value={`${summary.registros_sin_gerente} de ${summary.registros}`} tone={summary.registros_sin_gerente ? "text-red-700" : "text-slate-900"}/>
      </div>}

      {data?.gerentes?.length > 0 && <div className="mt-4">
        <button type="button" onClick={() => setOpen((v) => !v)} className="text-sm font-semibold text-blue-700 hover:underline">
          {open ? "Ocultar detalles gerentes - envío individual" : "Ver detalles gerentes - envío individual"}
        </button>
        {open && <div className="mt-3 flex flex-wrap items-center gap-3">
          <select value={managerFilter} onChange={(e) => { setManagerFilter(e.target.value); setPage(1); }}
            aria-label="Elegir gerente" className="h-11 w-full max-w-md rounded-lg border border-slate-300 bg-white px-3 text-sm">
            <option value="">Todos los gerentes ({data.gerentes.length})</option>
            {[...data.gerentes].sort((a, b) => String(a.gerente).localeCompare(String(b.gerente)))
              .map((g) => <option key={g.clave} value={g.clave}>{g.gerente}</option>)}
          </select>
          <div className="flex h-11 w-full max-w-md items-center gap-2 rounded-lg border border-slate-300 bg-white px-3">
            <Search size={16} className="shrink-0 text-slate-500"/>
            <input value={managerText} onChange={(e) => { setManagerText(e.target.value); setPage(1); }}
              aria-label="Buscar gerente por nombre o correo" placeholder="Escribe el nombre o correo del gerente..."
              className="w-full border-none bg-transparent text-sm outline-none"/>
          </div>
          {(managerFilter || managerText) && <>
            <span className="text-sm text-slate-500">{shownManagers.length} de {data.gerentes.length}</span>
            <button type="button" onClick={() => { setManagerFilter(""); setManagerText(""); setPage(1); }}
              className="text-sm font-semibold text-blue-700 hover:underline">Limpiar</button>
          </>}
        </div>}
        {open && <div className="mt-3 overflow-x-auto"><table className="w-full border-collapse text-sm">
          <thead><tr className="bg-slate-50 text-left">
            <th className="border-b p-3">Gerente</th><th className="border-b p-3">{itemLabel} (pendientes)</th><th className="border-b p-3">Correo</th>
            <th className="border-b p-3">Contacto</th><th className="border-b p-3">Aviso</th><th className="border-b p-3">Acción</th>
          </tr></thead>
          <tbody>{shownManagers.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE).map((g) => {
            const contact = CONTACT[g.contacto] || { label: g.contacto, className: "" };
            const notice = NOTIFICATION[g.notificacion];
            return <tr key={g.clave}>
              <td className="border-b p-3 font-semibold">{g.gerente}</td>
              <td className="border-b p-3">{g.vpn} ({g.pendientes})</td>
              <td className="border-b p-3">{g.correo || "-"}</td>
              <td className={`border-b p-3 font-semibold ${contact.className}`}>{contact.label}</td>
              <td className="border-b p-3">{notice ? <span className={`font-semibold ${notice.className}`}>{notice.label}</span> : "No enviado"}
                {g.fecha_envio && <p className="text-xs text-slate-500">{formatDateTime(g.fecha_envio, { seconds: false })}</p>}
                {g.detalle && <p className="text-xs text-slate-500">{g.detalle}</p>}
                {g.intentos > 1 && <p className="text-xs text-slate-500">{g.intentos} intentos</p>}</td>
              <td className="border-b p-3">{g.enviable && <button type="button" disabled={!data.envio_habilitado || data.en_proceso}
                onClick={() => setConfirmSend([g.clave])} className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-semibold hover:bg-slate-50 disabled:opacity-50">
                {g.notificacion === "FALLIDO" ? "Reintentar" : "Enviar"}</button>}</td>
            </tr>;
          })}
          {shownManagers.length === 0 && <tr><td colSpan={6} className="p-6 text-center text-slate-500">Ningún gerente coincide con la búsqueda.</td></tr>}</tbody>
        </table>
          <Pagination currentPage={page} totalPages={Math.ceil(shownManagers.length / PAGE_SIZE)} onPageChange={setPage}/>
        </div>}
      </div>}

      {confirmSend !== undefined && <ConfirmModal title="¿Está seguro de que quiere enviar las notificaciones a los gerentes?" icon={Send}
        confirmLabel="Sí, enviar" onClose={() => setConfirmSend(undefined)} onConfirm={() => send(confirmSend)}>
        <p>Se enviará un correo {data?.modo_prueba ? "de prueba" : <b>REAL</b>} a{" "}
          <b>{confirmSend ? (all.find((g) => g.clave === confirmSend[0])?.gerente || "1 gerente") : `${pending.length} gerente(s)`}</b> de la
          campaña <b>{data?.campana?.nombre}</b> con su cantidad de {itemLabel} y la fecha límite.</p>
        <p>Los gerentes ya notificados no recibirán otro aviso.</p>
        {data?.modo_prueba && <p className="rounded-lg bg-violet-50 p-3 font-semibold text-violet-800">Modo prueba: los correos llegan a {data.correos_prueba?.join(", ")}, no a los gerentes.</p>}
      </ConfirmModal>}
    </div>
  );
}
