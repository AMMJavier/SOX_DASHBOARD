import { Globe, Network } from "lucide-react";
import { useNavigate } from "react-router-dom";

export const INTERNAL_PATH = "/SOX/Controls/Control_7/internas";

/** Selector del Control 7 en el sidebar: VPN externas (Check Point) o VPN internas (LDAP RDP / Aplicaciones). */
export default function VpnScopeSwitch({ internal }) {
  const navigate = useNavigate();
  const option = (active, label, Icon, to) => (
    <button type="button" onClick={() => navigate(to)} aria-pressed={active}
      className={`flex flex-1 items-center justify-center gap-1.5 rounded-lg px-2 py-2 text-xs font-semibold transition ${active ? "bg-blue-600 text-white" : "text-slate-300 hover:bg-white/10"}`}>
      <Icon size={14}/>{label}
    </button>
  );
  return (
    <div className="mb-3 mt-2">
      <p className="px-2 pb-1.5 text-xs font-bold uppercase tracking-wider text-slate-400">Tipo de VPN</p>
      <div className="flex gap-1 rounded-xl bg-white/5 p-1" role="group" aria-label="Tipo de VPN">
        {option(!internal, "Externas", Globe, "/SOX/Controls/Control_7/dashboard")}
        {option(internal, "Internas", Network, INTERNAL_PATH)}
      </div>
    </div>
  );
}
