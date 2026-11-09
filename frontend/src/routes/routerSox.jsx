import { Route } from "react-router-dom";

import PrivateRoute from "./PrivateRoute";
import SoxLayout from "../layouts/SoxLayout";

// Controles SOX
import Control_1 from "../pages/SOX/Control_1/Control_1";
import Control_2 from "../pages/SOX/Control_2/Control_2";
import Control_3 from "../pages/SOX/Control_3/Control_3";
import Control_4 from "../pages/SOX/Control_4/Control_4";
import Control_5 from "../pages/SOX/Control_5/Control_5";
import Control_6 from "../pages/SOX/Control_6/Control_6";
import Control_10 from "../pages/SOX/Control_10/Control_10";

// Control 7
import DashboardRouter from "../pages/SOX/Control_7/DashboardRouter";
import Campaigns from "../pages/SOX/Control_7/Campaigns";
import History from "../pages/SOX/Control_7/History";
import Reports from "../pages/SOX/Control_7/Reports";
import Exceptions from "../pages/SOX/Control_7/Exceptions";
import AuditLogs from "../pages/SOX/Control_7/AuditLogs";

// Configuración SOX
import Settings from "../pages/SOX/Control_7/Settings";
import Users from "../pages/SOX/Control_7/Users";

const STANDARD_ROLES = [
  "administrador",
  "desarrollador",
];

const CONTROL_7_ROLES = [
  "gerencial",
  "desarrollador",
  "administrador",
];

function ProtectedSoxLayout({ roles = STANDARD_ROLES }) {
  return (
    <PrivateRoute allowedRoles={roles}>
      <SoxLayout />
    </PrivateRoute>
  );
}

export const soxRoutes = (
  <>
    <Route path="/admin/users" element={<PrivateRoute allowedRoles={["administrador"]}><Users /></PrivateRoute>} />
    <Route path="/admin/settings" element={<PrivateRoute allowedRoles={["administrador"]}><Settings /></PrivateRoute>} />

    {/* CONTROL 1 */}
    <Route
      path="/SOX/Controls/Control_1"
      element={<ProtectedSoxLayout />}
    >
      <Route
        path="dashboard"
        element={
          <Control_1
            control={{
              name: "Control 1 - Cambios en la SIS016",
            }}
          />
        }
      />
    </Route>

    {/* CONTROL 2 */}
    <Route
      path="/SOX/Controls/Control_2"
      element={<ProtectedSoxLayout />}
    >
      <Route
        path="dashboard"
        element={
          <Control_2
            control={{
              name: "Control 2 - Plan de Seguridad Ok de Gerencia",
            }}
          />
        }
      />
    </Route>

    {/* CONTROL 3 */}
    <Route
      path="/SOX/Controls/Control_3"
      element={<ProtectedSoxLayout />}
    >
      <Route
        path="dashboard"
        element={
          <Control_3
            control={{
              name: "Control 3 - Revisioo del Plan Seguridades (Semestral)",
            }}
          />
        }
      />
    </Route>

    {/* CONTROL 4 */}
    <Route
      path="/SOX/Controls/Control_4"
      element={<ProtectedSoxLayout />}
    >
      <Route
        path="dashboard"
        element={
          <Control_4
            control={{
              name: "Control 4 - VPNs Corporativas",
            }}
          />
        }
      />
    </Route>

    {/* CONTROL 5 */}
    <Route
      path="/SOX/Controls/Control_5"
      element={<ProtectedSoxLayout />}
    >
      <Route
        path="dashboard"
        element={
          <Control_5
            control={{
              name: "Control 5 - Administradores del Firewall",
            }}
          />
        }
      />
    </Route>

    {/* CONTROL 6 */}
    <Route
      path="/SOX/Controls/Control_6"
      element={<ProtectedSoxLayout />}
    >
      <Route
        path="dashboard"
        element={
          <Control_6
            control={{
              name: "Control 6 - Personal Cesante vs_VPN_por eventos",
            }}
          />
        }
      />
    </Route>

    {/* CONTROL 7 */}
    <Route
      path="/SOX/Controls/Control_7"
      element={<ProtectedSoxLayout roles={CONTROL_7_ROLES} />}
    >
      <Route
        index
        element={<DashboardRouter />}
      />

      <Route
        path="dashboard"
        element={<DashboardRouter />}
      />

      <Route
        path="campaigns"
        element={<PrivateRoute allowedRoles={["administrador", "desarrollador"]}><Campaigns /></PrivateRoute>}
      />

      <Route
        path="history"
        element={<History />}
      />

      <Route
        path="reports"
        element={<Reports />}
      />

      <Route
        path="exceptions"
        element={<Exceptions />}
      />

      <Route
        path="logs"
        element={<AuditLogs />}
      />

      <Route
        path="settings"
        element={<PrivateRoute allowedRoles={["administrador"]}><Settings /></PrivateRoute>}
      />
    </Route>

    {/* CONTROL 10 */}
    <Route
      path="/SOX/Controls/Control_10"
      element={<ProtectedSoxLayout />}
    >
      <Route
        path="dashboard"
        element={
          <Control_10
            control={{
              name: "Control 10 - automatizado",
            }}
          />
        }
      />
    </Route>
  </>
);