import { Outlet, NavLink } from "react-router-dom";

import {
  Network,
  LayoutDashboard,
  Server,
  Settings,
  LayoutGrid,
} from "lucide-react";

import ModuleNavbar from "../components/common/ModuleNavbar";


function MenuItem({ to, icon: Icon, label }) {

  return (

    <NavLink
      to={to}
      className={({isActive}) =>
        `flex h-11 items-center gap-3 rounded-xl px-3 text-sm transition ${
          isActive
          ? "bg-cyan-600 text-white"
          : "text-white hover:bg-white/10"
        }`
      }
    >

      <Icon size={19}/>

      <span>
        {label}
      </span>

    </NavLink>

  );

}



export default function NetworkLayout() {


  return (

    <div className="min-h-screen bg-slate-50">


      <aside
        className="
        fixed left-0 top-0 hidden h-screen w-64
        bg-gradient-to-b from-cyan-950 to-cyan-900
        p-5 text-white lg:block
        "
      >


        {/* LOGO */}

        <div className="mb-9 flex items-center gap-3">


          <div
            className="
            flex h-12 w-12 items-center justify-center
            rounded-2xl bg-cyan-600
            "
          >

            <Network size={28}/>

          </div>


          <div>

            <h1 className="text-2xl font-bold">
              Red
            </h1>


            <p className="text-xs text-cyan-200">
              Control de infraestructura
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
            to="/network/dashboard"
            icon={LayoutDashboard}
            label="Dashboard"
          />



          <p className="px-2 pt-6 text-xs font-bold text-cyan-300">
            GESTIÓN
          </p>



          <MenuItem
            to="/network/equipment"
            icon={Server}
            label="Equipos"
          />



          <p className="px-2 pt-6 text-xs font-bold text-cyan-300">
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