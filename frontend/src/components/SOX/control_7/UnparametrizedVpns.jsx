import { useEffect, useMemo, useState } from "react";
import { AlertCircle, ChevronDown, ChevronUp, Download, RefreshCw, Search } from "lucide-react";
import { api } from "../../../services/api";

/**
 * VPN extraídas de Check Point que no quedaron parametrizadas: su comentario no tiene el
 * formato esperado (REQ / solicitante / gerente), por eso no entran a la validación de
 * gerentes. Es la diferencia del indicador "Conciliación Check Point" (p. ej. 763/769).
 */
export default function UnparametrizedVpns() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(true);
  const [query, setQuery] = useState("");

  const load = async () => {
    setLoading(true); setError("");
    try {
      const response = await api.get("/sox/campaign/vpn-sin-parametrizar");
      setData(response.data);
    } catch (e) {
      setError(e?.response?.data?.detail || "No fue posible consultar las VPN sin parametrizar.");
    } finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const items = useMemo(() => {
    const q = query.trim().toLowerCase();
    const list = data?.items || [];
    if (!q) return list;
    return list.filter((v) => [v.nombre_vpn, v.comentario, v.checkpoint_uid, v.motivo].some((x) => String(x || "").toLowerCase().includes(q)));
  }, [data, query]);

  const exportCsv = () => {
    const esc = (v) => `"${String(v ?? "").replace(/"/g, '""')}"`;
    const rows = [["Nombre VPN", "Motivo", "Comentario en Check Point", "UID Check Point", "Fecha extracción"],
      ...(data?.items || []).map((v) => [v.nombre_vpn, v.motivo, v.comentario, v.checkpoint_uid, v.fecha_almacenado])];
    const blob = new Blob(["﻿" + rows.map((r) => r.map(esc).join(";")).join("\r\n")], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = Object.assign(document.createElement("a"), { href: url, download: "vpn_sin_parametrizar.csv" });
    link.click();
    URL.revokeObjectURL(url);
  };

  const total = data?.total ?? 0;

  return (
    <section className="mt-6 rounded-2xl border border-amber-200 bg-white shadow-sm">
      <div className="flex flex-col gap-3 p-5 sm:flex-row sm:items-center sm:justify-between">
        <button type="button" onClick={() => setOpen((v) => !v)} className="flex items-start gap-3 text-left">
          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-amber-100 text-amber-700"><AlertCircle size={22}/></div>
          <div>
            <h2 className="flex items-center gap-2 text-lg font-bold text-slate-900">
              VPN sin parametrizar {data && <span className="rounded-full bg-amber-100 px-2.5 py-0.5 text-sm text-amber-800">{total}</span>}
              {open ? <ChevronUp size={18} className="text-slate-400"/> : <ChevronDown size={18} className="text-slate-400"/>}
            </h2>
            <p className="text-sm text-slate-500">
              Extraídas de Check Point{data ? ` (${data.total_checkpoint})` : ""} pero sin REQ, solicitante o gerente reconocibles en su comentario; no entran a la validación de gerentes.
            </p>
          </div>
        </button>
        <div className="flex gap-2">
          <button type="button" onClick={load} disabled={loading} className="inline-flex items-center gap-2 rounded-xl border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50">
            <RefreshCw size={15} className={loading ? "animate-spin" : ""}/>Actualizar</button>
          <button type="button" onClick={exportCsv} disabled={!total} className="inline-flex items-center gap-2 rounded-xl border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50">
            <Download size={15}/>CSV</button>
        </div>
      </div>

      {open && <div className="border-t border-slate-100 p-5">
        {error && <p className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</p>}
        {!error && loading && !data && <p className="text-sm text-slate-500">Cargando...</p>}
        {!error && data && total === 0 && <p className="rounded-lg bg-emerald-50 p-3 text-sm text-emerald-800">Todas las VPN extraídas de Check Point están parametrizadas.</p>}
        {!error && total > 0 && <>
          {data.origen === "calculado" && <p className="mb-4 rounded-lg bg-slate-50 p-3 text-xs text-slate-600">
            Motivo estimado: falta ejecutar <code>backend/sql/checkpoint_rechazados.sql</code> en Oracle para registrar el motivo exacto.</p>}
          <div className="relative mb-4 sm:w-80">
            <Search size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"/>
            <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Buscar VPN o comentario"
              className="h-10 w-full rounded-xl border border-slate-300 pl-9 pr-3 text-sm outline-none focus:border-amber-500"/>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
                <tr><th className="px-4 py-3">Nombre VPN</th><th className="px-4 py-3">Motivo</th><th className="px-4 py-3">Comentario en Check Point</th><th className="px-4 py-3">Fecha extracción</th></tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {items.map((v) => <tr key={v.checkpoint_uid} className="align-top hover:bg-slate-50/70">
                  <td className="px-4 py-3 font-semibold text-slate-900">{v.nombre_vpn}<p className="font-mono text-[11px] font-normal text-slate-400">{v.checkpoint_uid}</p></td>
                  <td className="px-4 py-3"><span className="inline-flex rounded-full bg-amber-50 px-2.5 py-0.5 text-xs font-semibold text-amber-800 ring-1 ring-amber-200">{v.motivo}</span></td>
                  <td className="max-w-md px-4 py-3 text-slate-600"><span className="whitespace-pre-wrap break-words">{v.comentario || "—"}</span></td>
                  <td className="whitespace-nowrap px-4 py-3 text-slate-600">{v.fecha_almacenado ? String(v.fecha_almacenado).replace("T", " ").slice(0, 16) : "—"}
                    {v.fecha_deteccion && <p className="text-[11px] text-slate-400">Detectada: {String(v.fecha_deteccion).replace("T", " ").slice(0, 16)}</p>}</td>
                </tr>)}
              </tbody>
            </table>
          </div>
          {!items.length && <p className="p-4 text-center text-sm text-slate-500">Ninguna VPN coincide con la búsqueda.</p>}
          <p className="mt-3 text-xs text-slate-500">Para corregirlas, ajusta el comentario de cada VPN en Check Point con el formato esperado y vuelve a sincronizar la campaña.</p>
        </>}
      </div>}
    </section>
  );
}
