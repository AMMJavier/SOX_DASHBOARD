import { useEffect, useState } from "react";
import { SECONDARY } from "./ControlUI";

/**
 * Lista paginada de documentos del repositorio para adjuntar a un correo.
 * La selección se conserva al cambiar de página (vive en el componente padre).
 */
export default function RepositoryFilePicker({ files, selected, onToggle, legend, pageSize = 3 }) {
  const [page, setPage] = useState(1);
  const pageCount = Math.max(1, Math.ceil(files.length / pageSize));
  useEffect(() => { if (page > pageCount) setPage(pageCount); }, [page, pageCount]);
  if (!files.length) return null;
  const current = Math.min(page, pageCount);
  const rows = files.slice((current - 1) * pageSize, current * pageSize);

  return <fieldset className="mt-4">
    <legend className="text-xs font-semibold text-slate-600">{legend}
      {selected.length > 0 && <span className="ml-2 font-normal text-blue-700">{selected.length} seleccionado(s)</span>}</legend>
    <ul className="mt-2 space-y-2">{rows.map((f) => <li key={f.id}>
      <label className="flex cursor-pointer items-center gap-3 rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm hover:bg-slate-100">
        <input type="checkbox" checked={selected.includes(f.id)} onChange={() => onToggle(f.id)} className="h-4 w-4"/>
        <span className="min-w-0 flex-1"><span className="block truncate font-semibold text-slate-700">{f.nombre}</span>
          <span className="text-xs text-slate-500">{f.origen}{f.bytes ? ` · ${(f.bytes / 1024).toFixed(1)} KB` : ""}</span></span>
      </label>
    </li>)}</ul>
    {files.length > pageSize && <div className="mt-3 flex flex-wrap items-center justify-between gap-3 text-sm text-slate-600">
      <span>Mostrando {(current - 1) * pageSize + 1}–{Math.min(current * pageSize, files.length)} de {files.length} documentos</span>
      <div className="flex items-center gap-2">
        <button type="button" className={SECONDARY} disabled={current <= 1} onClick={() => setPage(current - 1)}>Anterior</button>
        <span className="px-2 font-semibold">Página {current} de {pageCount}</span>
        <button type="button" className={SECONDARY} disabled={current >= pageCount} onClick={() => setPage(current + 1)}>Siguiente</button>
      </div>
    </div>}
  </fieldset>;
}
