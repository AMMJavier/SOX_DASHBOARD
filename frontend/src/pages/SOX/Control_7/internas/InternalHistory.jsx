import { useEffect, useState } from "react";
import { Search } from "lucide-react";
import StatusBadge from "../../../../components/SOX/control_7/StatusBadge";
import Pagination from "../../../../components/common/Pagination";
import { exportToExcel } from "../../../../utils/sox/control_7/exportExcel";
import { exportToPdf } from "../../../../utils/sox/control_7/exportPdf";
import { registerExport } from "../../../../utils/sox/control_7/registerExport";
import { formatDateTime } from "../../../../utils/dateTime";
import { errorText, getInternalHistory, getInternalHistoryFilters } from "../../../../services/sox/control_7/internalVpnService";
import { ACCESS_LABEL, DECISION_LABEL, INTERNAL_HISTORY_COLUMNS } from "./internalShared";

const SELECT = "h-11 rounded-lg border border-slate-300 bg-white px-3 text-sm";

// En el histórico una cuenta no confirmada de una campaña ya vencida o cerrada cuenta como Vencido.
function historyStatus(item) {
  if (!item.gerente) return "Sin Responsable";
  if (item.confirmacion === 1) return "Confirmado";
  const late = item.campaign_status === "CERRADA" || (item.deadline && new Date(item.deadline) < new Date());
  return late ? "Vencido" : "Pendiente";
}

/** Histórico de VPN internas: mismo formato que el Histórico SOX de VPN externas. */
export default function InternalHistory() {
  const [rows, setRows] = useState([]);
  const [options, setOptions] = useState({ campaigns: [], years: [], managers: [] });
  const [filters, setFilters] = useState({ campaign_id: "", year: "", manager: "", status: "", tipo: "", search: "" });
  const [page, setPage] = useState(1);
  const [message, setMessage] = useState("Seleccione filtros y presione Buscar para consultar el histórico.");
  const rowsPerPage = 80;

  useEffect(() => { getInternalHistoryFilters().then(setOptions).catch(() => {}); }, []);
  const set = (key) => (e) => setFilters((f) => ({ ...f, [key]: e.target.value }));

  async function searchHistory() {
    try {
      const params = Object.fromEntries(Object.entries(filters).filter(([, v]) => v !== ""));
      const data = await getInternalHistory(params);
      setRows(data); setPage(1);
      setMessage(data.length ? "" : "No hay registros con los filtros seleccionados.");
    } catch (e) { setMessage(errorText(e, "No se pudo consultar el histórico.")); }
  }

  const totalPages = Math.ceil(rows.length / rowsPerPage);
  const visible = rows.slice((page - 1) * rowsPerPage, page * rowsPerPage);
  const register = (type, n) => registerExport({ type, module: "Histórico · VPN internas", description: "Histórico de VPN internas", records: n });

  return (
    <div>
      <h1 className="text-2xl font-bold">Histórico SOX · VPN internas</h1>
      <p className="mt-1 text-slate-500">Consulta de campañas y validaciones de VPN internas (RDP y Aplicaciones).</p>

      <div className="mt-6 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
          <h3 className="text-lg font-bold">Registros históricos</h3>
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex h-11 w-80 items-center gap-2 rounded-lg border border-slate-300 bg-white px-3">
              <Search size={18} className="text-slate-500"/>
              <input value={filters.search} onChange={set("search")} onKeyDown={(e) => e.key === "Enter" && searchHistory()}
                className="w-full border-none bg-transparent text-sm outline-none" placeholder="Buscar por cuenta, nombre o gerente..."/>
            </div>
            <button onClick={searchHistory} className="h-11 rounded-lg bg-blue-600 px-6 text-sm font-bold text-white hover:bg-blue-700">Buscar</button>
            <button className="h-11 rounded-lg bg-green-600 px-5 text-sm font-bold text-white hover:bg-green-700" onClick={async () => {
              try { register("Excel", await exportToExcel(rows, "historico-vpn-internas-sox.xlsx", INTERNAL_HISTORY_COLUMNS, "Histórico internas")); }
              catch { window.alert("No se pudo generar el archivo Excel."); }
            }}>Excel</button>
            <button className="h-11 rounded-lg bg-red-600 px-5 text-sm font-bold text-white hover:bg-red-700" onClick={() => {
              try { register("PDF", exportToPdf(rows, "historico-vpn-internas-sox.pdf", INTERNAL_HISTORY_COLUMNS, "Histórico de VPN internas - Control 7")); }
              catch { window.alert("No se pudo generar el archivo PDF."); }
            }}>PDF</button>
          </div>
        </div>

        <div className="mb-5 grid grid-cols-1 gap-3 md:grid-cols-5">
          <select value={filters.campaign_id} onChange={set("campaign_id")} className={SELECT}>
            <option value="">Todas las campañas</option>{options.campaigns.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
          <select value={filters.year} onChange={set("year")} className={SELECT}>
            <option value="">Todos los años</option>{options.years.map((y) => <option key={y} value={y}>{y}</option>)}
          </select>
          <select value={filters.status} onChange={set("status")} className={SELECT}>
            <option value="">Todos los estados</option><option value="pendiente">Pendiente</option>
            {Object.entries(DECISION_LABEL).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
          <select value={filters.tipo} onChange={set("tipo")} className={SELECT}>
            <option value="">Todos los accesos</option><option value="RDP">RDP</option><option value="APLICACIONES">Aplicaciones</option>
          </select>
          <select value={filters.manager} onChange={set("manager")} className={SELECT}>
            <option value="">Todos los gerentes</option>{options.managers.map((m) => <option key={m} value={m}>{m}</option>)}
          </select>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full min-w-[1200px] border-collapse text-sm">
            <thead><tr className="bg-slate-50 text-left">
              {["Campaña", "Cuenta", "Nombre", "Acceso", "Gerente", "Estado", "Decisión", "Observación", "Fecha Límite", "Confirmó"].map((h) => <th key={h} className="border-b border-slate-200 p-4">{h}</th>)}
            </tr></thead>
            <tbody>{visible.map((item) => (
              <tr key={item.id} className="hover:bg-slate-50">
                <td className="border-b border-slate-100 p-4 font-bold">{item.campaign_name}</td>
                <td className="border-b border-slate-100 p-4 font-bold text-blue-700">{item.usuario}</td>
                <td className="border-b border-slate-100 p-4">{item.nombre || "-"}</td>
                <td className="border-b border-slate-100 p-4">{ACCESS_LABEL[item.tipo_acceso]}</td>
                <td className="border-b border-slate-100 p-4">{item.gerente || "-"}</td>
                <td className="border-b border-slate-100 p-4"><StatusBadge status={historyStatus(item)}/></td>
                <td className="border-b border-slate-100 p-4">{item.confirmacion === 1 ? DECISION_LABEL[item.estado] : "-"}</td>
                <td className="border-b border-slate-100 p-4">{item.observacion || "-"}</td>
                <td className="border-b border-slate-100 p-4">{item.deadline ? formatDateTime(item.deadline, { seconds: false }) : "-"}</td>
                <td className="border-b border-slate-100 p-4">{item.confirmado_por || "-"}</td>
              </tr>
            ))}</tbody>
          </table>
        </div>
        <Pagination currentPage={page} totalPages={totalPages} onPageChange={setPage}/>
        {message && <div className="p-8 text-center text-slate-500">{message}</div>}
      </div>
    </div>
  );
}
