
import { Navigate, Route } from "react-router-dom";

import PrivateRoute from "./PrivateRoute";
import AssetsLayout from "../layouts/AssetsLayout";

import AssetsDashboard from "../pages/Assets/AssetsDashboard";
import Upload from "../pages/Assets/Upload";
import Inventory from "../pages/Assets/Inventory";
import Locations from "../pages/Assets/Locations";
import Logs from "../pages/Assets/Logs";
import Users from "../pages/SOX/Control_7/Users";

const ASSETS_ACCESS = ["administrador", "assets_admin", "assets_viewer"];

const ASSETS_WRITE = ["administrador", "assets_admin"];

export const assetsRoutes = (
  <Route
    path="/assets"
    element={
      <PrivateRoute allowedRoles={ASSETS_ACCESS}>
        <AssetsLayout />
      </PrivateRoute>
    }
  >
    <Route
      index
      element={<Navigate to="dashboard" replace />}
    />

    <Route
      path="dashboard"
      element={<AssetsDashboard />}
    />

    <Route
      path="inventory"
      element={<Inventory />}
    />

    <Route
      path="locations"
      element={<Locations />}
    />

    <Route
      path="logs"
      element={<Logs />}
    />

    <Route path="users" element={<PrivateRoute allowedRoles={["assets_admin"]}><Users /></PrivateRoute>} />

    <Route
      path="upload"
      element={
        <PrivateRoute allowedRoles={ASSETS_WRITE}>
          <Upload />
        </PrivateRoute>
      }
    />
  </Route>
);
