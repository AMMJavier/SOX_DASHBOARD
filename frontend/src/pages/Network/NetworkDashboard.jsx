import {
  Router,
  Wifi,
  AlertTriangle,
  CheckCircle
} from "lucide-react";


export default function NetworkDashboard(){

return (

<div>

<h1 className="text-3xl font-bold">
Dashboard Activos de Red
</h1>

<p className="text-slate-500 mt-1">
Monitoreo general de infraestructura de comunicaciones.
</p>


<div className="grid grid-cols-1 md:grid-cols-4 gap-5 mt-8">


<Kpi
title="Dispositivos"
value="245"
color="bg-cyan-500"
icon={Router}
/>


<Kpi
title="Operativos"
value="220"
color="bg-green-600"
icon={CheckCircle}
/>


<Kpi
title="Alertas"
value="18"
color="bg-orange-500"
icon={AlertTriangle}
/>


<Kpi
title="Caídos"
value="7"
color="bg-red-600"
icon={Wifi}
/>


</div>


<div className="
mt-8
bg-white
rounded-2xl
border
p-6
">


<h2 className="text-xl font-bold">
Equipos recientes
</h2>


<table className="w-full mt-5">

<thead className="bg-slate-50">

<tr>

<th className="p-3 text-left">
Equipo
</th>

<th>
Tipo
</th>

<th>
Ubicación
</th>

<th>
Estado
</th>

</tr>

</thead>


<tbody>


<tr>
<td className="p-3">
RTR-001
</td>

<td>
Router Cisco
</td>

<td>
Quito
</td>

<td>
Operativo
</td>

</tr>


<tr>

<td className="p-3">
SW-002
</td>

<td>
Switch
</td>

<td>
Data Center
</td>

<td>
Operativo
</td>


</tr>


</tbody>

</table>


</div>


</div>


)

}



function Kpi({title,value,color,icon:Icon}){


return (

<div className="
bg-white
border
rounded-2xl
p-6
">


<div className={`
h-14
w-14
rounded-full
${color}
flex
items-center
justify-center
text-white
`}>

<Icon size={30}/>

</div>


<p className="mt-4 font-bold text-slate-600">
{title}
</p>


<h2 className="text-3xl font-bold mt-2">
{value}
</h2>


</div>

)

}