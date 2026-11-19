import { useEffect, useState } from "react";
import { Check, Search, UserCheck, X } from "lucide-react";
import {
  assignInternalManager, errorText, getInternalManagers, searchInternalManagersAd,
} from "../../../../services/sox/control_7/internalVpnService";

const INPUT = "h-11 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm outline-none focus:border-blue-500";
const plain = (v) => String(v || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

/**
 * Asignación manual del gerente a cuentas SIN gerente en AD (casos especiales).
 * Búsqueda por cuenta o por nombre. Si el gerente ya está en la campaña, las cuentas
 * se suman a él (mismo nombre y correo).
 */
export default function AssignManagerModal({ accounts, onClose, onSaved }) {
  const [managers, setManagers] = useState([]);
  const [mode, setMode] = useState("existente");
  const [filter, setFilter] = useState("");
  const [selected, setSelected] = useState("");
  const [query, setQuery] = useState("");
  const [results, setResults] = useState(null);
  const [chosen, setChosen] = useState(null); // persona elegida de AD
  const [name, setName] = useState("");
  const [mail, setMail] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    getInternalManagers().then(setManagers).catch((e) => setError(errorText(e, "No se pudo leer la lista de gerentes.")));
  }, []);

  // Gerentes de la campaña filtrados por cuenta o por nombre (todas las palabras).
  const words = plain(filter).split(/\s+/).filter(Boolean);
  const shown = managers.filter((m) => words.every((w) => plain(`${m.usuario} ${m.nombre}`).includes(w)));
  const already = chosen && managers.find((m) => m.usuario?.toLowerCase() === chosen.usuario);

  async function search(e) {
    e?.preventDefault();
    if (query.trim().length < 3) { setError("Escribe al menos 3 letras de la cuenta o del nombre."); return; }
    setBusy(true); setError(""); setChosen(null);
    try { setResults(await searchInternalManagersAd(query.trim())); }
    catch (err) { setResults(null); setError(errorText(err, "No se pudo buscar en AD.")); }
    finally { setBusy(false); }
  }

  function choose(p) {
    setChosen(p); setName(p.nombre || ""); setMail(p.correo || ""); setError("");
  }

  async function save() {
    const usuario = mode === "existente" ? selected : chosen?.usuario;
    if (!usuario) {
      setError(mode === "existente" ? "Elige un gerente de la lista." : "Busca por cuenta o nombre y elige el gerente de la lista.");
      return;
    }
    setBusy(true); setError("");
    try {
      const r = await assignInternalManager({
        ids: accounts.map((a) => a.id), usuario,
        nombre: mode === "nuevo" ? name.trim() || null : null,
        correo: mode === "nuevo" ? mail.trim() || null : null,
      });
      onSaved(r);
    } catch (err) {
      setError(errorText(err, "No se pudo asignar el gerente."));
    } finally { setBusy(false); }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4">
      <div className="flex max-h-[90vh] w-full max-w-xl flex-col rounded-2xl bg-white p-6 shadow-xl">
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

        <div className="min-h-0 overflow-y-auto">
          {mode === "existente" ? (
            <div className="space-y-2">
              <input value={filter} onChange={(e) => setFilter(e.target.value)} className={INPUT} placeholder="Filtrar por cuenta o nombre..."/>
              <div className="max-h-64 overflow-y-auto rounded-lg border border-slate-200">
                {shown.map((m) => (
                  <button key={m.usuario} onClick={() => setSelected(m.usuario)}
                    className={`flex w-full items-center justify-between gap-3 border-b px-3 py-2 text-left text-sm last:border-b-0 hover:bg-slate-50 ${selected === m.usuario ? "bg-blue-50" : ""}`}>
                    <span><span className="font-bold">{m.nombre}</span> <span className="text-slate-500">({m.usuario})</span>
                      <span className="block text-xs text-slate-500">{m.accesos} acceso(s) · {m.correo || "sin correo"}</span></span>
                    {selected === m.usuario && <Check size={16} className="shrink-0 text-blue-600"/>}
                  </button>
                ))}
                {!shown.length && <p className="p-3 text-sm text-slate-500">Ningún gerente de la campaña coincide. Prueba en "Otro gerente".</p>}
              </div>
              <p className="text-xs text-slate-500">La cuenta se suma a ese gerente y recibe un solo correo con todas sus cuentas.</p>
            </div>
          ) : (
            <div className="space-y-3">
              <form onSubmit={search} className="flex gap-2">
                <input value={query} onChange={(e) => setQuery(e.target.value)} className={INPUT} placeholder="Cuenta o nombre, ej. anapao o Angel Napa"/>
                <button type="submit" disabled={busy} className="flex h-11 shrink-0 items-center gap-2 rounded-lg border border-slate-300 px-4 text-sm font-bold hover:bg-slate-50 disabled:opacity-60">
                  <Search size={16}/>{busy && !chosen ? "Buscando..." : "Buscar en AD"}</button>
              </form>

              {results && (
                <div className="max-h-56 overflow-y-auto rounded-lg border border-slate-200">
                  {results.map((p) => (
                    <button key={p.usuario} onClick={() => choose(p)}
                      className={`flex w-full items-center justify-between gap-3 border-b px-3 py-2 text-left text-sm last:border-b-0 hover:bg-slate-50 ${chosen?.usuario === p.usuario ? "bg-blue-50" : ""}`}>
                      <span><span className="font-bold">{p.nombre}</span> <span className="text-slate-500">({p.usuario})</span>
                        <span className="block text-xs text-slate-500">{p.cargo || "sin cargo"} · {p.correo || "sin correo en AD"}</span></span>
                      {chosen?.usuario === p.usuario && <Check size={16} className="shrink-0 text-blue-600"/>}
                    </button>
                  ))}
                  {!results.length && <p className="p-3 text-sm text-slate-500">No hay personas activas en AD con esa cuenta o nombre.</p>}
                  {results.length >= 20 && <p className="p-2 text-xs text-slate-500">Se muestran los primeros 20: escribe más para afinar.</p>}
                </div>
              )}

              {chosen && (already
                ? <p className="rounded-lg bg-blue-50 p-3 text-sm text-blue-800">{already.nombre} ya está en la campaña: la cuenta se sumará a sus {already.accesos} acceso(s).</p>
                : <div className="space-y-2">
                    <input value={name} onChange={(e) => setName(e.target.value)} className={INPUT} placeholder="Nombre del gerente"/>
                    <input value={mail} onChange={(e) => setMail(e.target.value)} className={INPUT} placeholder="Correo del gerente"/>
                    <p className="text-xs text-slate-500">Se usan el nombre y el correo de AD; si AD no tiene correo, escríbelo.</p>
                  </div>)}
            </div>
          )}

          {error && <p className="mt-4 rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</p>}
        </div>

        <div className="mt-6 flex justify-end gap-3">
          <button onClick={onClose} className="h-11 rounded-lg border border-slate-300 px-5 text-sm font-bold">Cancelar</button>
          <button onClick={save} disabled={busy} className="flex h-11 items-center gap-2 rounded-lg bg-blue-600 px-5 text-sm font-bold text-white hover:bg-blue-700 disabled:opacity-60">
            <UserCheck size={16}/>{busy && (mode === "existente" || chosen) ? "Guardando..." : "Asignar"}</button>
        </div>
      </div>
    </div>
  );
}
