import { useEffect, useState } from "react";
import { AlertTriangle, CheckCircle, ClipboardList, Clock, Network } from "lucide-react";
import Pagination from "../../../../components/common/Pagination";
import { errorText, getInternalDashboard } from "../../../../services/sox/control_7/internalVpnService";

/** Dashboard de VPN internas: mismo diseño que el Dashboard Administrador SOX de VPN externas. */
export default function InternalDashboard() {
  const [manager, setManager] = useState("");
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [page, setPage] = useState(1);
  const perPage = 5;

  useEffect(() => {
    getInternalDashboard(manager).then((d) => { setData(d); setError(""); })
      .catch((e) => setError(errorText(e, "No se pudo cargar el dashboard de VPN internas.")));
  }, [manager]);

  const k = data?.kpis || {};
  const total = k.total || 0;
  const percent = total ? Math.round(((k.confirmed || 0) / total) * 100) : 0;
  const responsibles = (data?.responsables || []).map((r) => ({ ...r, percent: r.total ? Math.round((r.confirmed / r.total) * 100) : 0 }));
  const pages = Math.ceil(responsibles.length / perPage);
  const visible = responsibles.slice((page - 1) * perPage, page * perPage);

  return (
    <div>
      <h1 className="text-2xl font-bold">Dashboard Administrador SOX · VPN internas</h1>
      <p className="mt-1 text-slate-500">Resumen ejecutivo de la campaña activa: cuentas en los grupos LDAP RDP y Aplicaciones.</p>
      {error && <p className="mt-4 rounded-xl bg-amber-50 p-3 text-sm text-amber-800">{error}</p>}
      {data && !data.campana && <p className="mt-4 rounded-xl bg-amber-50 p-3 text-sm text-amber-800">No hay una campaña activa.</p>}

      <div className="mt-5 flex items-center gap-3">
        <label className="font-bold" htmlFor="internal-manager">Gerente:</label>
        <select id="internal-manager" className="rounded-lg border border-slate-300 px-4 py-2" value={manager}
          onChange={(e) => { setManager(e.target.value); setPage(1); }}>
          <option value="">Todos los gerentes</option>
          {(data?.gerentes || []).map((g) => <option key={g.usuario} value={g.usuario}>{g.nombre}</option>)}
        </select>
      </div>

      <div className="mt-6 grid grid-cols-1 gap-5 md:grid-cols-2 xl:grid-cols-5">
        <Kpi title="Total Registros" value={total} color="bg-blue-600" icon={ClipboardList}/>
        <Kpi title="Confirmados" value={k.confirmed || 0} color="bg-green-600" icon={CheckCircle}/>
        <Kpi title="Pendientes" value={k.pending || 0} color="bg-amber-500" icon={Clock}/>
        <Kpi title="Vencidos" value={k.expired || 0} color="bg-red-600" icon={AlertTriangle}/>
        {/* Mismo cuadro, un tipo de acceso por línea para que no se confundan. */}
        <Kpi title="RDP y Aplicaciones" color="bg-indigo-600" icon={Network}>
          <div className="mt-2 space-y-1">
            <div className="flex items-baseline justify-between gap-3"><span className="text-sm font-semibold text-slate-600">RDP</span><span className="text-2xl font-bold">{k.rdp || 0}</span></div>
            <div className="flex items-baseline justify-between gap-3 border-t border-slate-100 pt-1"><span className="text-sm font-semibold text-slate-600">Aplicaciones</span><span className="text-2xl font-bold">{k.aplicaciones || 0}</span></div>
            {/* Suma: debe coincidir con "Total Registros". */}
            <div className="flex items-baseline justify-between gap-3 border-t-2 border-slate-300 pt-1"><span className="text-sm font-bold text-slate-800">Total</span><span className="text-2xl font-bold text-indigo-700">{(k.rdp || 0) + (k.aplicaciones || 0)}</span></div>
          </div>
        </Kpi>
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 xl:grid-cols-2">
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <h3 className="text-lg font-bold">Avance General de Validación</h3>
          <div className="mt-6 flex items-center gap-10">
            <div className="flex h-56 w-56 items-center justify-center rounded-full"
              style={{ background: `conic-gradient(#16a34a ${percent}%, #f59e0b ${percent}% 100%)` }}>
              <div className="flex h-36 w-36 flex-col items-center justify-center rounded-full bg-white">
                <span className="text-4xl font-bold">{percent}%</span>
                <span className="text-sm text-slate-500">Avance general</span>
              </div>
            </div>
            <div className="flex-1 space-y-4">
              <Legend color="bg-green-600" label="Confirmados" value={k.confirmed || 0}/>
              <Legend color="bg-amber-500" label="Pendientes" value={k.pending || 0}/>
              <Legend color="bg-red-600" label="Vencidos" value={k.expired || 0}/>
              <Legend color="bg-purple-600" label="Sin Responsable" value={k.no_owner || 0}/>
              <Legend color="bg-slate-700" label="Marcados para eliminar" value={k.eliminar || 0}/>
            </div>
          </div>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <h3 className="text-lg font-bold">Avance por Responsable</h3>
          <div className="mt-6 space-y-5">
            {visible.map((item) => (
              <div key={item.usuario}>
                <div className="mb-2 flex justify-between text-sm">
                  <span>{item.manager}</span>
                  <b>{item.percent}% ({item.confirmed} / {item.total})</b>
                </div>
                <div className="h-2 rounded-full bg-slate-200">
                  <div className={`h-2 rounded-full ${item.percent > 0 ? "bg-green-600" : "bg-slate-200"}`} style={{ width: `${item.percent}%` }}/>
                </div>
              </div>
            ))}
            {responsibles.length === 0 && <p className="text-sm text-slate-500">No hay responsables para mostrar en la campaña activa.</p>}
            {pages > 1 && <Pagination currentPage={page} totalPages={pages} onPageChange={setPage}/>}
          </div>
        </div>
      </div>
    </div>
  );
}

function Kpi({ title, value, color, icon: Icon, children }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className={`mb-4 flex h-14 w-14 items-center justify-center rounded-full ${color}`}><Icon size={30} className="text-white"/></div>
      <p className="text-sm font-bold text-slate-700">{title}</p>
      {children || <h2 className="mt-2 text-3xl font-bold">{value}</h2>}
    </div>
  );
}

function Legend({ color, label, value }) {
  return (
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-3"><span className={`h-4 w-4 rounded ${color}`}/><span>{label}</span></div>
      <b>{value}</b>
    </div>
  );
}
