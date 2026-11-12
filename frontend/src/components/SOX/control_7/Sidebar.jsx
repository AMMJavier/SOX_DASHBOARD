import { Database, Download, FileText, ScrollText, Settings, UserCog } from "lucide-react";
import SidebarItem from "../layout/SidebarItem";

/** Opciones exclusivas del Control 7. No dibuja un segundo <aside>. */
export default function Sidebar({ role, pathname }) {
  const admin = ["administrador", "desarrollador"].includes(role);
  if (!admin) return null;
  const current = pathname.toLowerCase();
  const item = (path, icon, label) => (
    <SidebarItem key={path} to={path} icon={icon} label={label}
      active={current === path.toLowerCase()} />
  );
  return (
    <>
      <p className="px-2 pb-1 pt-6 text-xs font-bold uppercase tracking-wider text-slate-400">Gestión · Control 7</p>
      {item("/SOX/Controls/Control_7/campaigns", Database, "Campañas")}
      {item("/SOX/Controls/Control_7/history", FileText, "Histórico")}
      {item("/SOX/Controls/Control_7/reports", Download, "Exportaciones")}
      <p className="px-2 pb-1 pt-6 text-xs font-bold uppercase tracking-wider text-slate-400">Administración</p>
      {item("/SOX/Controls/Control_7/logs", ScrollText, "Logs")}
      {role === "administrador" && item("/SOX/Controls/Control_7/users", UserCog, "Usuarios")}
      {role === "administrador" && item("/SOX/Controls/Control_7/settings", Settings, "Configuración")}
    </>
  );
}
