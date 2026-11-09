import { Link } from "react-router-dom";

/** Enlace visual compartido. `active` se calcula en el sidebar maestro,
 * para distinguir correctamente rutas con ?vista=... . */
export default function SidebarItem({ to, label, icon: Icon, active = false }) {
  return (
    <Link
      to={to}
      aria-current={active ? "page" : undefined}
      className={`flex min-h-11 items-center gap-3 rounded-xl px-3 py-2 text-sm transition-colors ${
        active
          ? "bg-blue-600 font-semibold text-white"
          : "text-slate-200 hover:bg-white/10"
      }`}
    >
      <Icon size={19} className="shrink-0" aria-hidden="true" />
      <span className="leading-5">{label}</span>
    </Link>
  );
}
