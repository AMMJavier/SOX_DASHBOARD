import { useCallback, useEffect, useState } from "react";
import { getLatestC6Cut, getC6CutAccounts, syncC6Ldap } from "../../../services/sox/control_6/cortes";
import { Panel, FIELD, PRIMARY, SECONDARY, InfoBanner } from "../common/ControlUI";

const PAGE_SIZE = 25;

export default function LdapCortesTable({ onUseAccounts }) {
  const [cut, setCut] = useState(null);
  const [entries, setEntries] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [input, setInput] = useState("");
  const [query, setQuery] = useState("");
  const [group, setGroup] = useState("");
  const [loading, setLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState("");

  const loadLatest = useCallback(async () => {
    const data = await getLatestC6Cut();
    setCut(data.corte || null);
  }, []);

  useEffect(() => {
    loadLatest().catch((e) => setError(e.message));
  }, [loadLatest]);

  useEffect(() => {
    if (!cut) return;
    let active = true;
    setLoading(true);
    getC6CutAccounts(cut.id, { offset: page * PAGE_SIZE, limite: PAGE_SIZE, buscar: query, grupo: group })
      .then((result) => { if (active) { setEntries(result.items || []); setTotal(result.total || 0); setError(""); } })
      .catch((e) => { if (active) setError(e.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [cut, page, query, group]);

  async function refreshLive() {
    if (!window.confirm("¿¿Consultar los grupos RDP y Aplicaciones y guardar el resultado en Oracle? Esta acción NO modifica Active Directory.")) return;
    setSyncing(true); setError("");
    try {
      await syncC6Ldap();
      setPage(0);
      await loadLatest();
    } catch (e) { setError(e.message); }
    finally { setSyncing(false); }
  }

  async function useCurrentCut() {
    if (!cut || !onUseAccounts) return;
    setLoading(true); setError("");
    try {
      const all = [];
      let offset = 0;
      while (true) {
        const result = await getC6CutAccounts(cut.id, { offset, limite: 200 });
        all.push(...(result.items || []));
        offset += (result.items || []).length;
        if (offset >= result.total || !result.items?.length) break;
        if (offset > 15000) throw new Error("El corte supera el límite de consulta permitido");
      }
      onUseAccounts([...new Set(all.map((row) => row.usuario))]);
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  }

  return <Panel title="Inventario LDAP guardado en Oracle" description="Cortes de membresías RDP y Aplicaciones. Consulta el último corte, aun cuando el servidor LDAP esté temporalmente inaccesible.">
    {error && <InfoBanner caution>{error}</InfoBanner>}
    {!cut ? <p className="text-sm text-slate-600">Todavía no hay datos guardados. Presiona «Consultar LDAP y guardar en Oracle» para obtener el primer corte directamente desde Active Directory.</p> : <>
      <div className="mb-4 grid gap-3 text-sm sm:grid-cols-4">
        <div className="rounded-xl bg-slate-50 p-3"><p className="text-slate-500">RDP</p><strong className="text-lg">{cut.rdp}</strong></div>
        <div className="rounded-xl bg-slate-50 p-3"><p className="text-slate-500">Aplicaciones</p><strong className="text-lg">{cut.aplicaciones}</strong></div>
        <div className="rounded-xl bg-slate-50 p-3"><p className="text-slate-500">Cuentas únicas</p><strong className="text-lg">{cut.cuentas_unicas}</strong></div>
        <div className="rounded-xl bg-slate-50 p-3"><p className="text-slate-500">Registro Oracle (UTC)</p><strong className="text-xs">{cut.fuente} · {cut.fecha_registro_utc?.replace("T", " ").slice(0, 19)}</strong></div>
      </div>
      <p className="mb-3 text-xs text-slate-600">Extracción LDAP original (UTC): {cut.fecha_extraccion_utc?.replace("T", " ").slice(0, 19) || "No indicada en la importación"}</p>
      <div className="mb-3 flex flex-wrap gap-3">
        <input aria-label="Buscar usuario LDAP" value={input} onChange={(e) => setInput(e.target.value)} placeholder="Buscar usuario" className={`${FIELD} max-w-xs`} />
        <button className={SECONDARY} type="button" onClick={() => { setPage(0); setQuery(input); }}>Buscar</button>
        <select aria-label="Filtrar grupo LDAP" className={`${FIELD} max-w-xs`} value={group} onChange={(e) => { setGroup(e.target.value); setPage(0); }}>
          <option value="">Ambos grupos</option><option value="RDP">RDP</option><option value="APLICACIONES">Aplicaciones</option>
        </select>
      </div>
      <div className="overflow-x-auto"><table className="w-full min-w-[540px] text-left text-sm">
        <thead className="bg-slate-100"><tr><th className="p-3">Cuenta</th><th className="p-3">Nombre</th><th className="p-3">Grupo</th><th className="p-3">Estado en AD</th></tr></thead>
        <tbody>{entries.map((entry) => <tr key={`${entry.usuario}-${entry.tipo_acceso}`} className="border-b border-slate-100">
          <td className="p-3 font-medium">{entry.usuario}</td><td className="p-3">{entry.nombre || "—"}</td><td className="p-3">{entry.tipo_acceso}</td>
          <td className="p-3">{entry.activo === null ? "No informado" : entry.activo ? "Habilitada" : "Deshabilitada"}</td>
        </tr>)}{!entries.length && <tr><td className="p-5 text-center text-slate-500" colSpan={4}>{loading ? "Consultando..." : "Sin cuentas para este filtro"}</td></tr>}</tbody>
      </table></div>
      <div className="mt-3 flex items-center justify-between text-xs text-slate-600">
        <span>Registros: {total}. Página {page + 1} de {Math.max(1, Math.ceil(total / PAGE_SIZE))}</span>
        <div className="flex gap-2"><button type="button" className={SECONDARY} disabled={!page || loading} onClick={() => setPage((v) => v - 1)}>Anterior</button><button type="button" className={SECONDARY} disabled={loading || (page + 1) * PAGE_SIZE >= total} onClick={() => setPage((v) => v + 1)}>Siguiente</button></div>
      </div>
    </>}
    <div className="mt-4 flex flex-wrap gap-3">
      {cut && onUseAccounts && <button type="button" className={PRIMARY} disabled={loading} onClick={useCurrentCut}>Usar corte en conciliación</button>}
      <button type="button" className={SECONDARY} disabled={syncing} onClick={refreshLive}>{syncing ? "Consultando LDAP..." : "Consultar LDAP y guardar en Oracle"}</button>
    </div>
    <p className="mt-3 text-xs text-slate-500">Un clic consulta ambos grupos, guarda un nuevo corte en Oracle y actualiza la tabla. Si falla LDAP, el último corte permanece disponible. No modifica cuentas.</p>
  </Panel>;
}
