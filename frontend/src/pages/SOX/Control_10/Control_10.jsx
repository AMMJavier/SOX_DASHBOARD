import { CheckCircle2, FileText, ClipboardList, ShieldCheck } from "lucide-react";

/**
 * Control 10 — Vista informativa de un procedimiento ya automatizado en Workflow.
 * Fuente: matriz SOIT-3 / EC-SE-SIS-03, fila C10.
 * No envía correos, genera VPN ni administra contraseñas o secretos.
 */
const pasos = [
  "Al generarse una VPN, Workflow de Infraestructura emite automáticamente un correo electrónico.",
  "El correo contiene un archivo protegido por una contraseña robusta con los parámetros de la VPN, incluido el secreto precompartido (PRESHARED SECRET).",
  "La contraseña del archivo se comunica por separado, únicamente a la persona que configura la VPN, mediante Skype o llamada telefónica.",
  "La información recibida permite realizar la configuración necesaria para establecer el túnel VPN.",
  "El informe de Workflow conserva la evidencia del archivo cifrado asociado a la generación de la VPN.",
];

const puntos = [
  "El correo se genera automáticamente desde Workflow cuando se crea la VPN.",
  "Los parámetros de conexión se entregan dentro de un archivo protegido.",
  "La contraseña de apertura se comunica por un canal separado del correo.",
  "La evidencia del archivo cifrado queda disponible en el informe de Workflow.",
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
        <p className="text-sm font-medium text-blue-600">SOX / Control 10</p>
        <h1 className="text-2xl font-bold tracking-tight text-slate-950 md:text-3xl">
          {control?.name || "Entrega protegida de parámetros de VPN"}
        </h1>
        <p className="max-w-5xl text-sm leading-6 text-slate-600">
          Comunicación segura de la información necesaria para configurar un túnel VPN
          mediante el proceso automatizado existente en Workflow de Infraestructura.
        </p>
      </header>

      <div className="grid items-start gap-5 lg:grid-cols-[minmax(0,3fr)_minmax(320px,2fr)]">
        <div className="space-y-5">
          <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm md:p-6">
            <div className="mb-5">
              <h2 className="text-lg font-bold text-slate-950">Actividad del control</h2>
              <p className="mt-1 text-sm text-slate-500">Procedimiento de entrega y protección de parámetros VPN.</p>
            </div>
            <p className="text-sm leading-7 text-slate-700">
              Workflow de Infraestructura envía automáticamente un correo al generarse
              la VPN. La información de configuración, incluido el secreto precompartido,
              se encuentra en un archivo protegido por una contraseña robusta. La
              contraseña se proporciona por separado a quien realiza la configuración,
              mediante Skype o llamada telefónica.
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
            <h2 className="text-lg font-bold text-slate-950">Evidencia del procedimiento</h2>
            <p className="mt-1 mb-5 text-sm text-slate-500">
              Respaldo que identifica la matriz del control en Workflow.
            </p>
            <div className="grid gap-3 md:grid-cols-2">
              <Tarjeta
                titulo="Archivo cifrado de parámetros VPN"
                descripcion="Archivo protegido que contiene los parámetros necesarios para la configuración del túnel VPN."
              />
              <Tarjeta
                titulo="Informe de Workflow"
                descripcion="Informe donde permanece la evidencia del archivo cifrado asociado a la generación de la VPN."
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
              Compromiso de la seguridad de los sistemas por una administración
              inadecuada de las llaves criptográficas.
            </p>
          </section>
        </aside>
      </div>
    </main>
  );
}
