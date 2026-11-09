import { Outlet } from "react-router-dom";
import Sidebar from "../components/Assets/Sidebar";

export default function AssetsLayout() {
  return (
    <div className="min-h-screen bg-slate-50">

      {/* Sidebar independiente del módulo Activos */}
      <Sidebar />

      {/* Contenido principal */}
      <main className="lg:ml-64 p-6">
        <Outlet />
      </main>

    </div>
  );
}