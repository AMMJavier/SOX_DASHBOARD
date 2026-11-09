import {
 Wrench,
 CheckCircle,
 Clock,
 AlertTriangle
} from "lucide-react";

import { maintenanceSummary, maintenanceOrders } from "../../data/maintenanceData";
export default function MaintenanceDashboard(){

return (

<div>


<h1 className="text-3xl font-bold">
Dashboard Mantenimiento
</h1>


<p className="text-slate-500">
Gestión preventiva y correctiva de activos tecnológicos.
</p>



<div className="grid md:grid-cols-4 gap-5 mt-8">


<Card
title="Total órdenes"
value={maintenanceSummary.total}
color="bg-orange-500"
icon={Wrench}
/>


<Card
title="Completadas"
value={maintenanceSummary.completed}
color="bg-green-600"
icon={CheckCircle}
/>


<Card
title="Pendientes"
value={maintenanceSummary.pending}
color="bg-yellow-500"
icon={Clock}
/>


<Card
title="Críticas"
value={maintenanceSummary.critical}
color="bg-red-600"
icon={AlertTriangle}
/>


</div>
<div className="mt-8 rounded-2xl border bg-white p-6">

<h2 className="text-lg font-bold mb-5">
Órdenes recientes
</h2>


<table className="w-full">

<thead>
<tr className="text-left text-sm text-slate-500">

<th>Código</th>
<th>Activo</th>
<th>Tipo</th>
<th>Técnico</th>
<th>Ubicación</th>
<th>Estado</th>

</tr>
</thead>


<tbody>

{maintenanceOrders.map((order)=>(

<tr 
key={order.id}
className="border-t"
>

<td className="py-3 font-bold">
{order.id}
</td>

<td>
{order.asset}
</td>

<td>
{order.type}
</td>

<td>
{order.technician}
</td>

<td>
{order.location}
</td>

<td>
{order.status}
</td>

</tr>

))}


</tbody>


</table>

</div>

</div>


)

}



function Card({title,value,color,icon:Icon}){

return (

<div className="bg-white rounded-2xl border p-6">


<div className={`
${color}
w-14 h-14
rounded-full
flex
items-center
justify-center
text-white
`}>

<Icon/>

</div>


<p className="mt-4 font-bold">
{title}
</p>


<h2 className="text-3xl font-bold">
{value}
</h2>


</div>

)



}