import { useEffect, useState } from "react";
import {
  Search,
  RefreshCw,
  Boxes,
  Database,
  Filter,
  ChevronLeft,
  ChevronRight,
  X,
  AlertTriangle,
  HardDrive,
  Pencil,
  Save,
  CheckCircle2,
} from "lucide-react";

import { getInventory, getInventoryOptions, updateInventoryDevice } from "../../services/assets/catalog";
import { readStoredUser } from "../../services/authSession";

const FIELDS = [
  ["id", "ID"],
  ["especialidad", "Especialidad"],
  ["plataforma", "Plataforma"],
  ["tipo", "Tipo"],
  ["dispositivo", "Dispositivo"],
  ["estado", "Estado"],
  ["criticidad", "Criticidad"],
  ["infraestructura", "Infraestructura"],
  ["ip", "IP"],
  ["mask", "Máscara"],
  ["gateway", "Gateway"],
  ["mac", "MAC"],
  ["localidad", "Localidad"],
  ["piso", "Piso"],
  ["lado", "Lado"],
  ["ciudad", "Ciudad"],
  ["so", "Sistema operativo"],
  ["version", "Versión"],
  ["firmware", "Firmware"],
  ["fabricante", "Fabricante"],
  ["modelo", "Modelo"],
  ["serial", "Serial"],
  ["licencia", "Licencia"],
  ["eos", "EOS"],
  ["comentario", "Comentario"],
];

const PAGE_SIZE = 20;
const EMPTY_FILTERS = { q: "", id: "", serial: "", tipo: "", ciudad: "", localidad: "", eos: "" };

// El guion es una representación visual de vacío, no un cambio auditable.
const isBlankMarker = (value) =>
  value === null || value === undefined ||
  ["", "-", "–", "—"].includes(String(value).trim());

const display = (value) => isBlankMarker(value) ? "—" : String(value);

export default function Inventory() {
  const [records, setRecords] = useState([]);
  const [filters, setFilters] = useState({ ...EMPTY_FILTERS });
  const [applied, setApplied] = useState({ ...EMPTY_FILTERS });
  const [options, setOptions] = useState({ tipo: [], ciudad: [], localidad: [] });
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [pages, setPages] = useState(1);
  const [selected, setSelected] = useState(null);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(null);
  const [saving, setSaving] = useState(false);
  const [editError, setEditError] = useState("");
  const [editSuccess, setEditSuccess] = useState("");
  const canEdit = readStoredUser()?.rol === "assets_admin";
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [refresh, setRefresh] = useState(0);

  useEffect(() => {
    let active = true;
    async function loadOptions() {
      try {
        const data = await getInventoryOptions();
        if (active) setOptions({
          tipo: data.tipo ?? [], ciudad: data.ciudad ?? [], localidad: data.localidad ?? [],
        });
      } catch (err) {
        if (active) setError(err.message || "No se pudieron cargar las opciones de filtros.");
      }
    }
    loadOptions();
    return () => { active = false; };
  }, [refresh]);

  useEffect(() => {
    let active = true;
    async function load() {
      setLoading(true);
      setError("");
      try {
        const data = await getInventory({
          q: applied.q.trim(),
          id: applied.id,
          serial: applied.serial,
          tipo: applied.tipo,
          ciudad: applied.ciudad,
          localidad: applied.localidad,
          eos: applied.eos,
          page,
          page_size: PAGE_SIZE,
        });
        if (!active) return;
        const list = Array.isArray(data) ? data : data.items ?? [];
        if (!Array.isArray(list)) throw new Error("Formato de inventario no reconocido.");
        const count = Array.isArray(data) ? data.length : Number(data.pagination?.total ?? 0);
        setRecords(list);
        setTotal(count);
        setPages(Math.max(1, Number(data.pagination?.total_pages ?? Math.ceil(count / PAGE_SIZE))));
      } catch (err) {
        if (active) {
          setError(err.message || "No fue posible cargar el inventario.");
          setRecords([]);
          setTotal(0);
          setPages(1);
        }
      } finally {
        if (active) setLoading(false);
      }
    }
    load();
    return () => { active = false; };
  }, [applied, page, refresh]);

  const types = options.tipo;
  const cities = options.ciudad;
  const localities = options.localidad;

  const updateFilter = (key, value) => setFilters((current) => ({ ...current, [key]: value }));
  const submitSearch = (event) => {
    event.preventDefault();
    setPage(1);
    setApplied({ ...filters });
  };
  const openDevice = (item) => {
    setSelected(item);
    setEditing(false);
    setDraft(null);
    setEditError("");
    setEditSuccess("");
  };

  const closeDevice = () => {
    if (saving) return;
    setSelected(null);
    setDraft(null);
    setEditing(false);
  };

  const startEdit = () => {
    setDraft({
      ...selected,
      eos: selected.eos ? String(selected.eos).slice(0, 10) : "",
    });
    setEditing(true);
    setEditError("");
    setEditSuccess("");
  };

  const saveDevice = async () => {
    if (!selected || !canEdit || saving) return;
    const changes = {};
    for (const [key] of FIELDS) {
      if (key === "id") continue;
      const next = String(draft?.[key] ?? "").trim();
      const previous = key === "eos"
        ? String(selected[key] ?? "").slice(0, 10)
        : String(selected[key] ?? "").trim();
      // Los campos vacíos o "-" no reemplazan valores existentes.
      if (isBlankMarker(next)) continue;
      if (next !== previous) changes[key] = next;
    }
    if (!Object.keys(changes).length) {
      setEditing(false);
      setEditSuccess("No se detectaron cambios.");
      return;
    }
    setSaving(true);
    setEditError("");
    try {
      const result = await updateInventoryDevice(selected.id, changes);
      const updated = result.item;
      if (!updated) throw new Error("La API no devolvió el activo actualizado.");
      setSelected(updated);
      setRecords((current) => current.map((item) => item.id === updated.id ? updated : item));
      setEditing(false);
      setEditSuccess(result.actualizado ? "Cambios guardados en Oracle correctamente." : "No hubo diferencias para guardar.");
      setRefresh((value) => value + 1);
    } catch (err) {
      setEditError(err.message || "No se pudo actualizar el activo.");
    } finally {
      setSaving(false);
    }
  };

  const clearFilters = () => {
    setFilters({ ...EMPTY_FILTERS });
    setApplied({ ...EMPTY_FILTERS });
    setPage(1);
  };

  return (
    <div className="space-y-6 pb-10">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-sm font-semibold text-violet-600">
            Assets Management
          </p>
          <h1 className="mt-1 text-3xl font-bold text-slate-900">
            Inventario tecnológico
          </h1>
          <p className="mt-2 text-sm text-slate-500">
            Consulta de dispositivos registrados en Oracle.
          </p>
        </div>

        <button
          type="button"
          onClick={() => setRefresh((value) => value + 1)}
          disabled={loading}
          className="flex items-center gap-2 rounded-xl bg-violet-600 px-4 py-3 text-sm font-semibold text-white hover:bg-violet-700 disabled:opacity-50"
        >
          <RefreshCw
            size={17}
            className={loading ? "animate-spin" : ""}
          />
          Actualizar
        </button>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-blue-600 text-white">
            <Database size={24} />
          </div>
          <p className="text-sm font-medium text-slate-600">
            Dispositivos encontrados
          </p>
          <p className="mt-1 text-3xl font-bold text-slate-900">
            {total.toLocaleString("es-EC")}
          </p>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-violet-600 text-white">
            <Boxes size={24} />
          </div>
          <p className="text-sm font-medium text-slate-600">
            Registros en esta página
          </p>
          <p className="mt-1 text-3xl font-bold text-slate-900">
            {records.length}
          </p>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-emerald-600 text-white">
            <HardDrive size={24} />
          </div>
          <p className="text-sm font-medium text-slate-600">
            Página actual
          </p>
          <p className="mt-1 text-3xl font-bold text-slate-900">
            {page} / {pages}
          </p>
        </div>
      </div>

      <form onSubmit={submitSearch} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="mb-5 flex items-center gap-2">
          <Filter size={18} className="text-violet-600" />
          <h2 className="font-semibold text-slate-900">Filtros del inventario</h2>
        </div>
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          <label className="space-y-2">
            <span className="text-xs font-medium text-slate-600">Dispositivo, serial, IP, fabricante o comentario</span>
            <div className="relative">
              <Search size={16} className="absolute left-3 top-3 text-slate-400" />
              <input value={filters.q} onChange={(e) => updateFilter("q", e.target.value)}
                placeholder="Buscar dispositivo o comentario"
                className="w-full rounded-lg border border-slate-200 py-2 pl-9 pr-3 text-sm outline-none focus:border-violet-400" />
            </div>
          </label>
          <label className="space-y-2">
            <span className="text-xs font-medium text-slate-600">ID del dispositivo</span>
            <input type="number" min="1" value={filters.id} onChange={(e) => updateFilter("id", e.target.value)}
              placeholder="Buscar por ID exacto"
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-violet-400" />
          </label>
          <label className="space-y-2">
            <span className="text-xs font-medium text-slate-600">Serial exacto</span>
            <input value={filters.serial} onChange={(e) => updateFilter("serial", e.target.value)}
              placeholder="Filtrar por número de serie"
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-violet-400" />
          </label>
          <label className="space-y-2">
            <span className="text-xs font-medium text-slate-600">Tipo de dispositivo</span>
            <select value={filters.tipo} onChange={(e) => updateFilter("tipo", e.target.value)}
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm">
              <option value="">Todos los tipos</option>
              {types.map((value) => <option key={value} value={value}>{value}</option>)}
            </select>
          </label>
          <label className="space-y-2">
            <span className="text-xs font-medium text-slate-600">Ciudad</span>
            <select value={filters.ciudad} onChange={(e) => setFilters((current) => ({ ...current, ciudad: e.target.value, localidad: "" }))}
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm">
              <option value="">Todas las ciudades</option>
              {cities.map((value) => <option key={value} value={value}>{value}</option>)}
            </select>
          </label>
          <label className="space-y-2">
            <span className="text-xs font-medium text-slate-600">Localidad</span>
            <select value={filters.localidad} onChange={(e) => updateFilter("localidad", e.target.value)}
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm">
              <option value="">Todas las localidades</option>
              {localities.map((value) => <option key={value} value={value}>{value}</option>)}
            </select>
          </label>
          <label className="space-y-2">
            <span className="text-xs font-medium text-slate-600">Estado EOS</span>
            <select value={filters.eos} onChange={(e) => updateFilter("eos", e.target.value)}
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm">
              <option value="">Todos los EOS</option>
              <option value="vencido">EOS vencidos</option>
              <option value="generico">EOS genéricos (comentario: no anunciado)</option>
              <option value="vigente">EOS vigentes</option>
            </select>
          </label>
        </div>
        <div className="mt-4 flex flex-wrap justify-end gap-3">
          <button type="button" onClick={clearFilters}
            className="rounded-lg border border-slate-200 px-4 py-2 text-sm text-slate-600 hover:bg-slate-50">Limpiar</button>
          <button type="submit" disabled={loading}
            className="rounded-lg bg-violet-600 px-5 py-2 text-sm font-medium text-white hover:bg-violet-700 disabled:opacity-50">Aplicar filtros</button>
        </div>
      </form>

      {error && (
        <div className="flex items-center gap-2 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          <AlertTriangle size={19} />
          {error}
        </div>
      )}

      <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="border-b border-slate-200 p-5">
          <h2 className="font-semibold text-slate-900">
            Dispositivos registrados
          </h2>
          <p className="mt-1 text-xs text-slate-500">
            Selecciona un registro para consultar su información completa.
          </p>
        </div>

        <div className="overflow-x-auto">
          <table className="w-max min-w-full text-left text-sm">
            <thead className="bg-slate-100 text-slate-600">
              <tr>
                {FIELDS.map(([key, label]) => (
                  <th
                    key={key}
                    scope="col"
                    className="whitespace-nowrap px-4 py-3 font-semibold"
                  >
                    {label}
                  </th>
                ))}
              </tr>
            </thead>

            <tbody>
              {records.map((item, index) => (
                <tr
                  key={item.id ?? index}
                  onClick={() => openDevice(item)}
                  className="cursor-pointer border-t border-slate-100 hover:bg-violet-50"
                >
                  {FIELDS.map(([key]) => (
                    <td
                      key={key}
                      className={`
                        px-4 py-3 text-slate-700
                        ${
                          key === "dispositivo"
                            ? "min-w-[380px] max-w-[500px] whitespace-normal break-words"
                            : "whitespace-nowrap"
                        }
                      `}
                      title={display(item[key])}
                    >
                      {display(item[key])}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {!loading && records.length === 0 && !error && (
          <div className="p-12 text-center">
            <Boxes className="mx-auto mb-3 h-10 w-10 text-slate-300" />
            <p className="font-medium text-slate-600">
              No se encontraron dispositivos.
            </p>
            <p className="mt-1 text-sm text-slate-400">
              Los registros aparecerán después de importarlos.
            </p>
          </div>
        )}

        {loading && (
          <p className="p-6 text-center text-sm text-slate-500">
            Consultando inventario...
          </p>
        )}

        <div className="flex items-center justify-between border-t border-slate-200 p-4">
          <span className="text-sm text-slate-500">
            {total} registros encontrados
          </span>

          <div className="flex items-center gap-3">
            <button
              disabled={loading || page <= 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              className="rounded-lg border border-slate-200 p-2 disabled:opacity-40"
            >
              <ChevronLeft size={18} />
            </button>

            <span className="text-sm text-slate-700">
              {page} de {pages}
            </span>

            <button
              disabled={loading || page >= pages}
              onClick={() => setPage((p) => Math.min(pages, p + 1))}
              className="rounded-lg border border-slate-200 p-2 disabled:opacity-40"
            >
              <ChevronRight size={18} />
            </button>
          </div>
        </div>
      </section>

      {selected && (
        <div className="fixed inset-0 z-50 flex justify-end bg-slate-950/40">
          <div className="h-full w-full max-w-xl overflow-y-auto bg-white p-6 shadow-2xl">
            <div className="mb-6 flex items-start justify-between">
              <div>
                <p className="text-xs font-semibold text-violet-600">
                  DETALLE DEL ACTIVO
                </p>
                <h2 className="mt-1 text-xl font-bold text-slate-900">
                  {display(selected.dispositivo)}
                </h2>
              </div>

              <button
                onClick={closeDevice}
                className="rounded-lg p-2 hover:bg-slate-100"
                aria-label="Cerrar detalle"
              >
                <X size={22} />
              </button>
            </div>

            <div className="mb-5 flex flex-wrap items-center gap-2">
              {canEdit && !editing && (
                <button type="button" onClick={startEdit}
                  className="inline-flex items-center gap-2 rounded-xl bg-violet-600 px-4 py-2 text-sm font-semibold text-white hover:bg-violet-700">
                  <Pencil size={16} /> Editar activo
                </button>
              )}
              {canEdit && editing && (
                <>
                  <button type="button" disabled={saving} onClick={saveDevice}
                    className="inline-flex items-center gap-2 rounded-xl bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-700 disabled:opacity-50">
                    <Save size={16} /> {saving ? "Guardando..." : "Guardar cambios"}
                  </button>
                  <button type="button" disabled={saving} onClick={() => { setEditing(false); setDraft(null); setEditError(""); }}
                    className="rounded-xl border border-slate-300 px-4 py-2 text-sm text-slate-700 hover:bg-slate-50 disabled:opacity-50">
                    Cancelar
                  </button>
                </>
              )}
            </div>

            {editing && (
              <p className="mb-3 text-xs text-slate-500">
                Los campos vacíos o con «-» se ignoran al guardar y no generan cambios en el historial.
              </p>
            )}

            {editError && (
              <p role="alert" className="mb-4 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">{editError}</p>
            )}
            {editSuccess && !editing && (
              <p role="status" className="mb-4 flex items-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-700">
                <CheckCircle2 size={16} /> {editSuccess}
              </p>
            )}

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              {FIELDS.map(([key, label]) => (
                <div key={key} className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                  <label htmlFor={editing && key !== "id" ? `asset-edit-${key}` : undefined}
                    className="text-xs font-medium text-slate-500">{label}</label>
                  {editing && key !== "id" ? (
                    key === "comentario" || key === "licencia" ? (
                      <textarea id={`asset-edit-${key}`} rows={3} disabled={saving}
                        value={draft?.[key] ?? ""}
                        onChange={(e) => setDraft((current) => ({ ...current, [key]: e.target.value }))}
                        className="mt-2 w-full rounded-lg border border-slate-300 bg-white p-2 text-sm text-slate-800 outline-none focus:border-violet-500" />
                    ) : (
                      <input id={`asset-edit-${key}`} type={key === "eos" ? "date" : "text"}
                        disabled={saving} value={draft?.[key] ?? ""}
                        onChange={(e) => setDraft((current) => ({ ...current, [key]: e.target.value }))}
                        className="mt-2 w-full rounded-lg border border-slate-300 bg-white p-2 text-sm text-slate-800 outline-none focus:border-violet-500" />
                    )
                  ) : (
                    <p className="mt-1 break-words text-sm font-semibold text-slate-800">{display(selected[key])}</p>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}