import { useCallback, useEffect, useState } from "react";
import { Check, Copy, CornerDownLeft, RefreshCw, Sparkles } from "lucide-react";
import {
  LONGITUD_MAXIMA, LONGITUD_MINIMA, copiarTexto, fortaleza, generarClave,
} from "../../utils/passwordGenerator";

const COLORES = { 1: "bg-red-500", 2: "bg-amber-500", 3: "bg-lime-500", 4: "bg-green-600" };

/**
 * Recuadro para generar una clave segura y pasarla al campo de contraseña.
 * Solo se usa para usuarios locales. No guarda historial de claves.
 *
 * Props:
 *  - onUse(clave): escribe la clave en el campo de contraseña del formulario.
 */
export default function PasswordGenerator({ onUse }) {
  const [longitud, setLongitud] = useState(LONGITUD_MAXIMA);
  const [clave, setClave] = useState("");
  const [estado, setEstado] = useState(""); // "copiada" | "usada" | mensaje de error

  const generar = useCallback(() => {
    setClave(generarClave(longitud));
    setEstado("");
  }, [longitud]);

  useEffect(() => { generar(); }, [generar]);

  const copiar = async () => {
    try {
      await copiarTexto(clave);
      setEstado("copiada");
    } catch (err) {
      setEstado(err.message);
    }
  };

  const usar = () => {
    onUse(clave);
    setEstado("usada");
  };

  const f = fortaleza(longitud);
  const boton = "inline-flex h-9 items-center gap-1.5 rounded-lg border px-3 text-xs font-semibold";

  return (
    <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-4">
      <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-700">
        <Sparkles size={16} className="text-blue-600" /> Generador de clave segura
      </div>

      <div className="flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2">
        <code className="flex-1 select-all break-all font-mono text-base tracking-wider text-slate-900" aria-live="polite">{clave}</code>
        <button type="button" onClick={generar} title="Generar otra" aria-label="Generar otra clave"
          className="rounded-md p-1.5 text-slate-500 hover:bg-slate-100 hover:text-slate-800"><RefreshCw size={16} /></button>
      </div>

      <div className="mt-2 flex items-center gap-2">
        <div className="flex gap-1">
          {[1, 2, 3, 4].map((n) => (
            <span key={n} className={`h-1.5 w-8 rounded-full ${n <= f.nivel ? COLORES[f.nivel] : "bg-slate-200"}`} />
          ))}
        </div>
        <span className="text-xs text-slate-500">{f.texto} · {f.bits} bits</span>
      </div>

      <label className="mt-3 flex items-center gap-3 text-xs font-semibold text-slate-600">
        Longitud: <strong className="w-5 text-slate-900">{longitud}</strong>
        <input type="range" min={LONGITUD_MINIMA} max={LONGITUD_MAXIMA} value={longitud}
          onChange={(e) => setLongitud(Number(e.target.value))} className="flex-1 accent-blue-600" />
      </label>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <button type="button" onClick={usar} className={`${boton} border-blue-600 bg-blue-600 text-white hover:bg-blue-700`}>
          <CornerDownLeft size={14} /> Usar esta clave
        </button>
        <button type="button" onClick={copiar} className={`${boton} border-slate-300 bg-white text-slate-700 hover:bg-slate-100`}>
          {estado === "copiada" ? <Check size={14} className="text-green-600" /> : <Copy size={14} />} Copiar
        </button>
        {estado === "usada" && <span className="text-xs font-semibold text-green-700">Clave escrita en el campo de contraseña.</span>}
        {estado === "copiada" && <span className="text-xs font-semibold text-green-700">Copiada.</span>}
        {estado && !["usada", "copiada"].includes(estado) && <span className="text-xs font-semibold text-red-700">{estado}</span>}
      </div>

      <p className="mt-3 text-xs text-slate-500">Entrega esta clave al usuario: después de guardar no se puede volver a consultar.</p>
    </div>
  );
}
