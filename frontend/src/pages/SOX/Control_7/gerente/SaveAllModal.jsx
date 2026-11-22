import { AlertTriangle, Save, X } from "lucide-react";
import { SCOPES } from "./vpnRows";

/** Aviso antes del guardado masivo: qué cuadro se guarda y cuál falta validar. */
export default function SaveAllModal({ plan, touchedAny, busy, onClose, onConfirm }) {
  const saved = plan.scopes.map((s) => SCOPES[s.key].lower).join(" y las ");
  const untouched = plan.missing.filter((m) => !plan.scopes.some((s) => s.key === m.key));
  const partial = plan.missing.filter((m) => plan.scopes.some((s) => s.key === m.key));
  const reported = plan.scopes.reduce((n, s) => n + s.reported, 0);
  const canSave = plan.scopes.length > 0 && plan.invalid.length === 0;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4" role="dialog" aria-modal="true" aria-label="Guardado masivo">
      <div className="w-full max-w-lg rounded-2xl bg-white p-6 shadow-xl">
        <div className="mb-4 flex items-start justify-between gap-4">
          <h3 className="flex items-center gap-2 text-lg font-bold"><AlertTriangle size={20} className="text-amber-500"/>Guardar todas</h3>
          <button type="button" onClick={onClose} disabled={busy} className="rounded-lg p-1 text-slate-500 hover:bg-slate-100" aria-label="Cerrar"><X size={20}/></button>
        </div>

        <div className="space-y-3 text-sm text-slate-700">
          {plan.scopes.length === 0 && <p>{touchedAny
            ? "No hay decisiones por guardar en el cuadro que revisaste. Elige la decisión de al menos una VPN."
            : "Todavía no has trabajado en ningún cuadro. Revisa las VPN externas o internas y vuelve a presionar Guardar todas."}</p>}

          {plan.invalid.length > 0 && <p className="rounded-lg bg-red-50 p-3 text-red-700">
            Falta la observación en {plan.invalid.length} VPN con la decisión <b>Otro</b>: {plan.invalid.slice(0, 5).map((x) => x.name).join(", ")}{plan.invalid.length > 5 ? "..." : ""}.</p>}

          {canSave && <>
            <p className="text-base">{untouched.length > 0 || plan.scopes.length === 1 ? "Solo se guardarán" : "Se guardarán"} las decisiones de las <b>{saved}</b>.</p>
            <ul className="list-disc space-y-1 pl-5">
              {plan.scopes.map((s) => <li key={s.key}>{SCOPES[s.key].title}: <b>{s.toSave.length}</b> por guardar</li>)}
            </ul>
          </>}

          {plan.scopes.length > 0 && untouched.map((m) => <p key={m.key} className="rounded-lg bg-amber-50 p-3 font-semibold text-amber-800">
            Falta validar las {SCOPES[m.key].lower} ({m.count} pendiente{m.count === 1 ? "" : "s"}).</p>)}
          {canSave && partial.map((m) => <p key={m.key} className="rounded-lg bg-amber-50 p-3 text-amber-800">
            {SCOPES[m.key].title}: {m.count} sin decisión elegida; quedarán pendientes.</p>)}

          {canSave && reported > 0 && <p className="rounded-lg bg-slate-50 p-3">
            {reported} con <b>Otro</b> o <b>No pertenece</b> quedarán pendientes hasta que el administrador las revise.</p>}
          {canSave && <p className="text-slate-500">Una vez guardadas, las decisiones no se pueden cambiar.</p>}
        </div>

        <div className="mt-6 flex justify-end gap-3">
          <button type="button" onClick={onClose} disabled={busy} className="h-11 rounded-lg border border-slate-300 px-5 text-sm font-bold">{canSave ? "Cancelar" : "Entendido"}</button>
          {canSave && <button type="button" onClick={onConfirm} disabled={busy}
            className="flex h-11 items-center gap-2 rounded-lg bg-amber-500 px-5 text-sm font-bold text-white hover:bg-amber-600 disabled:opacity-60">
            <Save size={16}/>{busy ? "Guardando..." : "Guardar"}</button>}
        </div>
      </div>
    </div>
  );
}
