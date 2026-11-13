import { useEffect, useState } from "react";
import { Search, FileSpreadsheet, FileText } from "lucide-react";
import Pagination from "../../../components/common/Pagination";
import { api } from "../../../services/api";
import { exportToExcel } from "../../../utils/sox/control_7/exportExcel";
import { exportToPdf } from "../../../utils/sox/control_7/exportPdf";
import { AUDIT_COLUMNS } from "../../../utils/sox/control_7/exportColumns";
import { registerExport } from "../../../utils/sox/control_7/registerExport";

async function exportLogs(kind, rows) {
  try {
    const n = kind === "Excel"
      ? await exportToExcel(rows, "logs-control7-sox.xlsx", AUDIT_COLUMNS, "Logs")
      : exportToPdf(rows, "logs-control7-sox.pdf", AUDIT_COLUMNS, "Logs de auditoría - Control 7");
    registerExport({ type: kind, module: "Logs", description: "Logs de auditoría del Control 7", records: n });
  } catch (error) {
    console.error(`Error exportando logs a ${kind}:`, error);
    window.alert(`No se pudo generar el archivo ${kind}.`);
  }
}


export default function AuditLogs() {
  console.log("ENTRO AUDIT LOGS");

  const [logs, setLogs] = useState([]);

  const [search, setSearch] = useState("");

  const [selectedManager, setSelectedManager] = useState("");
  const [selectedAction, setSelectedAction] = useState("");
  const [selectedStatus, setSelectedStatus] = useState("");

  const [managers, setManagers] = useState([]);
  const [actions, setActions] = useState([]);
  const [statuses, setStatuses] = useState([]);

  const [currentPage, setCurrentPage] = useState(1);
  const rowsPerPage = 50;

  useEffect(() => {
    loadLogs();
  }, []);


  async function loadLogs(){
    const response = await api.get(
      "/sox/audit/logs"
    );

    const data = Array.isArray(response.data)
      ? response.data
      : response.data.data || response.data.logs || [];
    setLogs(data);
    setManagers(
      [
        ...new Set(
          data.map(
            item => item.gerente
          )
          .filter(Boolean)
        )
      ]
    );

    setActions(
      [
        ...new Set(
          data.map(
            item => item.accion
          )
          .filter(Boolean)
        )
      ]
    );

    setStatuses(
      [
        ...new Set(
          data.map(
            item => item.estado_nuevo
          )
          .filter(Boolean)
        )
      ]
    );
  }

  const filteredLogs = (Array.isArray(logs) ? logs : []).filter((item)=>{
    const text = `
      ${item.req}
      ${item.nombre_vpn}
      ${item.gerente}
      ${item.usuario}
      ${item.accion}
      ${item.estado_nuevo}
      ${item.observacion_nueva}
    `.toLowerCase();

    return (
      text.includes(
        search.toLowerCase()
      )
      &&
      (
        !selectedManager
        ||
        item.gerente === selectedManager
      )
      &&
      (
        !selectedAction
        ||
        item.accion === selectedAction
      )
      &&
      (
        !selectedStatus
        ||
        item.estado_nuevo === selectedStatus
      )
    );
  });

  const totalPages = Math.ceil(
    filteredLogs.length / rowsPerPage
  );

  const paginatedLogs =
    filteredLogs.slice(
      (currentPage - 1) * rowsPerPage,
      currentPage * rowsPerPage
    );

  return (
    <div>
      <h1 className="text-2xl font-bold">
        Auditoría SOX
      </h1>

      <p className="mt-1 text-slate-500">
        Historial de acciones realizadas sobre las validaciones de VPN.
      </p>

      <div className="mt-6 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="mb-5 flex items-center justify-between">
          <h3 className="text-lg font-bold">
            Registros de auditoría
          </h3>

          <div className="flex items-center gap-3">
            <div className="flex h-11 w-96 items-center gap-2 rounded-lg border border-slate-300 bg-white px-3">
              <Search
                size={18}
                className="text-slate-500"
              />

              <input
                value={search}
                onChange={(e)=>setSearch(e.target.value)}
                className="w-full border-none bg-transparent text-sm outline-none"
                placeholder="Buscar por VPN, REQ, gerente o usuario..."

              />
            </div>

            <button
              onClick={() => exportLogs("Excel", filteredLogs)}
              className="h-11 rounded-lg bg-green-600 px-5 text-sm font-bold text-white hover:bg-green-700"
            >
              Excel
            </button>

            <button
              onClick={() => exportLogs("PDF", filteredLogs)}
              className="h-11 rounded-lg bg-red-600 px-5 text-sm font-bold text-white hover:bg-red-700"
            >
              PDF
            </button>
          </div>
        </div>

        <div className="mb-5 grid grid-cols-1 gap-3 md:grid-cols-3">
          <select
            value={selectedManager}
            onChange={(e)=>setSelectedManager(e.target.value)}
            className="h-11 rounded-lg border border-slate-300 bg-white px-3 text-sm"

          >
            <option value="">
              Todos los gerentes
            </option>

            {
              managers.map((manager)=>(
                <option
                  key={manager}
                  value={manager}
                >
                  {manager}
                </option>
              ))
            }
          </select>

          <select
            value={selectedAction}
            onChange={(e)=>setSelectedAction(e.target.value)}
            className="h-11 rounded-lg border border-slate-300 bg-white px-3 text-sm"
          >
            <option value="">
              Todas las acciones
            </option>

            {
              actions.map((action)=>(
                <option
                  key={action}
                  value={action}
                >
                  {action}
                </option>
              ))
            }
          </select>

          <select
            value={selectedStatus}
            onChange={(e)=>setSelectedStatus(e.target.value)}
            className="h-11 rounded-lg border border-slate-300 bg-white px-3 text-sm"
          >
            <option value="">
              Todos los estados
            </option>

            {
              statuses.map((status)=>(
                <option
                  key={status}
                  value={status}
                >
                  {status}
                </option>
              ))
            }

          </select>
        </div>

        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="bg-slate-50 text-left">

              <th className="border-b p-4">
                Fecha
              </th>

              <th className="border-b p-4">
                Usuario
              </th>

              <th className="border-b p-4">
                Gerente
              </th>

              <th className="border-b p-4">
                REQ
              </th>

              <th className="border-b p-4">
                VPN
              </th>

              <th className="border-b p-4">
                Acción
              </th>

              <th className="border-b p-4">
                Estado anterior
              </th>

              <th className="border-b p-4">
                Estado nuevo
              </th>

              <th className="border-b p-4">
                Observación
              </th>

            </tr>
          </thead>
          <tbody>

            {
              paginatedLogs.map((item,index)=>(
                <tr key={index}>

                  <td className="border-b p-4">
                    {item.fecha_evento || "-"}
                  </td>

                  <td className="border-b p-4">
                    {item.usuario || "-"}
                  </td>

                  <td className="border-b p-4">
                    {item.gerente || "-"}
                  </td>

                  <td className="border-b p-4 font-bold text-blue-700">
                    {item.req || "-"}
                  </td>

                  <td className="border-b p-4">
                    {item.nombre_vpn || "-"}
                  </td>

                  <td className="border-b p-4">
                    {item.accion || "-"}
                  </td>

                  <td className="border-b p-4">
                    {item.estado_anterior || "-"}
                  </td>

                  <td className="border-b p-4">
                    {item.estado_nuevo || "-"}
                  </td>

                  <td className="border-b p-4">
                    {item.observacion_nueva || "-"}
                  </td>
                </tr>
              ))
            }
          </tbody>
        </table>

        <Pagination
          currentPage={currentPage}
          totalPages={totalPages}
          onPageChange={setCurrentPage}
        />

        {
          filteredLogs.length === 0 && (
            <div className="p-8 text-center text-slate-500">
              No existen registros de auditoría.
            </div>

          )
        }
      </div>
    </div>
  );
}