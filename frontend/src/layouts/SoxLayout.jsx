
import { Outlet } from "react-router-dom";
import Navbar from "../components/SOX/layout/Navbar";
import Sidebar from "../components/SOX/layout/Sidebar";

export default function SoxLayout() {
  return (
    <div className="min-h-screen bg-slate-50 text-slate-950">
      <Sidebar />

      <main className="lg:ml-64">
        <Navbar module="SOX" />

        <section className="p-6">
          <Outlet />
        </section>
      </main>
    </div>
  );
}
