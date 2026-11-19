import { useEffect, useMemo, useState } from "react";
import { RefreshCw, Search } from "lucide-react";
import StatusBadge from "../../../../components/SOX/control_7/StatusBadge";
import Pagination from "../../../../components/common/Pagination";
import { exportToExcel } from "../../../../utils/sox/control_7/exportExcel";
import { exportToPdf } from "../../../../utils/sox/control_7/exportPdf";
import { registerExport } from "../../../../utils/sox/control_7/registerExport";
import { formatDateTime } from "../../../../utils/dateTime";
import { errorText, getInternalCampaignRows, loadInternalFromLdap } from "../../../../services/sox/control_7/internalVpnService";
import { ACCESS_LABEL, DECISION_LABEL, INTERNAL_CAMPAIGN_COLUMNS, internalStatus } from "./internalShared";

const SELECT = "h-11 rounded-lg border border-slate-300 bg-white px-3 text-sm";

/** Campaña activa de VPN internas: mismo formato que "Validaciones de campaña activa" de VPN externas. */
export default function InternalCampaign() {
  const [data, setData] = useState({ campana: null, items: [] });
  const [search, setSearch] = useState("");
  const [manager, setManager] = useState("");
  const [status, setStatus] = useState("");
  const [decision, setDecision] = useState("");
  const [access, setAccess] = useState("");
  const [page, setPage] = useState(1);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const rowsPerPage = 80;

  const load = () => getInternalCampaignRows().then(setData).catch((e) => setMessage(errorText(e, "No se pudo cargar la campaña.")));
  useEffect(() => { load(); }, []);

  const expired = !!data.campana?.vencida;
  const managers = useMemo(() => [...new Set(data.items.map((i) => i.gerente).filter(Boolean))].sort(), [data.items]);
  const filtered = data.items.filter((item) => {
    const text = `${item.usuario} ${item.nombre} ${item.gerente} ${item.observacion}`.toLowerCase();
    return text.includes(search.toLowerCase())
      && (!manager || item.gerente === manager)
      && (!status || internalStatus(item, expired) === status)
      && (!decision || (item.confirmacion === 1 && item.estado === decision))
      && (!access || item.tipo_acceso === access);
  });
  const totalPages = Math.ceil(filtered.length / rowsPerPage);
  const rows = filtered.slice((page - 1) * rowsPerPage, page * rowsPerPage);
  const resetPage = (setter) => (e) => { setter(e.target.value); setPage(1); };

  async function reloadLdap() {
    if (!window.confirm("¿Volver a leer los grupos LDAP RDP y APLICACIONES? Las cuentas ya confirmadas conservan su decisión.")) return;
    setBusy(true); setMessage("");
    try {
      const r = await loadInternalFromLdap();
      setMessage(`LDAP leído: ${r.membresias} acceso(s), ${r.gerentes} gerente(s), ${r.sin_gerente} sin jefe en AD.`);
      load();
    } catch (e) { setMessage(errorText(e, "No se pudo leer LDAP.")); }
    finally { setBusy(false); }
  }

  return (
    <div>
      <h1 className="text-2xl font-bold">Campañas SOX · VPN internas</h1>
      <p className="mt-1 text-slate-500">{data.campana ? `${data.campana.nombre} · fecha límite ${formatDateTime(data.campana.fecha_limite, { seconds: false })}` : "Gestión de la campaña activa y sus validaciones."}</p>
      {message && <p className="mt-4 rounded-xl bg-blue-50 p-3 text-sm text-blue-800">{message}</p>}

      <div className="mt-6 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
          <h3 className="text-lg font-bold">Validaciones de campaña activa</h3>
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex h-11 w-80 items-center gap-2 rounded-lg border border-slate-300 bg-white px-3">
              <Search size={18} className="text-slate-500"/>
              <input value={search} onChange={resetPage(setSearch)} className="w-full border-none bg-transparent text-sm outline-none" placeholder="Buscar por cuenta, nombre o gerente..."/>
            </div>
            <button onClick={reloadLdap} disabled={busy || !data.campana} className="flex h-11 items-center gap-2 rounded-lg bg-slate-900 px-5 text-sm font-bold text-white hover:bg-slate-800 disabled:opacity-60">
              <RefreshCw size={16} className={busy ? "animate-spin" : ""}/>{busy ? "Leyendo LDAP..." : "Cargar desde LDAP"}</button>
            <button className="h-11 rounded-lg bg-green-600 px-5 text-sm font-bold text-white hover:bg-green-700" onClick={async () => {
              try {
                const n = await exportToExcel(filtered, "campana-vpn-internas-sox.xlsx", INTERNAL_CAMPAIGN_COLUMNS, "VPN internas");
                registerExport({ type: "Excel", module: "Campañas · VPN internas", description: "Validaciones de VPN internas", records: n });
              } catch { window.alert("No se pudo generar el archivo Excel."); }
            }}>Excel</button>
            <button className="h-11 rounded-lg bg-red-600 px-5 text-sm font-bold text-white hover:bg-red-700" onClick={() => {
              try {
                const n = exportToPdf(filtered, "campana-vpn-internas-sox.pdf", INTERNAL_CAMPAIGN_COLUMNS, "Validaciones de VPN internas - Control 7");
                registerExport({ type: "PDF", module: "Campañas · VPN internas", description: "Validaciones de VPN internas", records: n });
              } catch { window.alert("No se pudo generar el archivo PDF."); }
            }}>PDF</button>
          </div>
        </div>

        <div className="mb-5 grid grid-cols-1 gap-3 md:grid-cols-4">
          <select value={manager} onChange={resetPage(setManager)} className={SELECT}>
            <option value="">Todos los gerentes</option>{managers.map((m) => <option key={m} value={m}>{m}</option>)}
          </select>
          <select value={status} onChange={resetPage(setStatus)} className={SELECT}>
            <option value="">Todos los estados</option>{["Pendiente", "Confirmado", "Vencido", "Sin Responsable"].map((s) => <option key={s}>{s}</option>)}
          </select>
          <select value={decision} onChange={resetPage(setDecision)} className={SELECT}>
            <option value="">Todas las decisiones</option>{Object.entries(DECISION_LABEL).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
          <select value={access} onChange={resetPage(setAccess)} className={SELECT}>
            <option value="">Todos los accesos</option><option value="RDP">RDP</option><option value="APLICACIONES">Aplicaciones</option>
          </select>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full min-w-[1100px] border-collapse text-sm">
            <thead><tr className="bg-slate-50 text-left">
              {["Cuenta", "Nombre", "Acceso", "Gerente Asignado", "Estado", "Decisión", "Observación", "Confirmó", "Fecha Modificación"].map((h) => <th key={h} className="border-b p-4">{h}</th>)}
            </tr></thead>
            <tbody>{rows.map((item) => (
              <tr key={item.id}>
                <td className="border-b p-4 font-bold text-blue-700">{item.usuario}</td>
                <td className="border-b p-4">{item.nombre || "-"}{item.activo_ad === 0 && <p className="text-xs text-red-600">Deshabilitada en AD</p>}</td>
                <td className="border-b p-4">{ACCESS_LABEL[item.tipo_acceso]}</td>
                <td className="border-b p-4">{item.gerente || "-"}</td>
                <td className="border-b p-4"><StatusBadge status={internalStatus(item, expired)}/></td>
                <td className="border-b p-4">{item.confirmacion === 1 ? DECISION_LABEL[item.estado] : "-"}</td>
                <td className="border-b p-4">{item.observacion || "-"}</td>
                <td className="border-b p-4">{item.confirmado_por || "-"}</td>
                <td className="border-b p-4">{item.fecha_modificacion ? formatDateTime(item.fecha_modificacion, { seconds: false }) : "-"}</td>
              </tr>
            ))}</tbody>
          </table>
        </div>
        <Pagination currentPage={page} totalPages={totalPages} onPageChange={setPage}/>
        {filtered.length === 0 && <div className="p-8 text-center text-slate-500">No hay registros cargados para la campaña activa.</div>}
      </div>
    </div>
  );
}
