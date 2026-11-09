import { Route } from "react-router-dom";

import PrivateRoute from "./PrivateRoute";
import NetworkLayout from "../layouts/NetworkLayout";
import NetworkDashboard from "../pages/Network/NetworkDashboard";

export const networkRoutes = (
  <Route
    path="/network"
    element={
      <PrivateRoute
        allowedRoles={["administrador", "desarrollador"]}
      >
        <NetworkLayout />
      </PrivateRoute>
    }
  >
    <Route
      index
      element={<NetworkDashboard />}
    />
  </Route>
);