import UnparametrizedVpns from "../../../components/SOX/control_7/UnparametrizedVpns";

/** Página del Control 7: VPN de Check Point cuyo comentario no cumple REQ - SOLICITANTE - GERENTE. */
export default function UnparametrizedVpnsPage() {
  return (
    <div className="space-y-2">
      <h1 className="text-2xl font-bold text-slate-900">VPN sin parametrizar</h1>
      <p className="text-sm text-slate-500">
        VPN extraídas de Check Point cuyo comentario no cumple el formato <strong>REQ - SOLICITANTE - GERENTE</strong>.
        No entran a la validación de gerentes hasta que se corrijan en Check Point.
      </p>
      <UnparametrizedVpns />
    </div>
  );
}
