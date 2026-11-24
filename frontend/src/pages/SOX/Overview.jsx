import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  AlertTriangle, ArrowRight, CalendarDays, CheckCircle2, Clock3, FileText, Mail, MailCheck, RefreshCw, Users,
} from "lucide-react";
import { api } from "../../services/api";
import controlConfig from "../../constants/controlConfig";
import { formatDateTime } from "../../utils/dateTime";

const errorText = (e) => e?.response?.data?.detail || e?.message || "No se pudo cargar el resumen.";
const day = (v) => (v ? formatDateTime(v, { seconds: false, assumeUtc: false }).slice(0, 10) : "");
const sentDay = (v) => (v ? formatDateTime(v, { seconds: false }).slice(0, 10) : ""); // fechas de envío: UTC

const TONE = {
  ok: { dot: "bg-emerald-500", chip: "bg-emerald-50 text-emerald-700", text: "text-emerald-700" },
  warn: { dot: "bg-amber-400", chip: "bg-amber-50 text-amber-800", text: "text-amber-700" },
  bad: { dot: "bg-red-500", chip: "bg-red-50 text-red-700", text: "text-red-700" },
  none: { dot: "bg-slate-300", chip: "bg-slate-100 text-slate-600", text: "text-slate-500" },
};

/** Estado general del control para el semáforo de la tarjeta. */
function overall(c) {
  if (c.error) return ["bad", "Sin datos"];
  if (c.control === 7) {
    if (!c.campana) return ["none", "Sin campaña activa"];
    const pending = c.externas.pendientes + c.internas.pendientes;
    if (pending === 0) return ["ok", "Validación completa"];
    return c.vencido ? ["bad", "Campaña vencida"] : ["warn", "En validación"];
  }
  const confirmed = c.confirmacion?.estado === "APROBADO";
  if ([1, 2, 3].includes(c.control) ? confirmed : c.evidencias > 0) return ["ok", "Al día"];
  if (c.vencido) return ["bad", "Fecha tope vencida"];
  return ["warn", "Pendiente"];
}

function Row({ icon: Icon, label, value, tone = "none" }) {
  return <div className="flex items-start justify-between gap-3 border-t border-slate-100 py-2.5 text-sm">
    <span className="flex items-center gap-2 text-slate-600"><Icon size={16} className="shrink-0 text-slate-400"/>{label}</span>
    <span className={`text-right font-semibold ${TONE[tone].text}`}>{value}</span>
  </div>;
}

function Progress({ label, data }) {
  const pct = data.total ? Math.round((data.confirmadas / data.total) * 100) : 0;
  return <div className="border-t border-slate-100 py-2.5 text-sm">
    <div className="flex justify-between gap-3"><span className="text-slate-600">{label}</span>
      <span className="font-semibold">{data.confirmadas} / {data.total} confirmadas ({pct}%)</span></div>
    <div className="mt-1.5 h-2 rounded-full bg-slate-100"><div className="h-2 rounded-full bg-emerald-500" style={{ width: `${pct}%` }}/></div>
    <p className="mt-1 text-xs text-slate-500">{data.pendientes} por validar{data.reportadas ? ` · ${data.reportadas} en revisión (Otro / No pertenece)` : ""}
      {" · "}gerentes notificados: <b>{data.gerentes_notificados} de {data.gerentes}</b></p>
  </div>;
}

function deadlineRow(c) {
  if (!c.fecha_tope) return <Row icon={CalendarDays} label="Fecha tope" value="Sin fecha tope"/>;
  const tone = c.vencido ? "bad" : c.dias_restantes <= 7 ? "warn" : "none";
  const rest = c.vencido ? "vencida" : `${c.dias_restantes} día(s)`;
  return <Row icon={CalendarDays} label="Fecha tope" value={`${day(c.fecha_tope)} · ${rest}`} tone={tone}/>;
}

function confirmationRow(c) {
  const state = c.confirmacion?.estado;
  if (!state) return <Row icon={MailCheck} label="Correo de confirmación" value="Sin correo enviado" tone="warn"/>;
  if (state === "APROBADO") return <Row icon={MailCheck} label="Correo de confirmación" value={`Recibido${c.confirmacion.fecha ? ` · ${sentDay(c.confirmacion.fecha)}` : ""}`} tone="ok"/>;
  if (state === "RESPONDIDO") return <Row icon={MailCheck} label="Correo de confirmación" value="Respondido · revisar" tone="warn"/>;
  return <Row icon={MailCheck} label="Correo de confirmación" value={`Esperando respuesta (${c.confirmacion.codigo})`} tone="warn"/>;
}

function ControlCard({ c, onOpen }) {
  const [tone, status] = overall(c);
  return <article className="flex flex-col rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
    <div className="flex items-start justify-between gap-3">
      <div>
        <p className="text-sm font-semibold text-blue-600">Control {c.control}</p>
        <h3 className="mt-0.5 text-lg font-bold leading-6 text-slate-900">{c.nombre}</h3>
      </div>
      <span className={`flex shrink-0 items-center gap-1.5 rounded-full px-3 py-1 text-xs font-bold ${TONE[tone].chip}`}>
        <span className={`h-2 w-2 rounded-full ${TONE[tone].dot}`}/>{status}</span>
    </div>
    <p className="mb-2 mt-2 text-sm text-slate-500">{c.periodo || "—"}{c.frecuencia ? ` · ${c.frecuencia}` : ""}{c.campana ? ` · ${c.campana}` : ""}</p>

    <div className="flex-1">
      {c.error ? <p className="rounded-lg bg-red-50 p-3 text-sm text-red-700">No se pudo leer este control: {c.error}</p>
        : c.control === 7 ? (c.campana ? <>
          {deadlineRow(c)}
          <Progress label="VPN externas" data={c.externas}/>
          <Progress label="VPN internas" data={c.internas}/>
          <Row icon={Mail} label="Notificación a gerentes"
            value={(() => { const n = c.externas.gerentes_notificados + c.internas.gerentes_notificados;
              const t = c.externas.gerentes + c.internas.gerentes;
              return t === 0 ? "Sin gerentes" : n === 0 ? "No enviada" : n >= t ? "Enviada a todos" : `Enviada a ${n} de ${t}`; })()}
            tone={c.externas.gerentes_notificados + c.internas.gerentes_notificados === 0 ? "warn"
              : c.externas.gerentes_por_notificar + c.internas.gerentes_por_notificar > 0 ? "warn" : "ok"}/>
        </> : <p className="rounded-lg bg-slate-50 p-3 text-sm text-slate-600">No hay una campaña activa. Se inicia desde el Control 7.</p>)
        : <>
          {deadlineRow(c)}
          <Row icon={Mail} label="Notificación" value={c.notificacion ? (c.notificacion.enviada ? `Enviada · ${sentDay(c.notificacion.fecha)}` : `No enviada (${c.notificacion.estado})`) : "No enviada"}
            tone={c.notificacion?.enviada ? "ok" : "warn"}/>
          <Row icon={FileText} label="Correo formal" value={c.correo_formal ? (c.correo_formal.enviado ? `Enviado · ${sentDay(c.correo_formal.fecha)}` : `No enviado (${c.correo_formal.estado})`) : "No enviado"}
            tone={c.correo_formal?.enviado ? "ok" : "none"}/>
          {[1, 2, 3, 5].includes(c.control) && confirmationRow(c)}
          <Row icon={CheckCircle2} label="Evidencias del período" value={c.evidencias} tone={c.evidencias ? "ok" : "warn"}/>
          {c.control === 6 && <Row icon={Users} label="Conciliación del semestre"
            value={c.conciliacion ? `${sentDay(c.conciliacion.fecha)} · ${c.conciliacion.coincidencias} coincidencia(s)` : "Sin conciliación"}
            tone={c.conciliacion ? "ok" : "warn"}/>}
          {c.alerta?.enviada && <Row icon={AlertTriangle} label="Alerta de evidencia faltante" value={`Enviada · ${sentDay(c.alerta.fecha)}`} tone="bad"/>}
        </>}
    </div>

    <button type="button" onClick={() => onOpen(c.control)}
      className="mt-4 flex w-full items-center justify-center gap-2 rounded-xl bg-slate-900 px-4 py-2.5 text-sm font-bold text-white hover:bg-slate-800">
      Abrir Control {c.control}<ArrowRight size={16}/></button>
  </article>;
}

/** Pantalla de inicio del portal SOX: estado de todos los controles y acceso a cada uno. */
export default function Overview() {
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const load = () => {
    setLoading(true);
    api.get("/sox/resumen").then((r) => { setData(r.data); setError(""); })
      .catch((e) => setError(errorText(e))).finally(() => setLoading(false));
  };
  useEffect(load, []);

  const controls = data?.controles || [];
  const tones = controls.map((c) => overall(c)[0]);
  const count = (t) => tones.filter((x) => x === t).length;

  return <div>
    <div className="flex flex-wrap items-start justify-between gap-4">
      <div>
        <h1 className="text-2xl font-bold">Resumen general SOX</h1>
        <p className="mt-1 text-slate-500">Estado del período vigente de cada control. Elige un control para trabajar en él.</p>
      </div>
      <button type="button" onClick={load} disabled={loading}
        className="flex h-11 items-center gap-2 rounded-lg border border-slate-300 bg-white px-4 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-60">
        <RefreshCw size={16} className={loading ? "animate-spin" : ""}/>Actualizar</button>
    </div>

    {error && <p className="mt-4 rounded-xl bg-red-50 p-3 text-sm text-red-700">{error}</p>}

    <div className="mt-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
      {[["Controles", controls.length, "text-slate-900", FileText], ["Al día", count("ok"), "text-emerald-700", CheckCircle2],
        ["Pendientes", count("warn") + count("none"), "text-amber-700", Clock3], ["Vencidos / sin datos", count("bad"), "text-red-700", AlertTriangle]]
        .map(([label, value, color, Icon]) => <div key={label} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <p className="flex items-center gap-2 text-sm font-semibold text-slate-500"><Icon size={16}/>{label}</p>
          <p className={`mt-1 text-3xl font-bold ${color}`}>{data ? value : "—"}</p>
        </div>)}
    </div>

    {!data && !error && <p className="mt-6 rounded-xl bg-white p-8 text-center text-slate-500">Cargando el estado de los controles...</p>}
    <div className="mt-6 grid grid-cols-1 gap-5 lg:grid-cols-2 2xl:grid-cols-3">
      {controls.map((c) => <ControlCard key={c.control} c={c} onOpen={(n) => navigate(controlConfig[n]?.path || "/SOX/resumen")}/>)}
    </div>
  </div>;
}
