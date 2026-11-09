import { useLocation, useNavigate } from "react-router-dom";
import controlConfig from "../../../constants/controlConfig";

/** Selector maestro de controles. Las opciones proceden de una sola fuente. */
export default function ControlSelector() {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const active = pathname.match(/\/SOX\/Controls\/Control_(\d+)(?:\/|$)/i)?.[1] || "";
  return (
    <select
      aria-label="Seleccionar control SOX"
      value={active}
      onChange={(event) => {
        const control = controlConfig[event.target.value];
        if (control) navigate(control.path);
      }}
      className="max-w-[420px] rounded-lg border border-slate-300 bg-white px-4 py-3 text-sm"
    >
      {!active && <option value="">Seleccionar control</option>}
      {Object.values(controlConfig).map((control) => (
        <option key={control.id} value={control.id}>{control.name}</option>
      ))}
    </select>
  );
}
