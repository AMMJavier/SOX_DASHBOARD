import { useEffect, useState } from "react";
import { Search, UserCheck, X } from "lucide-react";
import {
  assignInternalManager, errorText, getInternalManagers, lookupInternalManager,
} from "../../../../services/sox/control_7/internalVpnService";

const INPUT = "h-11 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm outline-none focus:border-blue-500";

/**
 * Asignación manual del gerente a cuentas SIN gerente en AD (casos especiales).
 * Si el gerente ya está en la campaña, las cuentas se suman a él (mismo nombre y correo).
 */
export default function AssignManagerModal({ accounts, onClose, onSaved }) {
  const [managers, setManagers] = useState([]);
  const [mode, setMode] = useState("existente");
  const [selected, setSelected] = useState("");
  const [user, setUser] = useState("");
  const [name, setName] = useState("");
  const [mail, setMail] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    getInternalManagers().then(setManagers).catch((e) => setError(errorText(e, "No se pudo leer la lista de gerentes.")));
  }, []);

  const typed = user.trim().toLowerCase();
  const already = managers.find((m) => m.usuario?.toLowerCase() === typed);

  async function lookup() {
    if (!typed) return;
    setBusy(true); setError(""); setNote("");
    try {
      const p = await lookupInternalManager(typed);
      setName(p.nombre || ""); setMail(p.correo || "");
      setNote(`Encontrado en AD${p.cargo ? ` · ${p.cargo}` : ""}${p.correo ? "" : " · sin correo en AD: escríbelo"}`);
    } catch (e) {
      setNote(""); setError(errorText(e, "No se pudo consultar AD."));
    } finally { setBusy(false); }
  }

  async function save() {
    const usuario = mode === "existente" ? selected : typed;
    if (!usuario) { setError(mode === "existente" ? "Elige un gerente." : "Escribe el usuario de red del gerente."); return; }
    setBusy(true); setError("");
    try {
      const r = await assignInternalManager({
        ids: accounts.map((a) => a.id), usuario,
        nombre: mode === "nuevo" ? name.trim() || null : null,
        correo: mode === "nuevo" ? mail.trim() || null : null,
      });
      onSaved(r);
    } catch (e) {
      setError(errorText(e, "No se pudo asignar el gerente."));
    } finally { setBusy(false); }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4">
      <div className="w-full max-w-xl rounded-2xl bg-white p-6 shadow-xl">
        <div className="mb-4 flex items-start justify-between gap-4">
          <div>
            <h3 className="text-lg font-bold">Asignar gerente</h3>
            <p className="text-sm text-slate-500">
              {accounts.length === 1
                ? `${accounts[0].usuario} · ${accounts[0].nombre || "-"} · ${accounts[0].tipo_acceso === "RDP" ? "RDP" : "Aplicaciones"}`
                : `${accounts.length} cuentas sin gerente en AD`}
            </p>
          </div>
          <button onClick={onClose} className="rounded-lg p-1 text-slate-500 hover:bg-slate-100" aria-label="Cerrar"><X size={20}/></button>
        </div>

        <div className="mb-4 flex gap-2">
          {[["existente", "Gerente de la campaña"], ["nuevo", "Otro gerente"]].map(([v, l]) => (
            <button key={v} onClick={() => { setMode(v); setError(""); }}
              className={`h-10 flex-1 rounded-lg border text-sm font-bold ${mode === v ? "border-blue-600 bg-blue-50 text-blue-700" : "border-slate-300 text-slate-600"}`}>{l}</button>
          ))}
        </div>

        {mode === "existente" ? (
          <div>
            <select value={selected} onChange={(e) => setSelected(e.target.value)} className={INPUT}>
              <option value="">Elige un gerente...</option>
              {managers.map((m) => <option key={m.usuario} value={m.usuario}>{m.nombre} ({m.usuario}) · {m.accesos} acceso(s)</option>)}
            </select>
            <p className="mt-2 text-xs text-slate-500">La cuenta se suma a ese gerente y recibe un solo correo con todas sus cuentas.</p>
          </div>
        ) : (
          <div className="space-y-3">
            <div className="flex gap-2">
              <input value={user} onChange={(e) => { setUser(e.target.value); setNote(""); }} className={INPUT} placeholder="Usuario de red (AD), ej. janton"/>
              <button onClick={lookup} disabled={busy || !typed} className="flex h-11 shrink-0 items-center gap-2 rounded-lg border border-slate-300 px-4 text-sm font-bold hover:bg-slate-50 disabled:opacity-60">
                <Search size={16}/>Buscar en AD</button>
            </div>
            {already
              ? <p className="rounded-lg bg-blue-50 p-3 text-sm text-blue-800">{already.nombre} ya está en la campaña: la cuenta se sumará a sus {already.accesos} acceso(s).</p>
              : <>
                  <input value={name} onChange={(e) => setName(e.target.value)} className={INPUT} placeholder="Nombre del gerente"/>
                  <input value={mail} onChange={(e) => setMail(e.target.value)} className={INPUT} placeholder="Correo del gerente"/>
                  <p className="text-xs text-slate-500">Si el usuario existe en AD, se usan el nombre y el correo de AD.</p>
                </>}
            {note && <p className="text-sm text-green-700">{note}</p>}
          </div>
        )}

        {error && <p className="mt-4 rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</p>}

        <div className="mt-6 flex justify-end gap-3">
          <button onClick={onClose} className="h-11 rounded-lg border border-slate-300 px-5 text-sm font-bold">Cancelar</button>
          <button onClick={save} disabled={busy} className="flex h-11 items-center gap-2 rounded-lg bg-blue-600 px-5 text-sm font-bold text-white hover:bg-blue-700 disabled:opacity-60">
            <UserCheck size={16}/>{busy ? "Guardando..." : "Asignar"}</button>
        </div>
      </div>
    </div>
  );
}
