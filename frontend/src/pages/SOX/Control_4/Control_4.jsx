import { CheckCircle2, FileText, ClipboardList, ShieldCheck } from "lucide-react";

/**
 * Control 4 — Vista informativa de un control ya atendido por Workflow.
 * Fuente: matriz SOIT-3 / EC-SE-SIS-03, fila C4.
 * Sin lógica de validación, consultas, formularios ni conexión a servicios.
 */
const pasos = [
  "El usuario de CONECEL registra en Workflow la solicitud de creación, modificación o eliminación de un acceso remoto, con las especificaciones requeridas.",
  "El Jefe de Infraestructura TI aprueba previamente la solicitud a través de Workflow.",
  "El Ingeniero de Infraestructura TI ejecuta la acción solicitada de acuerdo con las especificaciones aprobadas.",
  "Después de la configuración, se registra el evento en la bitácora de control de accesos remotos del firewall.",
  "El informe correspondiente de Workflow conserva la información de la creación, modificación o eliminación realizada.",
];

const puntos = [
  "La solicitud se origina y se gestiona mediante Workflow.",
  "La aprobación del Jefe de Infraestructura TI antecede a la ejecución.",
  "Las operaciones posibles son creación, modificación y eliminación del acceso remoto.",
  "El resultado se registra en la bitácora del firewall y se documenta en Workflow.",
];

function Tarjeta({ titulo, descripcion }) {
  return (
    <div className="flex items-start gap-3 rounded-xl border border-slate-200 bg-slate-50 px-4 py-4">
      <FileText className="mt-0.5 h-5 w-5 shrink-0 text-blue-600" aria-hidden="true" />
      <div>
        <p className="text-sm font-semibold text-slate-900">{titulo}</p>
        <p className="mt-1 text-sm leading-6 text-slate-600">{descripcion}</p>
      </div>
    </div>
  );
}

export default function ControlPilot({ control }) {
  return (
    <main className="space-y-5 pb-8">
      <header className="space-y-1">
        <p className="text-sm font-medium text-blue-600">SOX / Control 4</p>
        <h1 className="text-2xl font-bold tracking-tight text-slate-950 md:text-3xl">
          {control?.name || "Gestión de accesos remotos VPN"}
        </h1>
        <p className="max-w-5xl text-sm leading-6 text-slate-600">
          Procedimiento de creación, modificación y eliminación de accesos remotos mediante
          solicitudes aprobadas en Workflow y registro de las operaciones en el firewall.
        </p>
      </header>

      <div className="grid items-start gap-5 lg:grid-cols-[minmax(0,3fr)_minmax(320px,2fr)]">
        <div className="space-y-5">
          <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm md:p-6">
            <div className="mb-5">
              <h2 className="text-lg font-bold text-slate-950">Actividad del control</h2>
              <p className="mt-1 text-sm text-slate-500">Objetivo y procedimiento de gestión de accesos remotos.</p>
            </div>
            <p className="text-sm leading-7 text-slate-700">
              El Ingeniero de Infraestructura TI crea, modifica o elimina accesos remotos
              conforme a las solicitudes generadas por los usuarios de CONECEL en Workflow.
              Cada solicitud debe contar con la aprobación previa del Jefe de Infraestructura TI.
              Una vez ejecutada, la operación se registra en la bitácora de accesos remotos
              configurados en el firewall.
            </p>
            <ol className="mt-5 space-y-3">
              {pasos.map((paso, i) => (
                <li key={i} className="flex items-start gap-3 text-sm leading-6 text-slate-700">
                  <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-blue-100 text-sm font-semibold text-blue-700">
                    {i + 1}
                  </span>
                  <span className="pt-0.5">{paso}</span>
                </li>
              ))}
            </ol>
          </section>

          <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm md:p-6">
            <h2 className="text-lg font-bold text-slate-950">Evidencias y registros del procedimiento</h2>
            <p className="mt-1 mb-5 text-sm text-slate-500">
              Información que se conserva en los sistemas donde ya se realiza el control.
            </p>
            <div className="grid gap-3 md:grid-cols-2">
              <Tarjeta
                titulo="Informe de Workflow"
                descripcion="Evidencia indicada en la matriz: informe con la información de la creación, modificación o eliminación del acceso remoto."
              />
              <Tarjeta
                titulo="Bitácora de accesos remotos"
                descripcion="Registro operativo de la acción ejecutada en los accesos remotos configurados en el firewall."
              />
            </div>
          </section>
        </div>

        <aside className="space-y-5">
          <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm md:p-6">
            <div className="mb-5 flex items-center gap-2">
              <ClipboardList className="h-5 w-5 text-blue-600" aria-hidden="true" />
              <h2 className="text-lg font-bold text-slate-950">Puntos principales del control</h2>
            </div>
            <ul className="space-y-4">
              {puntos.map((punto, i) => (
                <li key={i} className="flex items-start gap-3 text-sm leading-6 text-slate-700">
                  <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-blue-600" aria-hidden="true" />
                  <span>{punto}</span>
                </li>
              ))}
            </ul>
          </section>
          <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm md:p-6">
            <div className="mb-3 flex items-center gap-2">
              <ShieldCheck className="h-5 w-5 text-blue-600" aria-hidden="true" />
              <h2 className="text-lg font-bold text-slate-950">Riesgo que aborda</h2>
            </div>
            <p className="text-sm leading-7 text-slate-700">
              Falta de procedimientos y medios para identificar y autenticar a usuarios
              internos y externos antes de otorgarles acceso a los sistemas de TI.
            </p>
          </section>
        </aside>
      </div>
    </main>
  );
}

