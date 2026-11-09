import {
  BrowserRouter,
  Navigate,
  Route,
  Routes,
} from "react-router-dom";

import PrivateRoute from "./PrivateRoute";

// Páginas globales
import Login from "../pages/Login";
import ModuleSelector from "../pages/ModuleSelector";

// Routers independientes
import { soxRoutes } from "./routerSox";
import { assetsRoutes } from "./routerAssets";
import { networkRoutes } from "./routerNetwork";
import { maintenanceRoutes } from "./routerMaintenance";

export default function AppRouter() {
  return (
    <BrowserRouter>
      <Routes>
        {/* AUTENTICACIÓN */}
        <Route
          path="/login"
          element={<Login />}
        />

        {/* SELECCIÓN DE MÓDULOS */}
        <Route
          path="/modules"
          element={
            <PrivateRoute
              allowedRoles={[
                "administrador",
                "desarrollador",
              ]}
            >
              <ModuleSelector />
            </PrivateRoute>
          }
        />

        {/* MÓDULOS  */}
        {soxRoutes}
        {assetsRoutes}
        {networkRoutes}
        {maintenanceRoutes}

        {/* REDIRECCIONES GENERALES */}
        <Route
          path="/"
          element={<Navigate to="/login" replace />}
        />

        <Route
          path="*"
          element={<Navigate to="/login" replace />}
        />
      </Routes>
    </BrowserRouter>
  );
}