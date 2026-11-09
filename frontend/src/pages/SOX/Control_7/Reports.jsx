import { useEffect, useState } from "react";
import { Download } from "lucide-react";

export default function Reports() {
  const [exportsHistory, setExportsHistory] = useState([]);

  useEffect(() => {
    const saved = JSON.parse(localStorage.getItem("exportsHistory")) || [];
    setExportsHistory(saved);
  }, []);

  return (
    <div>
      <h1 className="text-2xl font-bold">Exportaciones</h1>
      <p className="mt-1 text-slate-500">
        Historial de archivos descargados por el administrador.
      </p>

      <div className="mt-6 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <h3 className="mb-5 text-lg font-bold">Historial de exportaciones</h3>

        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="bg-slate-50 text-left">
              <th className="border-b p-4">Tipo</th>
              <th className="border-b p-4">Módulo</th>
              <th className="border-b p-4">Descripción</th>
              <th className="border-b p-4">Registros</th>
              <th className="border-b p-4">Usuario</th>
              <th className="border-b p-4">Fecha</th>
            </tr>
          </thead>

          <tbody>
            {exportsHistory.map((item) => (
              <tr key={item.id}>
                <td className="border-b p-4">
                  <span className="flex items-center gap-2 font-bold">
                    <Download size={16} />
                    {item.type}
                  </span>
                </td>

                <td className="border-b p-4">{item.module}</td>
                <td className="border-b p-4">{item.description}</td>
                <td className="border-b p-4">{item.records || 0}</td>
                <td className="border-b p-4">{item.user}</td>
                <td className="border-b p-4">{item.date}</td>

              
              </tr>
            ))}
          </tbody>
        </table>

        {exportsHistory.length === 0 && (
          <div className="p-8 text-center text-slate-500">
            Todavía no existen exportaciones registradas.
          </div>
        )}
      </div>
    </div>
  );
}