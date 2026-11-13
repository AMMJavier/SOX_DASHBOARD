import { useEffect, useState } from "react";
import { Search } from "lucide-react";
import StatusBadge from "../../../components/SOX/control_7/StatusBadge";
import Pagination from "../../../components/common/Pagination";
import { getHistory, getHistoryFilters } from "../../../services/sox/control_7/historyService";
import { exportToExcel } from "../../../utils/sox/control_7/exportExcel";
import { exportToPdf } from "../../../utils/sox/control_7/exportPdf";
import { registerExport } from "../../../utils/sox/control_7/registerExport";
import { HISTORY_COLUMNS } from "../../../utils/sox/control_7/exportColumns";

export default function History() {
  const [history, setHistory] = useState([]);
  const [search, setSearch] = useState("");
  const [selectedCampaign, setSelectedCampaign] = useState("");
  const [selectedYear, setSelectedYear] = useState("");
  const [selectedMonth, setSelectedMonth] = useState("");
  const [selectedManager, setSelectedManager] = useState("");
  const [selectedStatus, setSelectedStatus] = useState("");
  const [selectedValidity, setSelectedValidity] = useState("");
  const [filterOptions, setFilterOptions] = useState({
    campaigns: [],
    years: [],
    managers: [],
  });
  const [currentPage, setCurrentPage] = useState(1);
  const rowsPerPage = 80;

  const months = [
    { value: "1", label: "Enero" },
    { value: "2", label: "Febrero" },
    { value: "3", label: "Marzo" },
    { value: "4", label: "Abril" },
    { value: "5", label: "Mayo" },
    { value: "6", label: "Junio" },
    { value: "7", label: "Julio" },
    { value: "8", label: "Agosto" },
    { value: "9", label: "Septiembre" },
    { value: "10", label: "Octubre" },
    { value: "11", label: "Noviembre" },
    { value: "12", label: "Diciembre" },
  ];

  const statuses = ["Mantener", "Eliminar", "No pertenece", "Otro"];

  useEffect(() => {
    async function loadFilters() {
      const data = await getHistoryFilters();
      setFilterOptions(data);
    }

    loadFilters();
  }, []);

  const handleSearchHistory = async () => {
    const filters = {
      campaign_id: selectedCampaign || undefined,
      year: selectedYear || undefined,
      month: selectedMonth || undefined,
      manager: selectedManager || undefined,
      status: selectedStatus || undefined,
      validity: selectedStatus || undefined,
      search: search || undefined,
    };

    const response = await getHistory(filters);
      setHistory(response);
      setCurrentPage(1);
  };

  const getSelectedLabel = (list, id) => {
    const item = list.find((x) => String(x.id) === String(id));
    return item ? item.name : "Todas";
  };

  const getMonthLabel = () => {
    const item = months.find((x) => x.value === selectedMonth);
    return item ? item.label : "Todos";
  };

  const filteredHistory = history;

  const totalPages = Math.ceil(
  filteredHistory.length / rowsPerPage
);


const paginatedHistory = filteredHistory.slice(
  (currentPage - 1) * rowsPerPage,
  currentPage * rowsPerPage
);

  const registerDownload = (type) => {
    registerExport({
      type,
      module: "Histórico",
      description: "Exportación de histórico filtrado",
      records: history.length,
    });
  };
  function getValidityStatus(item){

      if(
          item.decision === null &&
          item.deadline &&
          new Date(item.deadline) < new Date()
      ){
          return "Vencida";
      }

      return "En plazo";
  }
  return (
    <div>
      <h1 className="text-2xl font-bold">Histórico SOX</h1>

      <p className="mt-1 text-slate-500">
        Consulta de campañas cerradas y validaciones históricas.
      </p>

      <div className="mt-6 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="mb-5 flex items-center justify-between">
          <h3 className="text-lg font-bold">Registros históricos</h3>

          <div className="flex items-center gap-3">
            <div className="flex h-11 w-96 items-center gap-2 rounded-lg border border-slate-300 bg-white px-3">
              <Search size={18} className="text-slate-500" />
              <input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                className="w-full border-none bg-transparent text-sm outline-none"
                placeholder="Buscar por campaña, VPN, REQ o gerente..."
              />
            </div>

            <button
              onClick={handleSearchHistory}
              className="h-11 rounded-lg bg-blue-600 px-6 text-sm font-bold text-white hover:bg-blue-700"
            >
              Buscar
            </button>

            <button
              onClick={async () => {
                try {
                  await exportToExcel(filteredHistory, "historico-sox.xlsx", HISTORY_COLUMNS, "Histórico");
                  registerDownload("Excel");
                } catch (error) {
                  console.error("Error exportando histórico a Excel:", error);
                  window.alert("No se pudo generar el archivo Excel.");
                }
              }}
              className="h-11 rounded-lg bg-green-600 px-5 text-sm font-bold text-white hover:bg-green-700"
            >
              Excel
            </button>

            <button
              onClick={() => {
                try {
                  exportToPdf(filteredHistory, "historico-sox.pdf", HISTORY_COLUMNS, "Histórico de campañas - Control 7");
                  registerDownload("PDF");
                } catch (error) {
                  console.error("Error exportando histórico a PDF:", error);
                  window.alert("No se pudo generar el archivo PDF.");
                }
              }}
              className="h-11 rounded-lg bg-red-600 px-5 text-sm font-bold text-white hover:bg-red-700"
            >
              PDF
            </button>
          </div>
        </div>

        <div className="mb-5 grid grid-cols-1 gap-3 md:grid-cols-5">
          <select
            value={selectedCampaign}
            onChange={(e) => setSelectedCampaign(e.target.value)}
            className="h-11 rounded-lg border border-slate-300 bg-white px-3 text-sm"
          >
            <option value="">Todas las campañas</option>
            {filterOptions.campaigns.map((campaign) => (
              <option key={campaign.id} value={campaign.id}>
                {campaign.name}
              </option>
            ))}
          </select>

          <select
            value={selectedYear}
            onChange={(e) => setSelectedYear(e.target.value)}
            className="h-11 rounded-lg border border-slate-300 bg-white px-3 text-sm"
          >
            <option value="">Todos los años</option>
            {filterOptions.years.map((year) => (
              <option key={year} value={year}>
                {year}
              </option>
            ))}
          </select>

          <select
            value={selectedMonth}
            onChange={(e) => setSelectedMonth(e.target.value)}
            className="h-11 rounded-lg border border-slate-300 bg-white px-3 text-sm"
          >
            <option value="">Todos los meses</option>
            {months.map((month) => (
              <option key={month.value} value={month.value}>
                {month.label}
              </option>
            ))}
          </select>

          <select
            value={selectedStatus}
            onChange={(e) => setSelectedStatus(e.target.value)}
            className="h-11 rounded-lg border border-slate-300 bg-white px-3 text-sm"
          >
            <option value="">Todos los estados</option>
            {statuses.map((status) => (
              <option key={status} value={status}>
                {status}
              </option>
            ))}
          </select>

          <select
            value={selectedManager}
            onChange={(e) => setSelectedManager(e.target.value)}
            className="h-11 rounded-lg border border-slate-300 bg-white px-3 text-sm"
          >
            <option value="">Todos los gerentes</option>
            {filterOptions.managers.map((manager) => (
              <option key={manager} value={manager}>
                {manager}
              </option>
            ))}
          </select>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full min-w-[1200px] border-collapse text-sm">
            <thead>
              <tr className="bg-slate-50 text-left">
                <th className="border-b border-slate-200 p-4">Campaña</th>
                <th className="border-b border-slate-200 p-4">VPN / Cliente</th>
                <th className="border-b border-slate-200 p-4">REQ</th>
                <th className="border-b border-slate-200 p-4">Gerente</th>
                <th className="border-b border-slate-200 p-4">Estado</th>
                <th className="border-b border-slate-200 p-4">Decisión</th>
                <th className="border-b border-slate-200 p-4">Observación</th>
                <th className="border-b border-slate-200 p-4">Fecha Límite</th>
                <th className="border-b border-slate-200 p-4">Vencimiento</th>
                <th className="border-b border-slate-200 p-4">Cierre</th>
              </tr>
            </thead>

            <tbody>
              {paginatedHistory.map((item) => (
                <tr key={item.id} className="hover:bg-slate-50">
                  <td className="border-b border-slate-100 p-4 font-bold">
                    {item.campaign_name}
                  </td>
                  
                  <td className="border-b border-slate-100 p-4">{item.vpn}</td>
                  <td className="border-b border-slate-100 p-4 font-bold text-blue-700">
                    {item.req}
                  </td>
                  <td className="border-b border-slate-100 p-4">
                    {item.manager}
                  </td>
               
                 
                  <td className="border-b border-slate-100 p-4">
                    <StatusBadge status={item.status} />
                  </td>
                  <td className="border-b border-slate-100 p-4">
                    {item.decision || "-"}
                  </td>
                  <td className="border-b border-slate-100 p-4">
                    {item.observation || "-"}
                  </td>
                  <td className="border-b border-slate-100 p-4">
                    {item.deadline || "-"}
                  </td>
                  <td className="border-b border-slate-100 p-4">
                  {
                  getValidityStatus(item)
                  }
                  </td>
                  <td className="border-b border-slate-100 p-4">
                    {item.closed_at || "-"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <Pagination
              currentPage={currentPage}
              totalPages={totalPages}
              onPageChange={setCurrentPage}
          />
        {filteredHistory.length === 0 && (
          <div className="p-8 text-center text-slate-500">
            Seleccione filtros y presione Buscar para consultar el histórico.
          </div>
        )}
      </div>
    </div>
  );
}