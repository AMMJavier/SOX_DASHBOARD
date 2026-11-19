/**
 * Paginación compacta: primera, última y las páginas vecinas a la actual, con "…" entre
 * medio. Así no se desborda cuando hay muchas páginas (p. ej. 80 responsables).
 */
function pageItems(current, total) {
  const pages = new Set([1, total, current - 1, current, current + 1]);
  if (current <= 3) [2, 3, 4].forEach((p) => pages.add(p));
  if (current >= total - 2) [total - 3, total - 2, total - 1].forEach((p) => pages.add(p));
  const sorted = [...pages].filter((p) => p >= 1 && p <= total).sort((a, b) => a - b);
  const items = [];
  sorted.forEach((page, index) => {
    if (index > 0 && page - sorted[index - 1] > 1) items.push(`gap-${page}`);
    items.push(page);
  });
  return items;
}

export default function Pagination({ currentPage, totalPages, onPageChange }) {
  if (!totalPages || totalPages <= 1) return null;
  const current = Math.min(Math.max(currentPage, 1), totalPages);

  return (
    <nav className="mt-6 flex flex-wrap items-center justify-center gap-1" aria-label="Paginación">
      <button type="button" className="px-3 py-2 disabled:opacity-40" disabled={current === 1}
        onClick={() => onPageChange(current - 1)} aria-label="Página anterior">‹</button>
      {pageItems(current, totalPages).map((item) => (typeof item === "string"
        ? <span key={item} className="px-2 py-2 text-slate-400">…</span>
        : <button key={item} type="button" onClick={() => onPageChange(item)} aria-current={current === item ? "page" : undefined}
            className={current === item ? "bg-cyan-500 px-4 py-2 text-white" : "px-4 py-2"}>{item}</button>))}
      <button type="button" className="px-3 py-2 disabled:opacity-40" disabled={current === totalPages}
        onClick={() => onPageChange(current + 1)} aria-label="Página siguiente">›</button>
    </nav>
  );
}
