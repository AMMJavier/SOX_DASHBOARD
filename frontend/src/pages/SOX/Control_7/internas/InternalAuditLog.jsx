import { useEffect, useMemo, useState } from "react";
import { Search } from "lucide-react";
import Pagination from "../../../../components/common/Pagination";
import { exportToExcel } from "../../../../utils/sox/control_7/exportExcel";
import { exportToPdf } from "../../../../utils/sox/control_7/exportPdf";
import { registerExport } from "../../../../utils/sox/control_7/registerExport";
import { formatDateTime } from "../../../../utils/dateTime";
import { errorText, getInternalAuditLog } from "../../../../services/sox/control_7/internalVpnService";
import { ACCESS_LABEL, DECISION_LABEL, INTERNAL_AUDIT_COLUMNS } from "./internalShared";

const SELECT = "h-11 rounded-lg border border-slate-300 bg-white px-3 text-sm";
const ACTION_LABEL = { MODIFICACION_VALIDACION: "Validación individual", GUARDAR_MASIVO: "Guardado masivo" };
const unique = (rows, key) => [...new Set(rows.map((r) => r[key]).filter(Boolean))].sort();

async function exportLogs(kind, rows) {
  try {
    const n = kind === "Excel"
      ? await exportToExcel(rows, "seguimiento-vpn-internas-sox.xlsx", INTERNAL_AUDIT_COLUMNS, "Seguimiento internas")
      : exportToPdf(rows, "seguimiento-vpn-internas-sox.pdf", INTERNAL_AUDIT_COLUMNS, "Seguimiento VPN internas - Control 7");
    registerExport({ type: kind, module: "Seguimiento · VPN internas", description: "Seguimiento de VPN internas", records: n });
  } catch {
    window.alert(`No se pudo generar el archivo ${kind}.`);
  }
}

/** Seguimiento de VPN internas: mismo formato que el Seguimiento de VPN externas. */
export default function InternalAuditLog() {
  const [logs, setLogs] = useState([]);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [manager, setManager] = useState("");
  const [action, setAction] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const rowsPerPage = 50;

  useEffect(() => { getInternalAuditLog().then(setLogs).catch((e) => setError(errorText(e, "No se pudo cargar el seguimiento."))); }, []);

  const managers = useMemo(() => unique(logs, "gerente"), [logs]);
  const actions = useMemo(() => unique(logs, "accion"), [logs]);
  const statuses = useMemo(() => unique(logs, "estado_nuevo"), [logs]);
  const filtered = logs.filter((item) => {
    const text = `${item.cuenta} ${item.gerente} ${item.usuario} ${item.accion} ${item.estado_nuevo} ${item.observacion_nueva}`.toLowerCase();
    return text.includes(search.toLowerCase()) && (!manager || item.gerente === manager)
      && (!action || item.accion === action) && (!status || item.estado_nuevo === status);
  });
  const totalPages = Math.ceil(filtered.length / rowsPerPage);
  const rows = filtered.slice((page - 1) * rowsPerPage, page * rowsPerPage);
  const reset = (setter) => (e) => { setter(e.target.value); setPage(1); };

  return (
    <div>
      <h1 className="text-2xl font-bold">Seguimiento · VPN internas</h1>
      <p className="mt-1 text-slate-500">Historial de acciones realizadas sobre las validaciones de VPN internas (RDP y Aplicaciones).</p>
      {error && <p className="mt-4 rounded-xl bg-amber-50 p-3 text-sm text-amber-800">{error}</p>}

      <div className="mt-6 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
          <h3 className="text-lg font-bold">Registros de auditoría</h3>
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex h-11 w-96 items-center gap-2 rounded-lg border border-slate-300 bg-white px-3">
              <Search size={18} className="text-slate-500"/>
              <input value={search} onChange={reset(setSearch)} className="w-full border-none bg-transparent text-sm outline-none" placeholder="Buscar por cuenta, gerente o usuario..."/>
            </div>
            <button onClick={() => exportLogs("Excel", filtered)} className="h-11 rounded-lg bg-green-600 px-5 text-sm font-bold text-white hover:bg-green-700">Excel</button>
            <button onClick={() => exportLogs("PDF", filtered)} className="h-11 rounded-lg bg-red-600 px-5 text-sm font-bold text-white hover:bg-red-700">PDF</button>
          </div>
        </div>

        <div className="mb-5 grid grid-cols-1 gap-3 md:grid-cols-3">
          <select value={manager} onChange={reset(setManager)} className={SELECT}>
            <option value="">Todos los gerentes</option>{managers.map((m) => <option key={m} value={m}>{m}</option>)}
          </select>
          <select value={action} onChange={reset(setAction)} className={SELECT}>
            <option value="">Todas las acciones</option>{actions.map((a) => <option key={a} value={a}>{ACTION_LABEL[a] || a}</option>)}
          </select>
          <select value={status} onChange={reset(setStatus)} className={SELECT}>
            <option value="">Todos los estados</option>{statuses.map((s) => <option key={s} value={s}>{DECISION_LABEL[s] || s}</option>)}
          </select>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full min-w-[1100px] border-collapse text-sm">
            <thead><tr className="bg-slate-50 text-left">
              {["Fecha", "Usuario", "Gerente", "Cuenta", "Acceso", "Acción", "Estado anterior", "Estado nuevo", "Observación"].map((h) => <th key={h} className="border-b p-4">{h}</th>)}
            </tr></thead>
            <tbody>{rows.map((item) => (
              <tr key={item.id}>
                <td className="border-b p-4">{formatDateTime(item.fecha_evento)}</td>
                <td className="border-b p-4">{item.usuario || "-"}</td>
                <td className="border-b p-4">{item.gerente || "-"}</td>
                <td className="border-b p-4 font-bold text-blue-700">{item.cuenta || "-"}</td>
                <td className="border-b p-4">{ACCESS_LABEL[item.tipo_acceso] || "-"}</td>
                <td className="border-b p-4">{ACTION_LABEL[item.accion] || item.accion || "-"}</td>
                <td className="border-b p-4">{DECISION_LABEL[item.estado_anterior] || item.estado_anterior || "-"}</td>
                <td className="border-b p-4">{DECISION_LABEL[item.estado_nuevo] || item.estado_nuevo || "-"}</td>
                <td className="border-b p-4">{item.observacion_nueva || "-"}</td>
              </tr>
            ))}</tbody>
          </table>
        </div>
        <Pagination currentPage={page} totalPages={totalPages} onPageChange={setPage}/>
        {filtered.length === 0 && <div className="p-8 text-center text-slate-500">No existen registros de auditoría.</div>}
      </div>
    </div>
  );
}
