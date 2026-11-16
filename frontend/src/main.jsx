import React from "react";
import ReactDOM from "react-dom/client";
import AppRouter from "./routes/router";
import SessionTimeout from "./components/common/SessionTimeout";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <SessionTimeout />
    <AppRouter />
  </React.StrictMode>
);