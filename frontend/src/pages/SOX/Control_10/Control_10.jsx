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
                El Workflow de Infraestructura emitira un correo  automaticamente al momento de generar la VPN 
                dicho correo contendra un archivo  con clave  robusta por seguridad  en la que contendra 
                los paramentros de la VPN con su respectivo PRESHARED SECRET la clave de este archivo se lo dara unicamente 
                via skype o por llamada telefonica a quien configure la VPN para asi poder establecer el tunel.
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
                 Informacion que se encuentra en Workflow dentro de Informe con la evidencia del archivo encriptado
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