import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { getCurrentUser } from "../services/authService";
import { getAccessToken, readStoredUser, updateSessionProfile } from "../services/authSession";

const SOX_ROLES = ["administrador", "gerencial", "desarrollador"];
const ASSETS_ROLES = ["assets_admin", "assets_viewer"];

function homeForRole(rol) {
  if (ASSETS_ROLES.includes(rol)) return "/assets/dashboard";
  if (rol === "gerencial") return "/SOX/Controls/Control_7/dashboard";
  if (SOX_ROLES.includes(rol)) return "/modules";
  return "/login";
}

export default function PrivateRoute({ children, allowedRoles }) {
  const token = getAccessToken();
  const [state, setState] = useState(() => ({ token: null, user: null, pending: true }));

  useEffect(() => {
    let active = true;
    if (!token) return undefined;
    getCurrentUser().then((profile) => {
      if (!active) return;
      const user = updateSessionProfile(profile);
      setState({ token, user, pending: false });
    }).catch(() => {
      if (active) setState({ token, user: null, pending: false });
    });
    return () => { active = false; };
  }, [token]);

  if (!token || !readStoredUser()) return <Navigate to="/login" replace />;
  if (state.pending || state.token !== token) {
    return <p className="p-8 text-slate-600">Verificando sesión...</p>;
  }
  if (!state.user) return <Navigate to="/login" replace />;
  if (allowedRoles && !allowedRoles.includes(state.user.rol)) {
    return <Navigate to={homeForRole(state.user.rol)} replace />;
  }
  return children;
}
