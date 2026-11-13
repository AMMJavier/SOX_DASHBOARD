import { useEffect, useState } from "react";
import { Search, FileSpreadsheet, FileText } from "lucide-react";
import StatusBadge from "../../../components/SOX/control_7/StatusBadge";
import Pagination from "../../../components/common/Pagination";
import { api } from "../../../services/api";
import { exportToExcel } from "../../../utils/sox/control_7/exportExcel";
import { exportToPdf } from "../../../utils/sox/control_7/exportPdf";
import { closeActiveCampaign, getCampaignValidations } from "../../../services/sox/control_7/campaignService";
import CampaignNotifications from "../../../components/SOX/control_7/CampaignNotifications";

export default function Campaigns() {
  const [validations, setValidations] = useState([]);
  const [search, setSearch] = useState("");

const [selectedManager, setSelectedManager] = useState("");
const [selectedStatus, setSelectedStatus] = useState("");
const [selectedValidity, setSelectedValidity] = useState("");

const [managers, setManagers] = useState([]);
const [statuses, setStatuses] = useState([]);
const [currentPage, setCurrentPage] = useState(1);
const rowsPerPage = 80;

  useEffect(() => {
    loadValidations();
    loadFilters();
  }, []);

  async function loadValidations() {
    const response = await getCampaignValidations();
    
    const data = Array.isArray(response)
        ? response
        : response.data || [];
    
    setValidations(data);
  }

  async function loadFilters(){
    const response = await api.get(
        "/sox/campaign/validation-filters"
    );
    setManagers(response.data.managers);
    setStatuses(response.data.statuses);
}

  const handleCloseCampaign = async () => {
    const confirmClose = window.confirm(
      "¿Está seguro de cerrar la campaña activa? Los registros pasarán al histórico y se creará una nueva campaña."
    );

    if (!confirmClose) return;

    try {
      await closeActiveCampaign({
        
      });

      alert("Campaña cerrada correctamente.");
      window.location.reload();
    } catch (error) {
      console.error(error);
      alert("Error al cerrar la campaña.");
    }
  };

  const filteredValidations = validations.filter((item) => {
    const text = `
      ${item.req}
      ${item.nombre_vpn}
      ${item.manager}
      ${item.status}
      ${item.observacion}
    `.toLowerCase();

    return (
    text.includes(search.toLowerCase())
    &&
    (
        !selectedManager ||
        item.manager === selectedManager
    )
    &&
    (
        !selectedStatus ||
        item.status === selectedStatus
    )
    &&
    (
      !selectedValidity ||
      getValidityStatus(item) === selectedValidity
    )
  );
  });
  const totalPages = Math.ceil(
    filteredValidations.length / rowsPerPage
  );


const paginatedValidations = filteredValidations.slice(
  (currentPage - 1) * rowsPerPage,
  currentPage * rowsPerPage
);

function getValidityStatus(item){

    if(
        item.confirmed === 0 &&
        item.fecha_limite &&
        new Date(item.fecha_limite) < new Date()
    ){
        return "Vencida";
    }

    return "En plazo";
}

return (
    <div>
      <h1 className="text-2xl font-bold">Campañas SOX</h1>
      <p className="mt-1 text-slate-500">
        Gestión de la campaña activa y sus validaciones.
      </p>

      <CampaignNotifications />

      <div className="mt-6 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="mb-5 flex items-center justify-between">

          <h3 className="text-lg font-bold">
            Validaciones de campaña activa
          </h3>


          <div className="flex items-center gap-3">

            <div className="flex h-11 w-96 items-center gap-2 rounded-lg border border-slate-300 bg-white px-3">

              <Search size={18} className="text-slate-500" />

              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full border-none bg-transparent text-sm outline-none"
                placeholder="Buscar por VPN, solicitante, REQ o gerente..."
              />

            </div>


            <button
              onClick={handleCloseCampaign}
              className="h-11 rounded-lg bg-slate-900 px-5 text-sm font-bold text-white hover:bg-slate-800"
            >
              Cerrar campaña
            </button>


            <button
              onClick={async () => {
                try {
                  await exportToExcel(filteredValidations);
                } catch (error) {
                  console.error("Error exportando campaña a Excel:", error);
                  window.alert("No se pudo generar el archivo Excel.");
                }
              }}
              className="h-11 rounded-lg bg-green-600 px-5 text-sm font-bold text-white hover:bg-green-700"
            >
              Excel
            </button>


            <button
              onClick={() => exportToPdf(filteredValidations)}
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



          <select
            value={selectedValidity}
            onChange={(e)=>setSelectedValidity(e.target.value)}
            className="h-11 rounded-lg border border-slate-300 bg-white px-3 text-sm"
          >

            <option value="">
              Todos los vencimientos
            </option>

            <option value="En plazo">
              En plazo
            </option>

            <option value="Vencida">
              Vencidas
            </option>

          </select>

      </div>


        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="bg-slate-50 text-left">
              <th className="border-b p-4">REQ</th>
              <th className="border-b p-4">Nombre VPN</th>
              <th className="border-b p-4">Solicitante</th>
              <th className="border-b p-4">Gerente Asignado</th>
              <th className="border-b p-4">Estado</th>
              <th className="border-b p-4">Confirmación</th>
              <th className="border-b p-4">Observación</th>
              <th className="border-b p-4">Fecha VPN</th>
              <th className="border-b p-4">Vencimiento</th>
              <th className="border-b p-4">Fecha Modificación</th>
            </tr>
          </thead>

          <tbody>
            {paginatedValidations.map((item) => (
              <tr key={item.checkpoint_uid}>
                <td className="border-b p-4 font-bold text-blue-700">
                  {item.req}
                </td>

                <td className="border-b p-4">
                  {item.nombre_vpn || "-"}
                </td>

                <td className="border-b p-4">
                  {item.solicitante || "-"}
                </td>

                <td className="border-b p-4">
                  {item.manager || "-"}
                </td>

                <td className="border-b p-4">
                  <StatusBadge status={item.status}/>
                </td>

                <td className="border-b p-4">
                  {item.confirmed === 1 
                    ? "Confirmado" 
                    : "Pendiente"}
                </td>

                <td className="border-b p-4">
                  {item.observation || "-"}
                </td>

                <td className="border-b p-4">
                  {item.date || "-"}
                </td>

                <td className="border-b p-4">
                  {
                  getValidityStatus(item)
                  }
                </td>

                <td className="border-b p-4">
                  {item.fecha_modificacion || "-"}
                </td>

                
              </tr>
            ))}
          </tbody>
        </table>
        <Pagination
            currentPage={currentPage}
            totalPages={totalPages}
            onPageChange={setCurrentPage}
        />
        {filteredValidations.length === 0 && (
          <div className="p-8 text-center text-slate-500">
            No hay registros cargados para la campaña activa.
          </div>
        )}
      </div>
    </div>
  );
}