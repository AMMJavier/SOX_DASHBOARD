import { Route } from "react-router-dom";

import PrivateRoute from "./PrivateRoute";
import MaintenanceLayout from "../layouts/MaintenanceLayout";
import MaintenanceDashboard from "../pages/Maintenance/MaintenanceDashboard";

export const maintenanceRoutes = (
  <Route
    path="/maintenance"
    element={
      <PrivateRoute
        allowedRoles={["administrador", "desarrollador"]}
      >
        <MaintenanceLayout />
      </PrivateRoute>
    }
  >
    <Route
      index
      element={<MaintenanceDashboard />}
    />
  </Route>
);