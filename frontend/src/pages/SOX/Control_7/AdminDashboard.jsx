import { useEffect, useState } from "react";
import { api } from "../../../services/api";
import { ClipboardList, CheckCircle, Clock, AlertTriangle } from "lucide-react";
import { ShieldCheck } from "lucide-react";
import Pagination from "../../../components/common/Pagination";

export default function AdminDashboard() {
  const [kpis, setKpis] = useState({
    total: 0,
    total_checkpoint: 0,
    confirmed: 0,
    pending: 0,
    expired: 0,
    no_owner: 0,
    transform: 0,
  });

  const [managersProgress, setManagersProgress] = useState([]);
  const [selectedManager, setSelectedManager] = useState("TODOS");
  const [managersList, setManagersList] = useState([]);
  const [responsiblePage, setResponsiblePage] = useState(1);
  const responsiblePerPage = 5;

  useEffect(() => {
    loadDashboard();
    loadManagersProgress();
  }, [selectedManager]);

  useEffect(() => {
    loadManagers();
  }, []
);

  const indexLastResponsible =
    responsiblePage * responsiblePerPage;

const indexFirstResponsible =
    indexLastResponsible - responsiblePerPage;


const visibleManagersProgress =
    managersProgress.slice(
        indexFirstResponsible,
        indexLastResponsible
    );

const totalResponsiblePages =
    Math.ceil(
        managersProgress.length / responsiblePerPage
    );
async function loadManagersProgress(){
    const response = await api.get(
        "/sox/admin/dashboard/responsibles"
    );

    let data = response.data;
    if(selectedManager !== "TODOS"){
        data = data.filter(
            item => item.manager === selectedManager
        );

    }

    data = data.map(item => ({
        ...item,
        percent:
            item.total > 0
            ?
            Math.round(
                (item.confirmed / item.total) * 100
            )
            :
            0
    }));


    setManagersProgress(data);
}

  async function loadDashboard() {
    const response = await api.get("/sox/campaign/validations");
    let data = response.data.data;
    if(selectedManager !== "TODOS"){
        data = data.filter(
            item => item.manager === selectedManager
        );
    }

    // filtro por gerente seleccionado
    const filteredData =
        selectedManager === "TODOS"
        ?
        data
        :
        data.filter(
            item => item.manager === selectedManager
        );

    const total = filteredData.length;
    const confirmed = filteredData.filter(
        item => item.confirmed === 1
    ).length;

    const pending = filteredData.filter(
      item => item.confirmed === 0
  ).length;

    const expired = filteredData.filter(
    item =>
        item.confirmed === 0 &&
        item.fecha_limite &&
        new Date(item.fecha_limite) < new Date()
    ).length;

    const no_owner = filteredData.filter(
        item => !item.manager
    ).length;

    setKpis({
        total: response.data.total_checkpoint,
        total_checkpoint: response.data.total_checkpoint,
        transform: total,
        confirmed,
        pending,
        expired,
        no_owner
    });

}

 // cargar lista de gerentes
    async function loadManagers(){
    const response = await api.get("/sox/admin/managers");
    setManagersList(response.data);
}

  const confirmedPercent =
    kpis.total > 0 ? Math.round((kpis.confirmed / kpis.total) * 100) : 0;

  return (
    <div>
      <h1 className="text-2xl font-bold">Dashboard Administrador SOX</h1>
      <p className="mt-1 text-slate-500">
        Resumen ejecutivo de la campaña activa.
      </p>
      <div className="mt-5 flex items-center gap-3">
        <label className="font-bold">
            Gerente:
        </label>
        <select
            className="rounded-lg border border-slate-300 px-4 py-2"
            value={selectedManager}
            onChange={(e)=>{setSelectedManager(e.target.value);
              setResponsiblePage(1);
            }}
        >

            <option value="TODOS">
                Todos los gerentes
            </option>

            {managersList.map((manager)=>(
              <option
                  key={manager.id}
                  value={manager.name}
              >
                  {manager.name}
              </option>
           ))}

        </select>

      </div>

      <div className="mt-6 grid grid-cols-1 gap-5 md:grid-cols-2 xl:grid-cols-5">
        <Kpi
          title="Total Registros"
          value={kpis.total}
          color="bg-blue-600"
          icon={ClipboardList}
        />

        <Kpi
          title="Confirmados"
          value={kpis.confirmed}
          color="bg-green-600"
          icon={CheckCircle}
        />

        <Kpi
          title="Pendientes"
          value={kpis.pending}
          color="bg-amber-500"
          icon={Clock}
        />

        <Kpi
          title="Vencidos"
          value={kpis.expired}
          color="bg-red-600"
          icon={AlertTriangle}
        />

        <Kpi
          title="Conciliación Check Point"
          value={`${kpis.transform}/${kpis.total_checkpoint}`}
          color="bg-indigo-600"
          icon={ShieldCheck}
        />
      </div>


      <div className="mt-6 grid grid-cols-1 gap-6 xl:grid-cols-2">
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <h3 className="text-lg font-bold">Avance General de Validación</h3>

          <div className="mt-6 flex items-center gap-10">
            <div
              className="flex h-56 w-56 items-center justify-center rounded-full"
              style={{
                background: `conic-gradient(#16a34a ${confirmedPercent}%, #f59e0b ${confirmedPercent}% 100%)`,
              }}
            >
              <div className="flex h-36 w-36 flex-col items-center justify-center rounded-full bg-white">
                <span className="text-4xl font-bold">{confirmedPercent}%</span>
                <span className="text-sm text-slate-500">Avance general</span>
              </div>
            </div>

            <div className="flex-1 space-y-4">
              <Legend color="bg-green-600" label="Confirmados" value={kpis.confirmed} />
              <Legend color="bg-amber-500" label="Pendientes" value={kpis.pending} />
              <Legend color="bg-red-600" label="Vencidos" value={kpis.expired} />
              <Legend color="bg-purple-600" label="Sin Responsable" value={kpis.no_owner} />
            </div>
          </div>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <h3 className="text-lg font-bold">Avance por Responsable</h3>

          <div className="mt-6 space-y-5">
            {visibleManagersProgress.map((item) => (
              <div key={item.manager}>
                <div className="mb-2 flex justify-between text-sm">
                  <span>{item.manager}</span>
                  <b>
                    {item.percent}% ({item.confirmed} / {item.total})
                  </b>
                </div>

                <div className="h-2 rounded-full bg-slate-200">
                  <div
                      className={`h-2 rounded-full ${
                          item.percent > 0
                          ? "bg-green-600"
                          : "bg-slate-200"
                      }`}
                      style={{
                          width: `${item.percent}%`
                      }}
                  />
                </div>
              </div>
            ))}

            {managersProgress.length === 0 && (
              <p className="text-sm text-slate-500">
                No hay responsables para mostrar en la campaña activa.
              </p>
            )}
            {
              totalResponsiblePages > 1 && (
                  <Pagination
                      currentPage={responsiblePage}
                      totalPages={totalResponsiblePages}
                      onPageChange={setResponsiblePage}
                  />
              )
            }
          </div>
        </div>
      </div>
    </div>
  );
}

function Kpi({ title, value, color, icon: Icon }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className={`mb-4 flex h-14 w-14 items-center justify-center rounded-full ${color}`}>
        <Icon size={30} className="text-white" />
      </div>

      <p className="text-sm font-bold text-slate-700">{title}</p>
      <h2 className="mt-2 text-3xl font-bold">{value}</h2>
    </div>
  );
}

function Legend({ color, label, value }) {
  return (
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-3">
        <span className={`h-4 w-4 rounded ${color}`} />
        <span>{label}</span>
      </div>
      <b>{value}</b>
    </div>
  );

function getExpirationStatus(item){

    if(
        item.confirmed === 0 &&
        item.fecha_limite &&
        new Date(item.fecha_limite) < new Date()
    ){
        return "Vencida";
    }

    return "";
}

}