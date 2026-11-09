import {
  Boxes,
  Home,
  LayoutGrid,
  MapPin,
  FileText,
  Users,
} from "lucide-react";

import { NavLink } from "react-router-dom";
import { logout } from "../../services/authSession";

// Componente para cada opción del menú
function MenuItem({ to, icon: Icon, label }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        `flex h-11 items-center gap-3 rounded-xl px-3 text-sm transition ${
          isActive
            ? "bg-violet-600 text-white"
            : "text-slate-200 hover:bg-white/10"
        }`
      }
    >
      <Icon size={19} />
      <span>{label}</span>
    </NavLink>
  );
}

export default function Sidebar() {
  let user = null;

  try {
    user = JSON.parse(localStorage.getItem("soxUser"));
  } catch {
    // Usuario no disponible
  }

  const role = user?.rol;

  const isAssetsUser =
    role === "assets_admin" ||
    role === "assets_viewer";

  const canManageAssets = ["administrador", "assets_admin"].includes(role);

  return (
    <aside className="fixed left-0 top-0 hidden h-screen w-64 bg-gradient-to-b from-violet-950 to-violet-900 p-5 text-white lg:block">

      {/* ENCABEZADO */}
      <div className="mb-9 flex items-center gap-3">
        <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-violet-600">
          <Boxes size={28} />
        </div>

        <div>
          <h1 className="text-2xl font-bold">
            Activos
          </h1>

          <p className="text-xs text-violet-200">
            Control tecnológico
          </p>
        </div>
      </div>

      {/* NAVEGACIÓN */}
      <nav className="space-y-2">

        {/* PORTAL PRINCIPAL */}
        {!isAssetsUser && (
          <MenuItem
            to="/modules"
            icon={LayoutGrid}
            label="Portal de módulos"
          />
        )}

        {/* DASHBOARD */}
        <MenuItem
          to="/assets/dashboard"
          icon={Home}
          label="Dashboard"
        />

        {/* GESTIÓN */}
        <p className="px-2 pt-6 text-xs font-bold text-violet-300">
          GESTIÓN
        </p>

        <MenuItem
          to="/assets/inventory"
          icon={Boxes}
          label="Inventario"
        />

        <MenuItem
          to="/assets/locations"
          icon={MapPin}
          label="Ubicaciones"
        />

        {canManageAssets && (
          <MenuItem
            to="/assets/upload"
            icon={FileText}
            label="Upload file"
          />
        )}

        {/* REPORTES */}
        <p className="px-2 pt-6 text-xs font-bold text-violet-300">
          Reportes
        </p>

        <MenuItem
          to="/assets/logs"
          icon={FileText}
          label="Historial de cambios"
        />

        {canManageAssets && (
          <MenuItem to="/assets/users" icon={Users} label="Administrar usuarios" />
        )}
        <button type="button" onClick={logout} className="w-full rounded-lg border border-white/30 px-3 py-2 text-left text-sm hover:bg-white/10">Cerrar sesión</button>

      </nav>
    </aside>
  );
}


    