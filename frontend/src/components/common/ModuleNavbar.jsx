import { Bell } from "lucide-react";
import { logout } from "../../services/authSession";

export default function ModuleNavbar({
  moduleName
}) {

  const loggedUser = JSON.parse(
    localStorage.getItem("soxUser")
  );

  const getInitials = (name = "") =>
    name
      .split(" ")
      .filter(Boolean)
      .slice(0,2)
      .map(x => x[0])
      .join("")
      .toUpperCase();


  return (
    <header className="h-20 border-b border-slate-200 bg-white flex items-center justify-between px-6">

      <div className="flex items-center gap-5">

        {moduleName && (
          <div className="text-sm font-bold text-slate-700">
            {moduleName}
          </div>
        )}

      </div>


      <div className="flex items-center gap-6">

        <Bell size={22} className="text-slate-700"/>
        <button onClick={logout} className="rounded-md border px-3 py-2 text-sm">Salir</button>


        <div className="flex items-center gap-3">

          <div className="flex h-11 w-11 items-center justify-center rounded-full bg-blue-600 text-white font-bold">
            {getInitials(loggedUser?.name)}
          </div>


          <div>
            <p className="text-sm font-bold text-slate-900">
              {loggedUser?.name || "Usuario"}
            </p>

            <p className="text-xs text-slate-500">
              {loggedUser?.role || ""}
            </p>
          </div>

        </div>

      </div>

    </header>
  );
}