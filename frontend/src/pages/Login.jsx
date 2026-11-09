import { useState } from "react";
import { Shield } from "lucide-react";
import { loginUser, getCurrentUser } from "../services/authService";
import { saveSession } from "../services/authSession";
import { useNavigate, useSearchParams } from "react-router-dom";

export default function Login() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [form, setForm] = useState({ user: "", password: "" });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleChange = (event) => {
    setForm((current) => ({ ...current, [event.target.name]: event.target.value }));
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      const result = await loginUser(form.user.trim(), form.password);
      if (!result.access_token) throw new Error("El servidor no devolvió un token JWT");
      const profile = await getCurrentUser(result.access_token);
      const user = saveSession(result.access_token, profile);
      if (user.rol === "assets_admin" || user.rol === "assets_viewer") {
        navigate("/assets/dashboard", { replace: true });
      } else if (user.rol === "gerencial") {
        navigate("/SOX/Controls/Control_7/dashboard", { replace: true });
      } else {
        navigate("/modules", { replace: true });
      }
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || "No se pudo iniciar sesión");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen bg-slate-100">
      <div className="hidden w-1/2 items-center justify-center bg-gradient-to-br from-slate-950 to-blue-950 text-white lg:flex">
        <div className="max-w-md">
          <div className="mb-6 flex h-20 w-20 items-center justify-center rounded-3xl bg-blue-600"><Shield size={46} /></div>
          <h1 className="text-4xl font-bold">Portal de Control Tecnológico</h1>
          <p className="mt-2 text-xl text-slate-300">Sistema de Validación</p>
          <div className="my-8 h-px bg-white/20" />
          <p className="text-slate-300">Gestión centralizada de activos, infraestructura, mantenimiento y validaciones.</p>
        </div>
      </div>
      <div className="flex w-full items-center justify-center lg:w-1/2">
        <form onSubmit={handleSubmit} className="w-full max-w-md rounded-3xl bg-white p-10 shadow-xl">
          <h2 className="text-3xl font-bold text-slate-950">Iniciar sesión</h2>
          <p className="mt-2 text-slate-500">Ingresa con tu cuenta local o corporativa LDAP.</p>
          {params.get("expired") && <p className="mt-4 rounded-xl bg-amber-50 p-3 text-sm text-amber-800">Tu sesión expiró. Inicia sesión nuevamente.</p>}
          {error && <div className="mt-6 rounded-xl bg-red-50 p-4 text-sm font-semibold text-red-600" role="alert">{error}</div>}
          <div className="mt-8">
            <label htmlFor="user" className="text-sm font-bold text-slate-700">Usuario</label>
            <input id="user" name="user" autoComplete="username" value={form.user} onChange={handleChange} required className="mt-2 h-12 w-full rounded-xl border border-slate-300 px-4 outline-none focus:border-blue-600" />
          </div>
          <div className="mt-5">
            <label htmlFor="password" className="text-sm font-bold text-slate-700">Contraseña</label>
            <input id="password" name="password" value={form.password} onChange={handleChange} type="password" autoComplete="current-password" required className="mt-2 h-12 w-full rounded-xl border border-slate-300 px-4 outline-none focus:border-blue-600" />
          </div>
          <button disabled={loading} className="mt-8 h-12 w-full rounded-xl bg-blue-600 font-bold text-white hover:bg-blue-700 disabled:opacity-60">{loading ? "Validando acceso..." : "Iniciar sesión"}</button>
        </form>
      </div>
    </div>
  );
}
