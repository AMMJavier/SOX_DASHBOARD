

import { useState } from "react";
import Control6Repository from "../../../components/SOX/control_6/Control6Repository";
import LdapCortesTable from "../../../components/SOX/control_6/LdapCortesTable";
import Control6Conciliation from "../../../components/SOX/control_6/Control6Conciliation";
import { useSearchParams } from "react-router-dom";
import { LockKeyhole, Users } from "lucide-react";
import ControlReminderPanel from "../../../components/SOX/common/ControlReminderPanel";
import { ControlHeading, EvidenceKpis, InfoBanner, Panel, RequirementList, StepList, FIELD } from "../../../components/SOX/common/ControlUI";

const activity = "El Ingeniero Líder de Infraestructura TI contrasta la relación de personal cesante recibida desde Recursos Humanos con la lista de usuarios internos con acceso VPN. Cuando se confirma un acceso que corresponde eliminar, debe conservarse la evidencia de la baja y remitirse un informe al Jefe de Infraestructura TI.";
const steps = [
  "Registrar la fuente y el periodo de los cesantes informados por Recursos Humanos.",
  "Obtener un corte autorizado de accesos internos desde SASE y/o los directorios LDAP pertinentes.",
  "Conciliar identificadores confiables y separar coincidencias, ambigüedades y cuentas sin correspondencia.",
  "Revisar los accesos identificados: los hallazgos no implican baja automática.",
  "Ejecutar bajas aprobadas en los sistemas correspondientes, conservar su evidencia y emitir informe a Jefatura.",
];
const VIEWS = [
  ["resumen", "Resumen"], ["conciliacion", "Conciliación"],
  ["evidencias", "Evidencias"], ["historial", "Historial"], ["alertas", "Recordatorios"],
];

export default function Control_6() {
  const [params, setParams] = useSearchParams();
  const view = VIEWS.some(([key]) => key === params.get("vista")) ? params.get("vista") : "resumen";
  const setView = (next) => setParams((previous) => { const p = new URLSearchParams(previous); p.set("vista", next); return p; });
  const [mailYear, setMailYear] = useState(String(new Date().getFullYear()));
  const [mailSemester, setMailSemester] = useState("1");
  return <div className="space-y-6 pb-10">
    <ControlHeading number={6} title="Conciliación de cesantes y VPN internas" frequency="Por validar con RR. HH." responsible="Ingeniero Líder de Infraestructura TI · Jefe de Infraestructura TI"
      description="Comparación entre los reportes de cesantes y la existencia de accesos internos. Los grupos RDP y aplicaciones pueden consultarse por LDAP si la configuración TLS corporativa lo permite. SASE continúa pendiente."/>
    <EvidenceKpis metrics={null}/>
    <InfoBanner caution>Este control no debe usar la tabla de VPN externas de Check Point del control 7. La reunión describió fuentes de accesos <strong>internos</strong>, incluyendo SASE y LDAP. Los grupos RDP y aplicaciones pueden consultarse por LDAP en modo solo lectura; no se ejecutan bajas ni se integra SASE.</InfoBanner>
    {/* En escritorio la navegación está en el sidebar; solo queda aquí para móvil. */}
    <nav aria-label="Secciones del control 6 (móvil)" className="flex flex-wrap gap-2 rounded-2xl border border-slate-200 bg-white p-2 shadow-sm lg:hidden">
      {VIEWS.map(([key, label]) => <button key={key} type="button" onClick={() => setView(key)} className={`rounded-xl px-4 py-2.5 text-sm font-semibold ${view === key ? "bg-blue-600 text-white" : "text-slate-600 hover:bg-slate-100"}`}>{label}</button>)}
    </nav>

    {view === "resumen" && <div className="grid gap-5 xl:grid-cols-5">
      <div className="space-y-5 xl:col-span-3">
        <Panel title="Actividad del control"><p className="mb-5 text-sm leading-7 text-slate-700">{activity}</p><StepList steps={steps}/></Panel>
        <Panel title="Fuentes involucradas">
          <div className="grid gap-3 sm:grid-cols-2">
            {[{ icon: Users, title: "Recursos Humanos", desc: "Correos, matriz de cesantes y movimientos autorizados." }, { icon: LockKeyhole, title: "Accesos internos", desc: "Listados SASE y LDAP / RDP / aplicaciones, según validación del equipo." }].map(({ icon: Icon, title, desc }) => <div key={title} className="rounded-xl border border-slate-200 bg-slate-50 p-4"><Icon className="text-blue-600"/><h3 className="mt-2 font-semibold">{title}</h3><p className="mt-1 text-sm text-slate-500">{desc}</p></div>)}
          </div>
        </Panel>
      </div>
      <div className="space-y-5 xl:col-span-2">
        <Panel title="Resultados esperados"><RequirementList items={[
          "Listado de cesantes y su fecha de corte.",
          "Listado de accesos internos y su origen.",
          "Coincidencias identificadas por cuenta inequívoca.",
          "Evidencia de bajas autorizadas y excepciones.",
          "Informe de conciliación enviado a Jefatura.",
        ]}/></Panel>
        <Panel title="Decisiones pendientes"><RequirementList items={[
          "Formato y fuente oficial de los cesantes.",
          "Qué movimientos de cargo implican revisar acceso.",
          "Identificador común entre RR. HH. y SASE/LDAP.",
          "Plazo y frecuencia de conciliación.",
        ]}/></Panel>
      </div>
    </div>}

    {view === "conciliacion" && <div className="space-y-5">
      <LdapCortesTable />
      <Control6Conciliation onViewEvidences={() => setView("evidencias")} />
    </div>}

    {view === "evidencias" && <Control6Repository />}
    {view === "historial" && <Control6Repository historyOnly />}
    {view === "alertas" && <div className="space-y-5">
      <Panel title="Período para recordatorio del Control 6" description="Configura el período y previsualiza antes de enviar.">
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="text-xs font-semibold text-slate-600">Año<input type="number" min="2020" max="2100" className={FIELD} value={mailYear} onChange={(e) => setMailYear(e.target.value)}/></label>
          <label className="text-xs font-semibold text-slate-600">Semestre<select className={FIELD} value={mailSemester} onChange={(e) => setMailSemester(e.target.value)}><option value="1">Primer semestre</option><option value="2">Segundo semestre</option></select></label>
        </div>
      </Panel>
      <ControlReminderPanel control={6} anio={mailYear} semestre={mailSemester}/>
    </div>}
  </div>;
}
