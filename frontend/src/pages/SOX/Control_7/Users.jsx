import { useCallback, useEffect, useMemo, useState } from "react";
import {
  KeyRound, Power, Search, ShieldCheck, Trash2, UserCheck, UserPlus, Users as UsersIcon, UserX, X,
} from "lucide-react";
import {
  createUser, deleteUser, getUserPermissions, listUsers, resetUserPassword, setUserActive, userApiError,
} from "../../../services/usersService";
import PasswordGenerator from "../../../components/common/PasswordGenerator";

/*
 * Administración de usuarios compartida por SOX (/SOX/Controls/Control_7/users)
 * y Assets (/assets/users). Se muestra dentro del layout de cada módulo.
 * - Administrador SOX (módulo "global"): gestiona todos los roles y puede eliminar.
 * - Administrador Assets: solo roles de Assets; no elimina, solo activa/desactiva.
 */

const blank = { username: "", auth_provider: "ldap", rol: "", password: "" };

const ROLE_STYLES = {
  administrador: "bg-blue-50 text-blue-700 ring-blue-200",
  desarrollador: "bg-slate-100 text-slate-700 ring-slate-200",
  gerencial: "bg-amber-50 text-amber-700 ring-amber-200",
  assets_admin: "bg-violet-50 text-violet-700 ring-violet-200",
  assets_viewer: "bg-fuchsia-50 text-fuchsia-700 ring-fuchsia-200",
};

function Badge({ className, children }) {
  return <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ring-inset ${className}`}>{children}</span>;
}

function StatCard({ icon: Icon, label, value, tone }) {
  return (
    <div className="flex items-center gap-4 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl ${tone}`}><Icon size={22} /></div>
      <div>
        <p className="text-2xl font-bold text-slate-900">{value}</p>
        <p className="text-sm text-slate-500">{label}</p>
      </div>
    </div>
  );
}

function Modal({ title, onClose, children }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/50 p-4" role="dialog" aria-modal="true" aria-label={title}>
      <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl">
        <div className="mb-4 flex items-start justify-between gap-4">
          <h3 className="text-lg font-bold text-slate-900">{title}</h3>
          <button type="button" onClick={onClose} className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700" aria-label="Cerrar"><X size={20} /></button>
        </div>
        {children}
      </div>
    </div>
  );
}

export default function Users() {
  const [permisos, setPermisos] = useState(null);
  const [usuarios, setUsuarios] = useState([]);
  const [form, setForm] = useState(blank);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [query, setQuery] = useState("");
  const [resetUser, setResetUser] = useState(null);
  const [newPassword, setNewPassword] = useState("");
  const [deleteTarget, setDeleteTarget] = useState(null);

  const isGlobal = permisos?.modulo === "global";
  const canDelete = isGlobal;
  const accent = isGlobal
    ? { btn: "bg-blue-600 hover:bg-blue-700", ring: "focus:border-blue-500 focus:ring-blue-100", text: "text-blue-700" }
    : { btn: "bg-violet-600 hover:bg-violet-700", ring: "focus:border-violet-500 focus:ring-violet-100", text: "text-violet-700" };
  const input = `mt-1.5 block h-11 w-full rounded-xl border border-slate-300 bg-white px-3 text-sm outline-none focus:ring-4 ${accent.ring}`;

  const refresh = useCallback(async () => {
    const [roles, users] = await Promise.all([getUserPermissions(), listUsers()]);
    setPermisos(roles);
    setUsuarios(users);
    setForm((current) => ({ ...current, rol: roles.roles_creables.includes(current.rol) ? current.rol : roles.roles_creables[0] || "" }));
  }, []);

  useEffect(() => {
    let mounted = true;
    refresh().catch((err) => { if (mounted) setError(userApiError(err)); })
      .finally(() => { if (mounted) setLoading(false); });
    return () => { mounted = false; };
  }, [refresh]);

  const stats = useMemo(() => ({
    total: usuarios.length,
    activos: usuarios.filter((u) => u.activo).length,
    inactivos: usuarios.filter((u) => !u.activo).length,
    ldap: usuarios.filter((u) => u.auth_provider === "ldap").length,
  }), [usuarios]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return usuarios;
    return usuarios.filter((u) => [u.username, u.rol, u.auth_provider].some((v) => String(v || "").toLowerCase().includes(q)));
  }, [usuarios, query]);

  const run = async (action, okMessage) => {
    setError(""); setNotice("");
    try {
      await action();
      setNotice(okMessage);
      await refresh();
      return true;
    } catch (err) {
      setError(userApiError(err));
      return false;
    }
  };

  const handleCreate = async (event) => {
    event.preventDefault();
    setSaving(true);
    const payload = { username: form.username.trim(), auth_provider: form.auth_provider, rol: form.rol };
    if (payload.auth_provider === "local") payload.password = form.password;
    const ok = await run(() => createUser(payload), `Usuario ${payload.username} creado correctamente.`);
    if (ok) setForm((current) => ({ ...current, username: "", password: "" }));
    setSaving(false);
  };

  const handleActive = (usuario) => run(
    () => setUserActive(usuario.id, !usuario.activo),
    `Usuario ${usuario.username} ${usuario.activo ? "desactivado" : "activado"}.`,
  );

  const handleReset = async (event) => {
    event.preventDefault();
    setSaving(true);
    setError(""); setNotice("");
    try {
      await resetUserPassword(resetUser.id, newPassword);
      setNotice(`Contraseña de ${resetUser.username} restablecida.`);
      setResetUser(null); setNewPassword("");
    } catch (err) { setError(userApiError(err)); }
    finally { setSaving(false); }
  };

  const handleDelete = async () => {
    setSaving(true);
    const target = deleteTarget;
    await run(() => deleteUser(target.id), `Usuario ${target.username} eliminado.`);
    setDeleteTarget(null);
    setSaving(false);
  };

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Administración de usuarios</h1>
          <p className="mt-1 max-w-2xl text-sm text-slate-500">
            {isGlobal
              ? "Gestiona las cuentas locales y LDAP de todos los módulos."
              : "Gestiona las cuentas locales y LDAP del módulo Assets."}
          </p>
        </div>
        {permisos && (
          <div className={`inline-flex items-center gap-2 self-start rounded-full bg-white px-3 py-1.5 text-sm font-semibold shadow-sm ring-1 ring-slate-200 ${accent.text}`}>
            <ShieldCheck size={16} /> {permisos.modulo === "global" ? "SOX · todos los módulos" : "Assets"} · {permisos.rol_actual}
          </div>
        )}
      </header>

      {error && <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-800">{error}</div>}
      {notice && <div role="status" className="rounded-xl border border-green-200 bg-green-50 p-3 text-sm text-green-800">{notice}</div>}

      {loading ? <p className="text-slate-500">Cargando usuarios...</p> : permisos && <>
        <section className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <StatCard icon={UsersIcon} label="Usuarios" value={stats.total} tone="bg-slate-100 text-slate-700" />
          <StatCard icon={UserCheck} label="Activos" value={stats.activos} tone="bg-green-50 text-green-700" />
          <StatCard icon={UserX} label="Inactivos" value={stats.inactivos} tone="bg-red-50 text-red-700" />
          <StatCard icon={ShieldCheck} label="Cuentas LDAP" value={stats.ldap} tone="bg-blue-50 text-blue-700" />
        </section>

        <form onSubmit={handleCreate} className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="mb-5 flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-100 text-slate-700"><UserPlus size={20} /></div>
            <div>
              <h2 className="text-lg font-bold text-slate-900">Crear usuario</h2>
              <p className="text-sm text-slate-500">Las cuentas LDAP usan la contraseña corporativa; las locales requieren una contraseña inicial.</p>
            </div>
          </div>
          <div className="grid gap-4 md:grid-cols-3">
            <label className="text-sm font-semibold text-slate-700">Usuario
              <input required minLength={3} maxLength={100} autoComplete="off" value={form.username}
                onChange={(e) => setForm((f) => ({ ...f, username: e.target.value }))} className={input} placeholder="usuario.corporativo" />
            </label>
            <label className="text-sm font-semibold text-slate-700">Autenticación
              <select value={form.auth_provider} onChange={(e) => setForm((f) => ({ ...f, auth_provider: e.target.value, password: "" }))} className={input}>
                <option value="ldap">LDAP (corporativa)</option>
                <option value="local">Local</option>
              </select>
            </label>
            <label className="text-sm font-semibold text-slate-700">Rol
              <select required value={form.rol} onChange={(e) => setForm((f) => ({ ...f, rol: e.target.value }))} className={input}>
                {permisos.roles_creables.map((role) => <option key={role} value={role}>{role}</option>)}
              </select>
            </label>
            {form.auth_provider === "local" && (
              <label className="text-sm font-semibold text-slate-700">Contraseña inicial (8–72 caracteres)
                <input required type="password" minLength={8} autoComplete="new-password" value={form.password}
                  onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))} className={input} />
              </label>
            )}
            {form.auth_provider === "local" && (
              <div className="md:col-span-2">
                <PasswordGenerator onUse={(clave) => setForm((f) => ({ ...f, password: clave }))} />
              </div>
            )}
          </div>
          <div className="mt-5">
            <button disabled={saving} className={`inline-flex h-11 items-center gap-2 rounded-xl px-5 font-semibold text-white disabled:opacity-50 ${accent.btn}`}>
              <UserPlus size={18} /> {saving ? "Guardando..." : "Crear usuario"}
            </button>
          </div>
        </form>

        <section className="rounded-2xl border border-slate-200 bg-white shadow-sm">
          <div className="flex flex-col gap-3 border-b border-slate-200 p-5 sm:flex-row sm:items-center sm:justify-between">
            <h2 className="text-lg font-bold text-slate-900">
              {isGlobal ? "Usuarios de todos los módulos" : "Usuarios de Assets"} <span className="text-slate-400">({filtered.length})</span>
            </h2>
            <div className="relative sm:w-72">
              <Search size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
              <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Buscar usuario, rol o proveedor"
                className={`h-10 w-full rounded-xl border border-slate-300 pl-9 pr-3 text-sm outline-none focus:ring-4 ${accent.ring}`} />
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
                <tr><th className="px-5 py-3">Usuario</th><th className="px-5 py-3">Proveedor</th><th className="px-5 py-3">Rol</th><th className="px-5 py-3">Estado</th><th className="px-5 py-3 text-right">Acciones</th></tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filtered.map((usuario) => (
                  <tr key={usuario.id} className="hover:bg-slate-50/70">
                    <td className="px-5 py-3">
                      <div className="flex items-center gap-3">
                        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-slate-100 text-sm font-bold uppercase text-slate-600">{usuario.username.slice(0, 2)}</div>
                        <span className="font-semibold text-slate-900">{usuario.username}</span>
                      </div>
                    </td>
                    <td className="px-5 py-3">
                      <Badge className={usuario.auth_provider === "ldap" ? "bg-sky-50 text-sky-700 ring-sky-200" : "bg-slate-100 text-slate-600 ring-slate-200"}>
                        {usuario.auth_provider === "ldap" ? "LDAP" : "Local"}
                      </Badge>
                    </td>
                    <td className="px-5 py-3"><Badge className={ROLE_STYLES[usuario.rol] || "bg-slate-100 text-slate-700 ring-slate-200"}>{usuario.rol}</Badge></td>
                    <td className="px-5 py-3">
                      <span className={`inline-flex items-center gap-1.5 text-sm font-semibold ${usuario.activo ? "text-green-700" : "text-slate-400"}`}>
                        <span className={`h-2 w-2 rounded-full ${usuario.activo ? "bg-green-500" : "bg-slate-300"}`} />
                        {usuario.activo ? "Activo" : "Inactivo"}
                      </span>
                    </td>
                    <td className="px-5 py-3">
                      <div className="flex flex-wrap justify-end gap-2">
                        <button type="button" onClick={() => handleActive(usuario)}
                          className={`inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs font-semibold ${usuario.activo ? "border-amber-200 text-amber-700 hover:bg-amber-50" : "border-green-200 text-green-700 hover:bg-green-50"}`}>
                          <Power size={14} /> {usuario.activo ? "Desactivar" : "Activar"}
                        </button>
                        {usuario.auth_provider === "local" && (
                          <button type="button" onClick={() => { setResetUser(usuario); setNewPassword(""); }}
                            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-2.5 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50">
                            <KeyRound size={14} /> Contraseña
                          </button>
                        )}
                        {canDelete && (
                          <button type="button" onClick={() => setDeleteTarget(usuario)}
                            className="inline-flex items-center gap-1.5 rounded-lg border border-red-200 px-2.5 py-1.5 text-xs font-semibold text-red-700 hover:bg-red-50">
                            <Trash2 size={14} /> Eliminar
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {!filtered.length && <p className="p-6 text-center text-sm text-slate-500">{query ? "Ningún usuario coincide con la búsqueda." : "No hay usuarios en este módulo."}</p>}
        </section>
      </>}

      {resetUser && (
        <Modal title={`Restablecer contraseña de ${resetUser.username}`} onClose={() => { setResetUser(null); setNewPassword(""); }}>
          <form onSubmit={handleReset}>
            <PasswordGenerator onUse={setNewPassword} />
            <label className="mt-4 block text-sm font-semibold text-slate-700">Nueva contraseña (8–72 caracteres)
              <input required type="password" autoComplete="new-password" minLength={8} value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)} className={input} />
            </label>
            <div className="mt-6 flex justify-end gap-3">
              <button type="button" onClick={() => { setResetUser(null); setNewPassword(""); }} className="h-10 rounded-xl border border-slate-300 px-4 text-sm font-semibold text-slate-700 hover:bg-slate-50">Cancelar</button>
              <button disabled={saving} className={`h-10 rounded-xl px-4 text-sm font-semibold text-white disabled:opacity-50 ${accent.btn}`}>{saving ? "Guardando..." : "Guardar"}</button>
            </div>
          </form>
        </Modal>
      )}

      {deleteTarget && (
        <Modal title="Eliminar usuario" onClose={() => setDeleteTarget(null)}>
          <div className="flex gap-4">
            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-red-50 text-red-600"><Trash2 size={22} /></div>
            <p className="text-sm text-slate-600">
              Se eliminará definitivamente la cuenta <strong className="text-slate-900">{deleteTarget.username}</strong> ({deleteTarget.rol}) y se cerrarán sus sesiones.
              Esta acción no se puede deshacer. Si solo quieres quitarle el acceso, usa <strong>Desactivar</strong>.
            </p>
          </div>
          <div className="mt-6 flex justify-end gap-3">
            <button type="button" onClick={() => setDeleteTarget(null)} className="h-10 rounded-xl border border-slate-300 px-4 text-sm font-semibold text-slate-700 hover:bg-slate-50">Cancelar</button>
            <button type="button" disabled={saving} onClick={handleDelete} className="h-10 rounded-xl bg-red-600 px-4 text-sm font-semibold text-white hover:bg-red-700 disabled:opacity-50">{saving ? "Eliminando..." : "Eliminar"}</button>
          </div>
        </Modal>
      )}
    </div>
  );
}
