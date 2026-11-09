import { useEffect, useState, Fragment } from "react";
import {
  History, Search, RefreshCw, ChevronLeft, ChevronRight,
  Filter, ChevronDown, ChevronUp, FileSpreadsheet, FileText,
  AlertTriangle, Loader2,
} from "lucide-react";

import {
  getAssetLogSummary, getAssetLogDevice, getAllAssetLogs,
} from "../../services/assets/catalog";
import {
  exportAssetHistoryExcel, exportAssetHistoryPdf,
} from "../../utils/exportAssetHistory";

const PAGE_SIZE = 20;
const DETAIL_PAGE_SIZE = 100;
const INITIAL_FILTERS = {
  search: "", serial: "", campo: "", operacion: "", fecha_inicio: "", fecha_fin: "",
};
const FIELDS = [
  "ESPECIALIDAD", "PLATAFORMA", "TIPO", "DISPOSITIVO", "IP", "MASK",
  "GATEWAY", "MAC", "ESTADO", "CRITICIDAD", "CIUDAD", "LOCALIDAD",
  "PISO", "LADO", "INFRAESTRUCTURA", "SO", "VERSION", "FIRMWARE",
  "FABRICANTE", "MODELO", "SERIAL", "LICENCIA", "EOS", "COMENTARIO",
];

function formatDate(value) {
  if (!value) return "—";
  const [date, time = ""] = String(value).split("T");
  const [year, month, day] = date.split("-");
  if (!year || !month || !day) return String(value);
  return `${day}/${month}/${year} ${time.split(".")[0]}`.trim();
}

function printValue(value) {
  const text = value === null || value === undefined ? "" : String(value).trim();
  return ["", "-", "–", "—"].includes(text) ? "Sin valor" : text;
}

export default function Logs() {
  const [filters, setFilters] = useState({ ...INITIAL_FILTERS });
  const [appliedFilters, setAppliedFilters] = useState({ ...INITIAL_FILTERS });
  const [page, setPage] = useState(1);
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);
  const [expandedId, setExpandedId] = useState(null);
  const [details, setDetails] = useState({});
  const [exporting, setExporting] = useState("");
  const [progress, setProgress] = useState("");

  useEffect(() => {
    let active = true;
    async function load() {
      setLoading(true);
      setError("");
      try {
        const data = await getAssetLogSummary({ ...appliedFilters, page, page_size: PAGE_SIZE });
        if (!active) return;
        setItems(data.items ?? []);
        setTotal(Number(data.total ?? 0));
        setTotalPages(Math.max(1, Number(data.total_pages ?? 1)));
      } catch (err) {
        if (!active) return;
        setItems([]);
        setTotal(0);
        setTotalPages(1);
        setError(err.message || "No fue posible consultar el historial.");
      } finally {
        if (active) setLoading(false);
      }
    }
    load();
    return () => { active = false; };
  }, [appliedFilters, page, refreshKey]);

  function updateFilter(key, value) {
    setFilters((current) => ({ ...current, [key]: value }));
  }

  function applyFilters(event) {
    event.preventDefault();
    if (filters.fecha_inicio && filters.fecha_fin && filters.fecha_inicio > filters.fecha_fin) {
      setError("La fecha inicial no puede ser posterior a la fecha final.");
      return;
    }
    setExpandedId(null);
    setDetails({});
    setPage(1);
    setAppliedFilters({ ...filters });
  }

  function clearFilters() {
    setFilters({ ...INITIAL_FILTERS });
    setAppliedFilters({ ...INITIAL_FILTERS });
    setExpandedId(null);
    setDetails({});
    setPage(1);
    setError("");
  }

  async function loadDetail(deviceId, nextPage = 1) {
    setDetails((current) => ({
      ...current,
      [deviceId]: { ...current[deviceId], loading: true, error: "" },
    }));
    try {
      const data = await getAssetLogDevice(deviceId, {
        ...appliedFilters, page: nextPage, page_size: DETAIL_PAGE_SIZE,
      });
      setDetails((current) => ({
        ...current,
        [deviceId]: {
          items: nextPage === 1
            ? (data.items || [])
            : [...(current[deviceId]?.items || []), ...(data.items || [])],
          page: nextPage,
          totalPages: Number(data.total_pages || 0),
          total: Number(data.total || 0),
          loading: false,
          error: "",
        },
      }));
    } catch (err) {
      setDetails((current) => ({
        ...current,
        [deviceId]: { ...current[deviceId], loading: false,
          error: err.message || "No se pudo consultar el detalle." },
      }));
    }
  }

  function toggleDetail(deviceId) {
    if (expandedId === deviceId) {
      setExpandedId(null);
      return;
    }
    setExpandedId(deviceId);
    if (!details[deviceId]) void loadDetail(deviceId);
  }

  async function download(format) {
    if (exporting) return;
    if (appliedFilters.fecha_inicio && appliedFilters.fecha_fin &&
        appliedFilters.fecha_inicio > appliedFilters.fecha_fin) {
      setError("Revisa el intervalo de fechas antes de exportar.");
      return;
    }
    setExporting(format);
    setProgress("Consultando el historial completo...");
    setError("");
    try {
      const logs = await getAllAssetLogs(appliedFilters, (downloaded, count) => {
        setProgress(`Descargando modificaciones: ${downloaded} de ${count}`);
      });
      if (!logs.length) {
        setError("No hay modificaciones que coincidan con los filtros seleccionados.");
        return;
      }
      const stamp = new Date().toISOString().slice(0, 10);
      if (format === "excel") {
        exportAssetHistoryExcel(logs, `Assets_Historial_${stamp}.xlsx`);
      } else {
        exportAssetHistoryPdf(logs, `Assets_Historial_${stamp}.pdf`);
      }
    } catch (err) {
      setError(err.message || "No fue posible exportar el historial completo.");
    } finally {
      setExporting("");
      setProgress("");
    }
  }

  return (
    <div className="space-y-6 pb-10">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-violet-600">Assets Management</p>
          <h1 className="mt-1 text-3xl font-bold text-slate-900">Historial de cambios</h1>
          <p className="mt-2 text-sm text-slate-500">
            Un registro por dispositivo. Despliega un activo para consultar los cambios y sus fechas.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button type="button" onClick={() => download("excel")} disabled={!!exporting}
            className="inline-flex items-center gap-2 rounded-xl border border-emerald-300 bg-emerald-50 px-4 py-2 text-sm font-semibold text-emerald-800 hover:bg-emerald-100 disabled:opacity-50">
            <FileSpreadsheet size={17} /> {exporting === "excel" ? "Preparando Excel..." : "Exportar Excel"}
          </button>
          <button type="button" onClick={() => download("pdf")} disabled={!!exporting}
            className="inline-flex items-center gap-2 rounded-xl border border-rose-300 bg-rose-50 px-4 py-2 text-sm font-semibold text-rose-700 hover:bg-rose-100 disabled:opacity-50">
            <FileText size={17} /> {exporting === "pdf" ? "Preparando PDF..." : "Exportar PDF"}
          </button>
          <button type="button" onClick={() => {
              setExpandedId(null); setDetails({}); setRefreshKey((value) => value + 1);
            }} disabled={loading}
            className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50">
            <RefreshCw size={16} className={loading ? "animate-spin" : ""} /> Actualizar
          </button>
        </div>
      </div>

      {progress && <p className="rounded-xl bg-violet-50 p-3 text-sm text-violet-800" role="status">
        <Loader2 size={15} className="mr-2 inline animate-spin" />{progress}
      </p>}

      <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex items-center gap-4">
          <div className="rounded-xl bg-violet-100 p-3 text-violet-700"><History size={24} /></div>
          <div>
            <p className="text-sm text-slate-500">Dispositivos con modificaciones</p>
            <p className="text-3xl font-bold text-slate-900">{total.toLocaleString("es-EC")}</p>
            <p className="text-xs text-slate-400">El exportado incluye todos los cambios, no solo la página visible.</p>
          </div>
        </div>
      </div>

      <form onSubmit={applyFilters} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="mb-4 flex items-center gap-2">
          <Filter size={18} className="text-violet-600" />
          <h2 className="font-semibold text-slate-900">Filtros de auditoría</h2>
        </div>
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          <label className="space-y-2">
            <span className="text-xs font-medium text-slate-600">Dispositivo, serial o ID</span>
            <div className="relative">
              <Search size={16} className="absolute left-3 top-3 text-slate-400" />
              <input value={filters.search} onChange={(e) => updateFilter("search", e.target.value)}
                placeholder="Buscar un activo" className="w-full rounded-lg border border-slate-200 py-2 pl-9 pr-3 text-sm outline-none focus:border-violet-400" />
            </div>
          </label>
          <label className="space-y-2">
            <span className="text-xs font-medium text-slate-600">Serial exacto</span>
            <input value={filters.serial} onChange={(e) => updateFilter("serial", e.target.value)}
              placeholder="Número de serie" className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm" />
          </label>
          <label className="space-y-2">
            <span className="text-xs font-medium text-slate-600">Campo modificado</span>
            <select value={filters.campo} onChange={(e) => updateFilter("campo", e.target.value)}
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm">
              <option value="">Todos los campos</option>
              {FIELDS.map((field) => <option key={field} value={field}>{field}</option>)}
            </select>
          </label>
          <label className="space-y-2">
            <span className="text-xs font-medium text-slate-600">Operación</span>
            <select value={filters.operacion} onChange={(e) => updateFilter("operacion", e.target.value)}
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm">
              <option value="">Todas</option><option value="UPDATE">Actualización</option>
            </select>
          </label>
          <label className="space-y-2">
            <span className="text-xs font-medium text-slate-600">Desde</span>
            <input type="date" value={filters.fecha_inicio}
              onChange={(e) => updateFilter("fecha_inicio", e.target.value)}
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm" />
          </label>
          <label className="space-y-2">
            <span className="text-xs font-medium text-slate-600">Hasta</span>
            <input type="date" value={filters.fecha_fin}
              onChange={(e) => updateFilter("fecha_fin", e.target.value)}
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm" />
          </label>
        </div>
        <div className="mt-4 flex justify-end gap-3">
          <button type="button" onClick={clearFilters}
            className="rounded-lg border border-slate-200 px-4 py-2 text-sm text-slate-600 hover:bg-slate-50">Limpiar</button>
          <button type="submit" disabled={loading}
            className="rounded-lg bg-violet-600 px-5 py-2 text-sm font-medium text-white hover:bg-violet-700 disabled:opacity-50">Aplicar filtros</button>
        </div>
      </form>

      {error && <div role="alert" className="flex items-center gap-2 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
        <AlertTriangle size={18} />{error}
      </div>}

      <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="border-b border-slate-200 p-5">
          <h2 className="font-semibold text-slate-900">Dispositivos con historial</h2>
          <p className="mt-1 text-xs text-slate-500">
            Selecciona «Ver cambios» para consultar fecha, campo, valor anterior y valor actual.
          </p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[900px] text-left text-sm">
            <thead className="bg-slate-100 text-xs text-slate-600">
              <tr>
                <th className="px-4 py-4">Dispositivo / serial</th>
                <th className="px-4 py-4">Última modificación</th>
                <th className="px-4 py-4">Campos modificados</th>
                <th className="px-4 py-4">Último usuario / origen</th>
                <th className="px-4 py-4 text-right">Detalle</th>
              </tr>
            </thead>
            <tbody>
              {loading ? <tr><td colSpan={5} className="py-12 text-center text-slate-500">Cargando historial...</td></tr>
                : items.length === 0 ? <tr><td colSpan={5} className="py-12 text-center text-slate-500">No se encontraron modificaciones.</td></tr>
                  : items.map((item) => {
                    const isOpen = expandedId === item.dispositivo_id;
                    const info = details[item.dispositivo_id];
                    return <Fragment key={item.dispositivo_id}>
                      <tr className="border-t border-slate-100 hover:bg-violet-50/40">
                        <td className="px-4 py-4">
                          <p className="font-semibold text-slate-900">{item.dispositivo || `Activo #${item.dispositivo_id}`}</p>
                          <p className="mt-1 text-xs text-slate-500">ID: {item.dispositivo_id}</p>
                          <p className="text-xs text-slate-500">Serial: {printValue(item.serial)}</p>
                        </td>
                        <td className="whitespace-nowrap px-4 py-4 text-slate-700">{formatDate(item.fecha_cambio)}</td>
                        <td className="px-4 py-4">
                          <span className="rounded-full bg-violet-100 px-3 py-1 text-xs font-semibold text-violet-700">{item.total_cambios}</span>
                        </td>
                        <td className="px-4 py-4 text-slate-700">{item.usuario || "—"}<p className="text-xs text-slate-400">{item.origen || "—"}</p></td>
                        <td className="px-4 py-4 text-right">
                          <button type="button" onClick={() => toggleDetail(item.dispositivo_id)}
                            aria-expanded={isOpen} aria-label={`Ver historial de ${item.dispositivo || item.dispositivo_id}`}
                            className="inline-flex items-center gap-2 rounded-lg border border-violet-200 bg-violet-50 px-3 py-2 text-xs font-semibold text-violet-700 hover:bg-violet-100">
                            {isOpen ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                            {isOpen ? "Ocultar" : "Ver cambios"}
                          </button>
                        </td>
                      </tr>
                      {isOpen && <tr className="bg-slate-50"><td colSpan={5} className="p-4 md:p-6">
                        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
                          <div className="border-b border-slate-100 px-4 py-3 text-sm font-semibold text-slate-700">
                            Historial de modificaciones del activo #{item.dispositivo_id}
                          </div>
                          {info?.error && <p className="p-4 text-sm text-red-600">{info.error}</p>}
                          {!info && <p className="p-4 text-sm text-slate-500">Consultando cambios...</p>}
                          {info && <div className="overflow-x-auto"><table className="w-full min-w-[780px] text-left text-xs md:text-sm">
                            <thead className="bg-slate-100 text-slate-600"><tr>
                              <th className="px-3 py-3">Fecha y hora</th>
                              <th className="px-3 py-3">Campo</th>
                              <th className="px-3 py-3">Estado anterior</th>
                              <th className="px-3 py-3">Estado actual</th>
                              <th className="px-3 py-3">Usuario</th>
                            </tr></thead>
                            <tbody>{(info.items || []).map((entry) => <tr key={entry.log_id} className="border-t border-slate-100">
                              <td className="whitespace-nowrap px-3 py-3 text-slate-600">{formatDate(entry.fecha_cambio)}</td>
                              <td className="px-3 py-3 font-medium text-violet-700">{entry.campo_modificado}</td>
                              <td className="max-w-[240px] break-words px-3 py-3 text-red-700"><span className="rounded-md bg-red-50 px-2 py-1">{printValue(entry.valor_anterior)}</span></td>
                              <td className="max-w-[240px] break-words px-3 py-3 text-emerald-700"><span className="rounded-md bg-emerald-50 px-2 py-1">{printValue(entry.valor_nuevo)}</span></td>
                              <td className="px-3 py-3 text-slate-600">{entry.usuario || "—"}</td>
                            </tr>)}</tbody>
                          </table></div>}
                          {info?.loading && <p className="p-3 text-center text-xs text-slate-500">Cargando cambios...</p>}
                          {info && info.page < info.totalPages && <div className="border-t border-slate-100 p-3 text-center">
                            <button type="button" disabled={info.loading}
                              onClick={() => loadDetail(item.dispositivo_id, info.page + 1)}
                              className="rounded-lg border border-violet-200 px-4 py-2 text-sm font-semibold text-violet-700 hover:bg-violet-50 disabled:opacity-50">
                              Cargar más cambios ({(info.items || []).length} de {info.total})
                            </button>
                          </div>}
                        </div>
                      </td></tr>}
                    </Fragment>;
                  })}
            </tbody>
          </table>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-200 px-5 py-4">
          <p className="text-sm text-slate-500">{total} dispositivos con cambios</p>
          <div className="flex items-center gap-3">
            <button type="button" disabled={loading || page <= 1}
              onClick={() => { setExpandedId(null); setDetails({}); setPage((p) => p - 1); }}
              className="rounded-lg border border-slate-200 p-2 disabled:opacity-40" aria-label="Página anterior">
              <ChevronLeft size={18} />
            </button>
            <span className="text-sm text-slate-700">{page} de {totalPages}</span>
            <button type="button" disabled={loading || page >= totalPages}
              onClick={() => { setExpandedId(null); setDetails({}); setPage((p) => p + 1); }}
              className="rounded-lg border border-slate-200 p-2 disabled:opacity-40" aria-label="Página siguiente">
              <ChevronRight size={18} />
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}
