import { AlertTriangle, X } from "lucide-react";

/**
 * Ventana de confirmación con "Cancelar" y "Confirmar".
 * tone: blue | green | slate | red (color del botón de confirmar).
 */
const TONES = {
  blue: "bg-blue-600 hover:bg-blue-700",
  green: "bg-green-600 hover:bg-green-700",
  slate: "bg-slate-900 hover:bg-slate-800",
  red: "bg-red-600 hover:bg-red-700",
};

export default function ConfirmModal({ title, children, confirmLabel = "Confirmar", cancelLabel = "Cancelar",
  icon: Icon, tone = "blue", busy = false, onClose, onConfirm }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4" role="dialog" aria-modal="true" aria-label={title}>
      <div className="w-full max-w-lg rounded-2xl bg-white p-6 text-left shadow-xl">
        <div className="mb-4 flex items-start justify-between gap-4">
          <h3 className="flex items-center gap-2 text-lg font-bold text-slate-900"><AlertTriangle size={20} className="shrink-0 text-amber-500"/>{title}</h3>
          <button type="button" onClick={onClose} disabled={busy} className="rounded-lg p-1 text-slate-500 hover:bg-slate-100" aria-label="Cerrar"><X size={20}/></button>
        </div>
        <div className="space-y-3 text-sm font-normal text-slate-700">{children}</div>
        <div className="mt-6 flex justify-end gap-3">
          <button type="button" onClick={onClose} disabled={busy} className="h-11 rounded-lg border border-slate-300 px-5 text-sm font-bold text-slate-700 hover:bg-slate-50">{cancelLabel}</button>
          <button type="button" onClick={onConfirm} disabled={busy}
            className={`flex h-11 items-center gap-2 rounded-lg px-5 text-sm font-bold text-white disabled:opacity-60 ${TONES[tone] || TONES.blue}`}>
            {Icon && <Icon size={16}/>}{confirmLabel}</button>
        </div>
      </div>
    </div>
  );
}
