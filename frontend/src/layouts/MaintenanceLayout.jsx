import {
  Wrench,
  Home,
  LayoutGrid,
  CalendarDays,
  ClipboardList,
  Settings,
} from "lucide-react";

import { NavLink, Outlet } from "react-router-dom";
import ModuleNavbar from "../components/common/ModuleNavbar";


function MenuItem({ to, icon: Icon, label }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        `flex h-11 items-center gap-3 rounded-xl px-3 text-sm transition ${
          isActive
            ? "bg-orange-600 text-white"
            : "text-white hover:bg-white/10"
        }`
      }
    >
      <Icon size={19}/>
      <span>{label}</span>
    </NavLink>
  );
}


export default function MaintenanceLayout(){

  return (

    <div className="min-h-screen bg-slate-50">


      <aside
        className="
        fixed left-0 top-0 hidden h-screen w-64
        bg-gradient-to-b from-orange-950 to-orange-900
        p-5 text-white lg:block
        "
      >

        <div className="mb-9 flex items-center gap-3">

          <div className="
            flex h-12 w-12 items-center justify-center
            rounded-2xl bg-orange-600
          ">
            <Wrench size={28}/>
          </div>


          <div>
            <h1 className="text-2xl font-bold">
              Mantenimiento
            </h1>

            <p className="text-xs text-orange-200">
              Gestión técnica
            </p>
          </div>

        </div>


        <nav className="space-y-2">


          <MenuItem
            to="/modules"
            icon={LayoutGrid}
            label="Portal de módulos"
          />


          <MenuItem
            to="/maintenance/dashboard"
            icon={Home}
            label="Dashboard"
          />


          <p className="px-2 pt-6 text-xs font-bold text-orange-300">
            GESTIÓN
          </p>


          <MenuItem
            to="/maintenance/programming"
            icon={CalendarDays}
            label="Programación"
          />


          <MenuItem
            to="/maintenance/orders"
            icon={ClipboardList}
            label="Órdenes"
          />


          <p className="px-2 pt-6 text-xs font-bold text-orange-300">
            ADMINISTRACIÓN
          </p>


          <MenuItem
            to="/settings"
            icon={Settings}
            label="Configuración"
          />


        </nav>


      </aside>


      <main className="lg:ml-64">

        <ModuleNavbar />

        <section className="p-6">

          <Outlet />

        </section>


      </main>


    </div>

  );
}