import { useEffect, useState } from "react";
import { Save } from "lucide-react";
import Pagination from "../../../components/common/Pagination";
import { getManagers } from "../../../services/sox/control_7/managerService";

import {
  getValidationsByManager,
  updateValidation,
  confirmAllValidations,
} from "../../../services/sox/control_7/validationService";

import { getCampaignStatus } from "../../../services/sox/control_7/campaignService";

export default function ManagerDashboard() {
  const loggedUser = JSON.parse(localStorage.getItem("soxUser"));

  const [managers, setManagers] = useState([]);
  const [selectedManager, setSelectedManager] = useState("");
  const [validations, setValidations] = useState([]);
  const [currentPage, setCurrentPage] = useState(1);
  const rowsPerPage = 30;
  const [editingId, setEditingId] = useState(null);
  const [savedIds, setSavedIds] = useState([]);
  const [campaignExpired,setCampaignExpired] = useState(false);
  const [campaignStatus,setCampaignStatus] = useState(null);

  const isOwnManager =
  loggedUser?.rol !== "gerencial" ||
  selectedManager === loggedUser?.name;

useEffect(()=>{
async function loadCampaignStatus(){
    const data = await getCampaignStatus();
    setCampaignExpired(data.expired);
    setCampaignStatus(data);
}

loadCampaignStatus();


},[]);

 useEffect(() => {
 async function loadManagers() {
   const data = await getManagers();
   console.log("GERENTES DESDE API:", data);
   setManagers(data);
 }

 loadManagers();

}, []);

  useEffect(() => {
  async function loadValidations() {

    if (!selectedManager) {
      setValidations([]);
      return;
    }

    console.log("Gerente seleccionado:", selectedManager);

    const data = await getValidationsByManager(selectedManager);

      setValidations(data);
      setCurrentPage(1);
      console.log("VALIDACIONES CARGADAS:", data);

      console.log(
        "IDS:",
        data.map(x => x.id)
      );

      const saved = data
      .filter(
        item =>
          item.confirmed === 1 
      )
      .map(item => item.id);


      setSavedIds(saved);
  }

  loadValidations();

}, [selectedManager]);

  const handleChange = (id, field, value) => {
    setValidations((prev) =>
      prev.map((item) =>
        item.id === id ? { ...item, [field]: value } : item
      )
    );
    
  };
  const enableEdit = (id) => {
      setEditingId(id);
    };
  const saveValidation = async (item) => {

    if (!item.decision) {
      alert("Debe seleccionar una decisión antes de guardar.");
      return;
    }


    if (
      item.decision === "Otro" &&
      (!item.observation || item.observation.trim() === "")
    ) {
      alert("Debe ingresar una observación cuando seleccione 'Otro'.");
      return;
    }

    try {

      await updateValidation(item.id,{
        decision:item.decision,
        observation:item.observation || "",
      });


      // marcar como guardado
      setValidations((prev)=>
        prev.map(row =>
            row.id === item.id
            ? {
                ...row,
                confirmed:1,
                decision:item.decision,
                observation:item.observation || ""
              }
            : row
        )
      );


      // bloquear nuevamente
      setEditingId(null);
      alert("Validación guardada correctamente");

    } catch(error){

      console.error("Error guardando validación:",error);
      
      if 
      (
        error.response &&
        error.response.data &&
        error.response.data.detail
      ){
        alert(error.response.data.detail);
      }
      else{
        alert("No se pudo guardar la validación");
      }
    }

};

const handleSaveAll = async () => {
  console.log("PAYLOAD GUARDAR TODAS:", validations);
  try {

    const pendingValidations = validations
    .filter(item => Number(item.confirmed) === 0)
    .map(item => ({
        checkpoint_uid:item.id,
        decision:item.decision,
        observation:item.observation || ""
    }));

    // Validar decisiones vacías
    const invalid = pendingValidations.some(
      item => !item.decision
    );

    if (invalid) {
      alert("Existen VPN sin decisión seleccionada.");
      return;
    }

    // Validar observación cuando es Otro
    const invalidObservation = pendingValidations.some(
      item =>
        item.decision === "Otro" &&
        (!item.observation ||
         item.observation.trim() === "")
    );

    if (invalidObservation) {
      alert("Debe ingresar observación para las opciones 'Otro'.");
      return;
    }

    console.log("ENVIADO AL BACKEND", {validations: pendingValidations});
    await confirmAllValidations({
      validations: pendingValidations
    }
    );

    // Actualizar pantalla sin recargar
    setValidations(prev =>
      prev.map(item => ({
        ...item,
        confirmed: 1
      }))
    );

    alert(
      "Todas las validaciones fueron confirmadas correctamente"
    );


  } catch(error){
    console.error(
      "Error confirmando todas las validaciones:",
      error
    );
    if(
      error.response &&
      error.response.data &&
      error.response.data.detail
    )
    {
      alert(error.response.data.detail);
    }
    else{
    alert("No se pudieron confirmar las validaciones");
    }
    
  }
};
  
  const totalPages = Math.ceil(
    validations.length / rowsPerPage
  );


  const paginatedValidations =
  validations.slice(
    (currentPage - 1) * rowsPerPage,
    currentPage * rowsPerPage
  );

  const getSemaphore = () => {

  if(!campaignStatus){ return null; }
    
  const config = { 
  verde: { 
      color:"bg-green-500",
      text:"En plazo"
  },

  amarillo:{
      color:"bg-yellow-400",
      text:"Próximo a vencer"
  },

  rojo:{
      color:"bg-red-500",
      text:"Tiempo agotado"
  }};

  return config[campaignStatus.semaforo];
  };

  return (
    <div>
      <h1 className="text-2xl font-bold">Dashboard Gerente</h1>

      <p className="mt-1 text-slate-500">
        Selecciona tu nombre y valida únicamente las VPN o comunidades asignadas.
      </p>

      <div className="mt-6 rounded-2xl border border-blue-200 bg-blue-50 p-5">
        <label className="mr-4 text-sm font-bold text-slate-700">
          Seleccionar gerente
        </label>

        <select
          value={selectedManager}
          onChange={(event) => setSelectedManager(event.target.value)}
          className="h-12 w-full max-w-md rounded-xl border border-blue-300 bg-white px-4 outline-none"
        >
          <option value="">Seleccionar gerente</option>

          {managers.map((manager) => (
            <option key={manager.id} value={manager.name}>
              {manager.name}
            </option>
          ))}
        </select>
      </div>
      <div className="mt-4 rounded-2xl border border-amber-200 bg-amber-50 p-5">
        <h3 className="text-base font-bold text-amber-800">
          Instrucciones para la validación
        </h3>

        <ul className="mt-3 list-disc space-y-2 pl-5 text-sm text-amber-700">
          <li>
            Seleccione correctamente su nombre en el campo <b>Seleccionar gerente</b>.
          </li>
          <li>
            Solo podrá visualizar y validar las VPN o comunidades asignadas a su nombre.
          </li>
          <li>
            En la columna <b>Decisión</b>, seleccione una opción: Mantener, Eliminar,
            No pertenece u Otro.
          </li>
          <li>
            El campo <b>Observación</b> solo se habilita cuando se selecciona la opción
            <b> Otro</b>.
          </li>
          <li>
            Si selecciona <b>Otro</b>, la observación es obligatoria. Si no escribe una
            observación, el sistema no permitirá guardar la validación.
          </li>
        </ul>
      </div>
      <div className="mt-6 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="mb-5 flex items-center justify-between flex-wrap gap-4">
          {campaignStatus && (
            <div className= "order-1 flex items-center gap-3">
              <span className={`h-4 w-4 rounded-full 
                ${getSemaphore().color}`}>
              </span>
              <div>
                <p className="font-bold">
                  Estado de campaña:
                  {
                    getSemaphore().text
                  }
                </p>
                <p className="text-sm text-slate-500">
                  Fecha límite:
                  {
                    campaignStatus.fecha_limite
                  }
                  (
                  {
                    campaignStatus.dias_restantes
                  }
                    -días restantes
                  )
                </p>
                </div>
              </div>
          )}
          <h3 className= "order-2 text-lg font-bold">
            Cliente VPN Externos</h3>
        <button

          disabled={campaignExpired}
          onClick={handleSaveAll}

          className={`order-3 flex items-center gap-2 rounded-lg px-5 py-2 font bold text-white ${ campaignExpired
          ?  "bg-slate-400 cursor-not-allowed" : "bg-amber-500 hover:bg-amber-600"}`}>
         
          <Save size={16}/>
          { campaignExpired ? "Campaña cerrada" : "Guardar todas" }
          
        </button>
      </div>

        {!selectedManager ? (
          <div className="rounded-xl bg-slate-50 p-8 text-center text-slate-500">
            Selecciona un gerente para visualizar la información asignada.
          </div>
        ) : !isOwnManager ? (
          <div className="rounded-xl border border-red-200 bg-red-50 p-8 text-center">
            <h3 className="text-lg font-bold text-red-700">
              Acceso restringido
            </h3>
            <p className="mt-2 text-red-600">
              No puedes visualizar ni validar VPN asignadas a otro gerente.
            </p>
          </div>
        ) : validations.length === 0 ? (
          <div className="rounded-xl bg-slate-50 p-8 text-center text-slate-500">
            No existen registros asignados a este gerente.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[1000px] border-collapse text-sm">
              <thead>
                <tr className="bg-slate-50 text-left">
                  
                  <th className="border-b border-slate-200 p-4">VPN</th>
                  <th className="border-b border-slate-200 p-4">
                    Nombre VPN
                  </th>
                  <th className="border-b border-slate-200 p-4">
                    Gerente Asignado
                  </th>
                  <th className="border-b border-slate-200 p-4">Decisión</th>
                  <th className="border-b border-slate-200 p-4">
                    Observación
                  </th>
                  <th className="border-b border-slate-200 p-4">Confirmación</th>
                  <th className="border-b border-slate-200 p-4">
                    Fecha Límite
                  </th>
                  <th className="border-b border-slate-200 p-4">Guardar</th>
                </tr>
              </thead>

              <tbody>
                {paginatedValidations.map((item) => (
                  <tr key={item.id} className="hover:bg-slate-50">

                    <td className="border-d border-slate-100 p-4">
                      {item.req}
                    </td>

                    <td className="border-b border-slate-100 p-4">
                      {item.nombre_vpn || "-"}
                    </td>
                  
                    <td className="border-b border-slate-100 p-4">
                      {item.manager}
                    </td>

                    

                    <td className="border-b border-slate-100 p-4">
                      <select
                        value={item.decision || ""}
                        disabled={
                          campaignExpired ||
                          (
                          item.confirmed === 1 &&
                          editingId !== item.id
                          )
                        }
                        onChange={(event)=>
                          handleChange(
                            item.id,
                            "decision",
                            event.target.value
                          )
                        }
                        className="h-10 rounded-lg border border-slate-300 px-3 outline-none bg-white"
                      >
                        <option value="">Seleccionar</option>
                        <option value="Mantener">Mantener</option>
                        <option value="Eliminar">Eliminar</option>
                        <option value="No pertenece">No pertenece</option>
                        <option value="Otro">Otro</option>
                      </select>
                      
                    </td>

                    <td className="border-b border-slate-100 p-4">
                      <input
                        value={item.observation}
                        onChange={(event) =>
                          handleChange(
                            item.id,
                            "observation",
                            event.target.value
                          )
                        }
                        disabled={
                          campaignExpired ||
                            item.decision !== "Otro" ||
                            (
                            item.confirmed === 1 &&
                            editingId !== item.id
                            )
                          }
                        placeholder={
                          item.decision === "Otro"
                            ? "Ingrese observación"
                            : "Bloqueado"
                        }
                        className={`h-10 w-64 rounded-lg border px-3 outline-none ${
                          item.decision === "Otro"
                            ? "border-slate-300 bg-white"
                            : "cursor-not-allowed border-slate-200 bg-slate-100 text-slate-400"
                        }`}
                      />
                    </td>
                    
                    <td className="border-b border-slate-100 p-4">
                        {item.confirmed === 1 ? "Confirmado" : "Pendiente"}
                      </td>

                    <td className="border-b border-slate-100 p-4">
                      {item.fecha_limite || item.deadline}
                    </td>

                    <td className="border-b border-slate-100 p-4">
                      <button
                        disabled={campaignExpired}
                          onClick={() => {

                          if(campaignExpired){
                              return;
                          }
                          if(item.confirmed === 1 && editingId !== item.id){
                              setEditingId(item.id);
                          }else{
                              saveValidation(item);
                          }

                          }}
                          className={` flex items-center gap-2 rounded-lg px-4 py-2 font-bold text-white ${
                          campaignExpired ? "bg-slate-400 cursor-not-allowed" : item.confirmed === 1 && editingId !== item.id ?
                          "bg-green-600 hover:bg-green-700" : "bg-amber-500 hover:bg-amber-600" } `} >

                        <Save size={16}/>
                        {
                          campaignExpired ? "Bloqueado" :
                        item.confirmed === 1 && editingId !== item.id
                        ? "Modificar"
                        : "Guardar"
                        }

                        </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
              
          </div>
        )}
        <Pagination
              currentPage={currentPage}
              totalPages={totalPages}
              onPageChange={setCurrentPage}
              />
      </div>
    </div>
  );
}
