import { Navigate } from "react-router-dom";
import { readStoredUser } from "../../../services/authSession";
import InternalDashboard from "./internas/InternalDashboard";

/** Administración: dashboard de VPN internas. El gerente las valida junto a las externas en su dashboard. */
export default function InternalVpns() {
  const role = String(readStoredUser()?.rol || "").toLowerCase();
  return ["administrador", "desarrollador"].includes(role)
    ? <InternalDashboard/> : <Navigate to="/SOX/Controls/Control_7/dashboard" replace/>;
}
