import { Home, LayoutGrid, Shield } from "lucide-react";
import { useLocation } from "react-router-dom";
import controlConfig from "../../../constants/controlConfig";
import { readStoredUser } from "../../../services/authSession";
import SidebarItem from "./SidebarItem";
import ControlSectionsNav from "./ControlSectionsNav";
import Control7Sidebar from "../control_7/Sidebar";

/** Marco de navegación compartido. Solo presenta las opciones del control activo. */
export default function Sidebar() {
  const { pathname, search } = useLocation();
  const role = String(readStoredUser()?.rol || "").trim().toLowerCase();
  const id = pathname.match(/\/SOX\/Controls\/Control_(\d+)(?:\/|$)/i)?.[1];
  const dashboard = controlConfig[id]?.path || "/SOX/Controls/Control_7/dashboard";
  const documental = ["1", "2", "3", "5", "6"].includes(id);
  return (
    <aside className="fixed left-0 top-0 hidden h-screen w-64 overflow-y-auto bg-gradient-to-b from-slate-950 to-slate-900 p-5 text-white lg:block">
      <div className="mb-9 flex items-center gap-3">
        <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-blue-600"><Shield size={28}/></div>
        <div><h1 className="text-2xl font-bold">SOX</h1><p className="text-xs text-slate-300">Sistema de Validación</p></div>
      </div>
      <nav className="space-y-1.5" aria-label="Navegación del módulo SOX">
        {role !== "gerencial" && <SidebarItem to="/modules" icon={LayoutGrid} label="Portal de módulos" active={pathname === "/modules"}/>}
        {!documental && <SidebarItem to={dashboard} icon={Home} label="Dashboard"
          active={pathname.toLowerCase() === dashboard.toLowerCase()}/>}
        <ControlSectionsNav controlId={id} pathname={pathname} search={search}/>
        {id === "7" && <Control7Sidebar role={role} pathname={pathname}/>}
      </nav>
    </aside>
  );
}
