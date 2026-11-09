import {
  ShieldCheck,
  Clock,
  FileText
} from "lucide-react";


export default function ControlPilot({control}) {

  return (
    
    <div>

      <h1 className="text-3xl font-bold">
        {control.name}
      </h1>

      <p className="mt-2 text-slate-500">
        Módulo de validación SOX pendiente de implementación.
      </p>


     <div className="grid md:grid-cols-2 gap-6 mt-8">

        {/* ACTIVIDAD DEL CONTROL */}
        <div
            className="
            rounded-2xl
            border
            bg-white
            p-6
            "
        >

            <h2 className="font-bold text-lg text-slate-800">
                Actividad del control
            </h2>

            <p className="mt-3 text-slate-600 leading-relaxed">
                El Ingeniero de Infraestructura TI ejecuta la creación,
                modificación o eliminación de acceso remoto en base a las
                especificaciones de la solicitud emitida por Workflow.
                La solicitud debe estar previamente aprobada por el Jefe de
                Infraestructura TI antes de realizar la configuración.
            </p>

        </div>


        {/* EVIDENCIA DEL CONTROL */}
        <div
            className="
            rounded-2xl
            border
            bg-white
            p-6
            "
        >

            <h2 className="font-bold text-lg text-slate-800">
                Evidencia del control
            </h2>

            <p className="mt-3 text-slate-600 leading-relaxed">
                La evidencia se encuentra en Workflow dentro del informe
                correspondiente, donde se almacena la información relacionada
                con la creación, modificación o eliminación de la VPN.
            </p>

        </div>

    </div>
  </div>

  );
}



function Card({icon:Icon,title,value}){

return (

<div className="
bg-white
border
rounded-2xl
p-6
">

<div className="
bg-blue-600
text-white
w-12
h-12
rounded-full
flex
items-center
justify-center
">

<Icon/>

</div>


<p className="mt-4 font-bold">
{title}
</p>


<h2 className="text-2xl font-bold">
{value}
</h2>


</div>

)

}