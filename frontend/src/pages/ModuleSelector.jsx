import {
  ArrowRight,
  Boxes,
  Construction,
  Network,
  ShieldCheck,
  Wrench,
} from "lucide-react";
import { useNavigate } from "react-router-dom";
import { readStoredUser, logout } from "../services/authSession";

const modules = [
  {
    id: "sox",
    title: "Control SOX / VPN",
    description:
      "Administración de campañas, validaciones VPN, REQ, responsables e histórico.",
    icon: ShieldCheck,
    path: "/SOX/Controls/Control_7/dashboard",
    enabled: true,
    color: "bg-blue-600",
  },
  {
    id: "assets",
    title: "Control de activos",
    description:
      "Inventario centralizado de equipos, responsables, ubicaciones y estados.",
    icon: Boxes,
    path: "/assets/dashboard",
    enabled: true,
    color: "bg-violet-600",
  },
  {
    id: "network",
    title: "Activos de red",
    description:
      "Control de routers, switches, firewalls, enlaces y dispositivos de red.",
    icon: Network,
    path: "/network",
    enabled: true,
    color: "bg-cyan-600",
  },
  {
    id: "maintenance",
    title: "Mantenimiento",
    description:
      "Gestión de mantenimientos preventivos, correctivos y seguimiento técnico.",
    icon: Wrench,
    path: "/maintenance",
    enabled: true,
    color: "bg-amber-500",
  },
];

export default function ModuleSelector() {
  const navigate = useNavigate();

  const loggedUser = readStoredUser();
  const rol = loggedUser?.rol;
  const allowedModules = modules.filter((module) => module.id === "sox" ? ["administrador", "desarrollador", "gerencial"].includes(rol) : module.id === "assets" ? ["administrador", "assets_admin", "assets_viewer"].includes(rol) : ["administrador", "desarrollador"].includes(rol));

  const handleOpenModule = (module) => {
    if (!module.enabled) return;

    if (module.id === "sox") {

      if (
        loggedUser?.rol === "administrador" ||
        loggedUser?.rol === "desarrollador" ||
        loggedUser?.rol === "gerencial"
      ) {
        navigate("/SOX/Controls/Control_7/dashboard");
        return;
      }

    }

    navigate(module.path);
  };

  const getInitials = (name = "") =>
    name
      .split(" ")
      .filter(Boolean)
      .slice(0, 2)
      .map((word) => word[0])
      .join("")
      .toUpperCase();

  return (
    <div className="min-h-screen bg-slate-100">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-5">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">
              Portal de módulos HITSS
            </h1>

            <p className="mt-1 text-sm text-slate-500">
              Seleccione el módulo que desea gestionar.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-full bg-blue-600 font-bold text-white">
              {getInitials(loggedUser?.username)}
            </div>

            <div>
              <p className="text-sm font-bold text-slate-900">
                {loggedUser?.username || "Usuario"}
              </p>

              <p className="text-xs text-slate-500">
                {loggedUser?.rol || "Sin rol"}
              </p>
            </div>
          </div>
          <button onClick={logout} className="rounded-lg border border-slate-300 px-3 py-2 text-sm">Cerrar sesión</button>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-6 py-10">
        <div className="mb-8">
          <h2 className="text-3xl font-bold text-slate-900">
            Sistemas disponibles
          </h2>

          <p className="mt-2 max-w-3xl text-slate-500">
            Desde este portal podrá acceder a los distintos módulos de control,
            seguimiento y administración de activos.
          </p>
        </div>

        <div className="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-3">
          {allowedModules.map((module) => {
            const Icon = module.icon;

            return (
              <article
                key={module.id}
                className={`relative rounded-2xl border bg-white p-6 shadow-sm transition ${
                  module.enabled
                    ? "border-slate-200 hover:-translate-y-1 hover:shadow-md"
                    : "border-slate-200 opacity-70"
                }`}
              >
                {!module.enabled && (
                  <span className="absolute right-5 top-5 rounded-full bg-slate-100 px-3 py-1 text-xs font-bold text-slate-500">
                    Próximamente
                  </span>
                )}

                <div
                  className={`flex h-14 w-14 items-center justify-center rounded-2xl text-white ${module.color}`}
                >
                  <Icon size={28} />
                </div>

                <h3 className="mt-5 text-xl font-bold text-slate-900">
                  {module.title}
                </h3>

                <p className="mt-2 min-h-16 text-sm leading-6 text-slate-500">
                  {module.description}
                </p>

                <button
                  type="button"
                  onClick={() => handleOpenModule(module)}
                  disabled={!module.enabled}
                  className={`mt-6 flex w-full items-center justify-center gap-2 rounded-xl px-4 py-3 text-sm font-bold transition ${
                    module.enabled
                      ? "bg-slate-900 text-white hover:bg-slate-800"
                      : "cursor-not-allowed bg-slate-100 text-slate-400"
                  }`}
                >
                  {module.enabled ? (
                    <>
                      Ingresar
                      <ArrowRight size={18} />
                    </>
                  ) : (
                    <>
                      <Construction size={18} />
                      No disponible
                    </>
                  )}
                </button>
              </article>
            );
          })}
        </div>
      </main>
    </div>
  );
}