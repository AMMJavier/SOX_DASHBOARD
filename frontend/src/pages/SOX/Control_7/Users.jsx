import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { createUser, getUserPermissions, listUsers, resetUserPassword, setUserActive, userApiError } from "../../../services/usersService";

const blank = { username: "", auth_provider: "ldap", rol: "", password: "" };

export default function Users() {
  const [permisos, setPermisos] = useState(null);
  const [usuarios, setUsuarios] = useState([]);
  const [form, setForm] = useState(blank);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [resetId, setResetId] = useState(null);
  const [newPassword, setNewPassword] = useState("");

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

  const handleCreate = async (event) => {
    event.preventDefault();
    setError(""); setNotice(""); setSaving(true);
    try {
      const payload = { username: form.username.trim(), auth_provider: form.auth_provider, rol: form.rol };
      if (payload.auth_provider === "local") payload.password = form.password;
      await createUser(payload);
      setNotice("Usuario creado correctamente.");
      setForm((current) => ({ ...current, username: "", password: "" }));
      await refresh();
    } catch (err) { setError(userApiError(err)); }
    finally { setSaving(false); }
  };

  const handleActive = async (usuario) => {
    if (!window.confirm(`${usuario.activo ? "Desactivar" : "Activar"} usuario ${usuario.username}?`)) return;
    setError(""); setNotice("");
    try {
      await setUserActive(usuario.id, !usuario.activo);
      setNotice("Estado actualizado.");
      await refresh();
    } catch (err) { setError(userApiError(err)); }
  };

  const handleReset = async (event) => {
    event.preventDefault();
    setError(""); setNotice(""); setSaving(true);
    try {
      await resetUserPassword(resetId, newPassword);
      setNewPassword(""); setResetId(null);
      setNotice("Contraseña local restablecida.");
    } catch (err) { setError(userApiError(err)); }
    finally { setSaving(false); }
  };

  return <main className="mx-auto max-w-6xl space-y-6 p-6">
    <header>
      <h1 className="text-2xl font-bold text-slate-900">Administración de usuarios</h1>
      <p className="mt-1 text-sm text-slate-600">Cuentas locales y LDAP administradas en Oracle. El administrador SOX gestiona todos los módulos; el administrador Assets gestiona únicamente Assets.</p>
      {permisos && <p className="mt-2 text-sm font-semibold text-blue-700">Módulo: {permisos.modulo.toUpperCase()} · Rol: {permisos.rol_actual}</p>}
      <Link to={permisos?.modulo === "assets" ? "/assets/dashboard" : "/SOX/Controls/Control_7/dashboard"} className="text-sm text-blue-700 underline">Volver al dashboard</Link>
    </header>
    {error && <div role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-800">{error}</div>}
    {notice && <div role="status" className="rounded-lg bg-green-50 p-3 text-sm text-green-800">{notice}</div>}
    {loading ? <p>Cargando usuarios...</p> : permisos && <>
      <form onSubmit={handleCreate} className="grid gap-4 rounded-2xl border bg-white p-5 shadow-sm md:grid-cols-2">
        <h2 className="text-lg font-bold md:col-span-2">Crear usuario</h2>
        <label className="text-sm font-semibold">Usuario
          <input required minLength={3} maxLength={100} autoComplete="off" value={form.username} onChange={(e) => setForm((f) => ({ ...f, username: e.target.value }))} className="mt-1 block w-full rounded-lg border p-2" placeholder="usuario.corporativo" />
        </label>
        <label className="text-sm font-semibold">Autenticación
          <select value={form.auth_provider} onChange={(e) => setForm((f) => ({ ...f, auth_provider: e.target.value, password: "" }))} className="mt-1 block w-full rounded-lg border p-2"><option value="ldap">LDAP</option><option value="local">Local</option></select>
        </label>
        <label className="text-sm font-semibold">Rol
          <select required value={form.rol} onChange={(e) => setForm((f) => ({ ...f, rol: e.target.value }))} className="mt-1 block w-full rounded-lg border p-2">{permisos.roles_creables.map((role) => <option key={role} value={role}>{role}</option>)}</select>
        </label>
        {form.auth_provider === "local" && <label className="text-sm font-semibold">Contraseña inicial (8–72 bytes)
          <input required type="password" minLength={8} autoComplete="new-password" value={form.password} onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))} className="mt-1 block w-full rounded-lg border p-2" />
        </label>}
        <div className="md:col-span-2"><button disabled={saving} className="rounded-lg bg-blue-600 px-5 py-2 font-semibold text-white disabled:opacity-50">{saving ? "Guardando..." : "Crear usuario"}</button></div>
      </form>
      <section className="overflow-x-auto rounded-2xl border bg-white p-5 shadow-sm">
        <h2 className="mb-4 text-lg font-bold">{permisos.modulo === "global" ? "Usuarios de todos los módulos" : "Usuarios de Assets"} ({usuarios.length})</h2>
        <table className="min-w-full text-left text-sm"><thead><tr className="border-b text-slate-600"><th className="p-2">Usuario</th><th className="p-2">Proveedor</th><th className="p-2">Rol</th><th className="p-2">Estado</th><th className="p-2">Acciones</th></tr></thead>
        <tbody>{usuarios.map((usuario) => <tr key={usuario.id} className="border-b"><td className="p-2">{usuario.username}</td><td className="p-2">{usuario.auth_provider}</td><td className="p-2">{usuario.rol}</td><td className="p-2">{usuario.activo ? "Activo" : "Inactivo"}</td><td className="space-x-3 p-2"><button type="button" className="text-blue-700 underline" onClick={() => handleActive(usuario)}>{usuario.activo ? "Desactivar" : "Activar"}</button>{usuario.auth_provider === "local" && <button type="button" onClick={() => { setResetId(usuario.id); setNewPassword(""); }} className="text-blue-700 underline">Restablecer contraseña</button>}</td></tr>)}</tbody>
        </table>
        {!usuarios.length && <p className="mt-4 text-sm text-slate-600">No hay usuarios de este módulo.</p>}
      </section>
      {resetId !== null && <form onSubmit={handleReset} className="rounded-xl border bg-white p-5"><h2 className="font-bold">Restablecer contraseña de usuario local</h2><label className="mt-3 block text-sm">Nueva contraseña<input required type="password" autoComplete="new-password" minLength={8} value={newPassword} onChange={(e) => setNewPassword(e.target.value)} className="mt-1 block w-full max-w-sm rounded-lg border p-2" /></label><div className="mt-3 flex gap-3"><button disabled={saving} className="rounded-lg bg-blue-600 px-4 py-2 text-white">Guardar</button><button type="button" onClick={() => { setResetId(null); setNewPassword(""); }} className="rounded-lg border px-4 py-2">Cancelar</button></div></form>}
    </>}
  </main>;
}
