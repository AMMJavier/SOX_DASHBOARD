import {
  Bell,
  CalendarDays,
  FolderOpen,
  GitCompareArrows,
  History,
  Home,
} from "lucide-react";
import SidebarItem from "./SidebarItem";

// Secciones compartidas por los controles documentales. La vista se resuelve
// con ?vista=... dentro de su /dashboard; no requiere agregar rutas React.
const DOCUMENTAL_SECTIONS = [
  ["resumen", "Resumen", Home],
  ["campana", "Período / campaña", CalendarDays],
  ["evidencias", "Evidencias", FolderOpen],
  ["historial", "Historial", History],
  ["alertas", "Recordatorios", Bell],
];

const CONTROL6_SECTIONS = [
  ["resumen", "Resumen", Home],
  ["conciliacion", "Conciliación", GitCompareArrows],
  ["evidencias", "Evidencias", FolderOpen],
  ["historial", "Historial", History],
  ["alertas", "Recordatorios", Bell],
];

export default function ControlSectionsNav({ controlId, pathname, search }) {
  const isDocumental = ["1", "2", "3", "5"].includes(controlId);
  if (!isDocumental && controlId !== "6") return null;

  const sections = isDocumental ? DOCUMENTAL_SECTIONS : CONTROL6_SECTIONS;
  const base = `/SOX/Controls/Control_${controlId}/dashboard`;
  const current = new URLSearchParams(search).get("vista") || "resumen";
  const view = sections.some(([key]) => key === current) ? current : "resumen";
  const onDashboard = pathname.toLowerCase() === base.toLowerCase();

  const resolveLabel = (key, defaultLabel) => {
    if (controlId === "5" && key === "campana") return "Seguimiento por evento";
    if (controlId === "5" && key === "evidencias") return "Eventos y evidencias";
    if (controlId === "3" && key === "campana") return "Semestre / período";
    return defaultLabel;
  };

  return (
    <>
      <p className="px-2 pb-1 pt-6 text-xs font-bold uppercase tracking-wider text-slate-400">
        Control {controlId} · Secciones
      </p>
      {sections.map(([key, label, Icon]) => (
        <SidebarItem
          key={`${controlId}-${key}`}
          to={`${base}?vista=${key}`}
          icon={Icon}
          label={resolveLabel(key, label)}
          active={onDashboard && view === key}
        />
      ))}
    </>
  );
}
