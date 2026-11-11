import { useRef, useState } from "react";
import {
  UploadCloud,
  FileSpreadsheet,
  TableProperties,
  Plus,
  Trash2,
  CheckCircle2,
  AlertCircle,
  Database,
  Loader2,
  FileCheck2,
  X,
} from "lucide-react";

import {
  previewAssetsCsv,
  confirmAssetsUpload,
  saveAssetsManual,
} from "../../services/assets/uploadApi";

const REQUIRED = []; // Temporalmente no hay campos obligatorios

const COLUMNS = [
  "especialidad",
  "plataforma",
  "tipo",
  "dispositivo",
  "estado",
  "criticidad",
  "infraestructura",
  "ip",
  "mask",
  "gateway",
  "mac",
  "localidad",
  "piso",
  "lado",
  "ciudad",
  "so",
  "version",
  "firmware",
  "fabricante",
  "modelo",
  "serial",
  "licencia",
  "eos",
  "comentario",
];

const LABELS = {
  especialidad: "Especialidad",
  plataforma: "Plataforma",
  tipo: "Tipo",
  dispositivo: "Dispositivo",
  estado: "Estado",
  criticidad: "Criticidad",
  infraestructura: "Infraestructura",
  ip: "IP",
  mask: "Máscara",
  gateway: "Gateway",
  mac: "MAC",
  localidad: "Localidad",
  piso: "Piso",
  lado: "Lado",
  ciudad: "Ciudad",
  so: "Sistema operativo",
  version: "Versión",
  firmware: "Firmware",
  fabricante: "Fabricante",
  modelo: "Modelo",
  serial: "Serial",
  licencia: "Licencia",
  eos: "EOS",
  comentario: "Comentario",
};

const createEmptyRow = () =>
  Object.fromEntries(COLUMNS.map((column) => [column, ""]));

function AlertMessage({ type = "error", children, onClose }) {
  const success = type === "success";

  return (
    <div
      className={`flex items-start gap-3 rounded-xl border p-4 ${
        success
          ? "border-emerald-200 bg-emerald-50 text-emerald-800"
          : "border-red-200 bg-red-50 text-red-800"
      }`}
    >
      {success ? (
        <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0" />
      ) : (
        <AlertCircle className="mt-0.5 h-5 w-5 shrink-0" />
      )}

      <p className="flex-1 whitespace-pre-line text-sm">{children}</p>

      {onClose && (
        <button type="button" onClick={onClose}>
          <X className="h-4 w-4" />
        </button>
      )}
    </div>
  );
}

export default function AssetsUpload() {
  const [mode, setMode] = useState("csv");
  const [file, setFile] = useState(null);
  const [delimiter, setDelimiter] = useState("auto");
  const [preview, setPreview] = useState(null);
  const [rows, setRows] = useState([createEmptyRow()]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState(null);

  const fileInputRef = useRef(null);

  const clearMessage = () => setMessage(null);

  const handleFileChange = (event) => {
    const selected = event.target.files?.[0];

    setFile(selected || null);
    setPreview(null);
    clearMessage();
  };

  const handlePreview = async () => {
    if (!file) {
      setMessage({
        type: "error",
        text: "Selecciona un archivo CSV.",
      });
      return;
    }

    setLoading(true);
    clearMessage();

    try {
      const result = await previewAssetsCsv(file, delimiter);
      setPreview(result);
    } catch (error) {
      setPreview(null);
      setMessage({
        type: "error",
        text: error.message,
      });
    } finally {
      setLoading(false);
    }
  };

  const handleConfirmCsv = async () => {
    if (!preview?.registros_validos?.length) return;

    const items = preview.registros_validos.map(
      (record) => record.datos
    );

    const accepted = window.confirm(
      `¿Confirmas la importación de ${items.length} dispositivos en Postgres?`
    );

    if (!accepted) return;

    setLoading(true);
    clearMessage();

    try {
      const result = await confirmAssetsUpload(items);

      setMessage({
        type: "success",
        text: `${result.mensaje} Procesados: ${result.total_procesados ?? items.length}. Insertados: ${result.insertados}. Actualizados: ${result.actualizados}. Sin cambios: ${result.sin_cambios}.`,
      });

      setPreview(null);
      setFile(null);

      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    } catch (error) {
      setMessage({
        type: "error",
        text: error.message,
      });
    } finally {
      setLoading(false);
    }
  };

  const updateCell = (rowIndex, column, value) => {
    setRows((current) =>
      current.map((row, index) =>
        index === rowIndex
          ? { ...row, [column]: value }
          : row
      )
    );
  };

  const handlePasteCells = (event, startRow, startColumn) => {
    const text = event.clipboardData.getData("text/plain");
    if (!text.includes("\t") && !/[\r\n]/.test(text)) return;
    event.preventDefault();

    const matrix = text.replace(/\r\n/g, "\n").replace(/\r/g, "\n")
      .replace(/\n$/, "").split("\n").map(line => line.split("\t"));
    if (startRow + matrix.length > 500) {
      setMessage({ type: "error", text: "La carga manual permite máximo 500 filas." });
      return;
    }
    if (matrix.some(cells => startColumn + cells.length > COLUMNS.length)) {
      setMessage({ type: "error", text: "Los datos pegados exceden las columnas disponibles." });
      return;
    }

    setRows(current => {
      const next = current.map(row => ({ ...row }));
      while (next.length < startRow + matrix.length) next.push(createEmptyRow());
      matrix.forEach((cells, rowOffset) => {
        cells.forEach((value, colOffset) => {
          const column = COLUMNS[startColumn + colOffset];
          next[startRow + rowOffset][column] = value.trim();
        });
      });
      return next;
    });
    clearMessage();
  };

  const addRow = () => {
    setRows((current) => [...current, createEmptyRow()]);
  };

  const removeRow = (index) => {
    setRows((current) =>
      current.length === 1
        ? [createEmptyRow()]
        : current.filter((_, rowIndex) => rowIndex !== index)
    );
  };

  const handleSaveManual = async () => {
    const items = rows.map((row) =>
      Object.fromEntries(
        Object.entries(row).map(([column, value]) => [
          column,
          String(value ?? "").trim() || (column === "eos" ? "2099-12-31" : "-"),
        ])
      )
    );

    const accepted = window.confirm(
      `¿Deseas guardar ${items.length} dispositivos en Postgres?`
    );

    if (!accepted) return;

    setLoading(true);
    clearMessage();

    try {
      const result = await saveAssetsManual(items);

      setMessage({
        type: "success",
        text: `${result.mensaje} Procesados: ${result.total_procesados ?? items.length}. Insertados: ${result.insertados}. Actualizados: ${result.actualizados}. Sin cambios: ${result.sin_cambios}.`,
      });

      setRows([createEmptyRow()]);
    } catch (error) {
      setMessage({
        type: "error",
        text: error.message,
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mx-auto max-w-[1600px] space-y-6 pb-10">
      {/* ENCABEZADO */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-violet-600">
            Assets Management
          </p>

          <h1 className="mt-1 text-3xl font-bold tracking-tight text-slate-900">
            Upload File
          </h1>

          <p className="mt-2 text-sm text-slate-500">
            Registro e importación de activos tecnológicos.
          </p>
        </div>

        <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-violet-600 text-white shadow-sm">
          <Database className="h-6 w-6" />
        </div>
      </div>

      {/* MODALIDADES */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <button
          type="button"
          onClick={() => {
            setMode("csv");
            clearMessage();
          }}
          className={`flex items-center gap-4 rounded-2xl border p-5 text-left transition ${
            mode === "csv"
              ? "border-violet-400 bg-violet-50 ring-1 ring-violet-200"
              : "border-slate-200 bg-white hover:border-violet-200"
          }`}
        >
          <div className="rounded-xl bg-violet-100 p-3 text-violet-700">
            <FileSpreadsheet className="h-6 w-6" />
          </div>

          <div>
            <h2 className="font-semibold text-slate-900">
              Importar CSV
            </h2>
            <p className="mt-1 text-sm text-slate-500">
              Carga masiva con validación y vista previa.
            </p>
          </div>
        </button>

        <button
          type="button"
          onClick={() => {
            setMode("manual");
            clearMessage();
          }}
          className={`flex items-center gap-4 rounded-2xl border p-5 text-left transition ${
            mode === "manual"
              ? "border-violet-400 bg-violet-50 ring-1 ring-violet-200"
              : "border-slate-200 bg-white hover:border-violet-200"
          }`}
        >
          <div className="rounded-xl bg-blue-100 p-3 text-blue-700">
            <TableProperties className="h-6 w-6" />
          </div>

          <div>
            <h2 className="font-semibold text-slate-900">
              Carga manual
            </h2>
            <p className="mt-1 text-sm text-slate-500">
              Registra dispositivos en una tabla editable.
            </p>
          </div>
        </button>
      </div>

      {/* MENSAJES */}
      {message && (
        <AlertMessage
          type={message.type}
          onClose={clearMessage}
        >
          {message.text}
        </AlertMessage>
      )}

      {/* IMPORTACIÓN CSV */}
      {mode === "csv" && (
        <div className="space-y-6">
          <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <div className="mb-5">
              <h2 className="text-lg font-semibold text-slate-900">
                Seleccionar archivo
              </h2>
              <p className="mt-1 text-sm text-slate-500">
                Archivo CSV en UTF-8, máximo 5 MB y 500 filas.
              </p>
              <label className="mt-4 block max-w-sm text-sm font-medium text-slate-700">
                Delimitador del archivo
                <select
                  value={delimiter}
                  onChange={(event) => {
                    setDelimiter(event.target.value);
                    setPreview(null);
                    clearMessage();
                  }}
                  disabled={loading}
                  className="mt-2 w-full rounded-lg border border-slate-300 bg-white px-3 py-2"
                >
                  <option value="auto">Detectar automáticamente</option>
                  <option value=",">Coma (,)</option>
                  <option value=";">Punto y coma (;)</option>
                  <option value="$">Signo dólar ($)</option>
                  <option value="tab">Tabulación (TAB)</option>
                  <option value="|">Barra vertical (|)</option>
                </select>
              </label>
            </div>

            <div className="rounded-2xl border-2 border-dashed border-slate-300 bg-slate-50 p-8 text-center">
              <UploadCloud className="mx-auto h-12 w-12 text-violet-500" />

              <p className="mt-3 font-medium text-slate-800">
                Selecciona un archivo CSV
              </p>

              <p className="mt-1 text-sm text-slate-500">
                Las columnas desconocidas serán ignoradas.
              </p>

              <input
                ref={fileInputRef}
                type="file"
                accept=".csv,text/csv"
                onChange={handleFileChange}
                className="mx-auto mt-5 block max-w-full text-sm text-slate-600 file:mr-4 file:rounded-lg file:border-0 file:bg-violet-600 file:px-4 file:py-2 file:font-medium file:text-white hover:file:bg-violet-700"
              />

              {file && (
                <p className="mt-3 text-sm font-medium text-slate-700">
                  {file.name}
                </p>
              )}
            </div>

            <div className="mt-5 flex justify-end">
              <button
                type="button"
                disabled={loading || !file}
                onClick={handlePreview}
                className="inline-flex items-center gap-2 rounded-xl bg-violet-600 px-5 py-3 text-sm font-semibold text-white transition hover:bg-violet-700 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {loading ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <FileCheck2 className="h-4 w-4" />
                )}
                Validar archivo
              </button>
            </div>
          </section>

          {preview && (
            <>
              <p className="text-sm text-slate-500">
                Delimitador utilizado: <strong>{preview.delimitador_detectado ?? delimiter}</strong>
              </p>
              {/* ESTADÍSTICAS */}
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                {[
                  {
                    label: "Registros válidos",
                    value: preview.total_validos,
                    color: "text-emerald-600",
                  },
                  {
                    label: "Registros con errores",
                    value: preview.total_errores,
                    color: "text-red-600",
                  },
                  {
                    label: "Columnas ignoradas",
                    value: preview.columnas_ignoradas.length,
                    color: "text-amber-600",
                  },
                ].map((stat) => (
                  <div
                    key={stat.label}
                    className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"
                  >
                    <p className="text-sm text-slate-500">
                      {stat.label}
                    </p>
                    <p
                      className={`mt-2 text-3xl font-bold ${stat.color}`}
                    >
                      {stat.value}
                    </p>
                  </div>
                ))}
              </div>

              {preview.columnas_ignoradas.length > 0 && (
                <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
                  <strong>Columnas ignoradas: </strong>
                  {preview.columnas_ignoradas.join(", ")}
                </div>
              )}

              {(preview.columnas_vacias_omitidas > 0 || preview.sin_serial_valido > 0 || preview.identidades_repetidas?.length > 0) && (
                <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
                  <p className="font-semibold">Observaciones de la carga</p>
                  {preview.columnas_vacias_omitidas > 0 && (
                    <p className="mt-1">Se omitieron {preview.columnas_vacias_omitidas} columnas finales totalmente vacías.</p>
                  )}
                  {preview.sin_serial_valido > 0 && (
                    <p className="mt-1">{preview.sin_serial_valido} filas no tienen serial válido: se consideran activos independientes al importar.</p>
                  )}
                  {preview.identidades_repetidas?.length > 0 && (
                    <div className="mt-2">
                      <p className="font-medium">{preview.identidades_repetidas.length} coincidencias repetidas de fabricante + serial dentro del mismo CSV. Estas filas pueden actualizar un mismo activo:</p>
                      <ul className="mt-1 list-disc pl-5">
                        {preview.identidades_repetidas.slice(0, 8).map((entry, i) => (
                          <li key={i}>Filas {entry.fila_primera} y {entry.fila_repetida}: {entry.fabricante} / {entry.serial}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  <p className="mt-2">La confirmación inserta equipos nuevos y actualiza coincidencias existentes por fabricante + serial. Revisa los totales después de guardar.</p>
                </div>
              )}

              {/* TABLA DE PREVISUALIZACIÓN */}
              <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
                <div className="border-b border-slate-200 p-5">
                  <h2 className="font-semibold text-slate-900">
                    Vista previa de registros
                  </h2>
                </div>

                <div className="max-h-[460px] overflow-auto">
                  <table className="w-full min-w-[950px] text-left text-sm">
                    <thead className="sticky top-0 bg-slate-100 text-slate-600">
                      <tr>
                        {[
                          "Fila",
                          "Dispositivo",
                          "Plataforma",
                          "Tipo",
                          "Fabricante",
                          "Modelo",
                          "Serial",
                          "EOS",
                          "Estado",
                        ].map((header) => (
                          <th
                            key={header}
                            className="px-4 py-3 font-semibold"
                          >
                            {header}
                          </th>
                        ))}
                      </tr>
                    </thead>

                    <tbody>
                      {preview.registros_validos.map((record) => (
                        <tr
                          key={record.fila}
                          className="border-t border-slate-100"
                        >
                          <td className="px-4 py-3">{record.fila}</td>
                          <td className="px-4 py-3">
                            {record.datos.dispositivo}
                          </td>
                          <td className="px-4 py-3">
                            {record.datos.plataforma}
                          </td>
                          <td className="px-4 py-3">
                            {record.datos.tipo}
                          </td>
                          <td className="px-4 py-3">
                            {record.datos.fabricante}
                          </td>
                          <td className="px-4 py-3">
                            {record.datos.modelo}
                          </td>
                          <td className="px-4 py-3">
                            {record.datos.serial}
                          </td>
                          <td className="px-4 py-3">
                            {record.datos.eos}
                          </td>
                          <td className="px-4 py-3">
                            <span className="rounded-full bg-emerald-100 px-2.5 py-1 text-xs font-semibold text-emerald-700">
                              Válido
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {preview.registros_validos.length === 0 && (
                  <p className="p-6 text-center text-sm text-slate-500">
                    No se encontraron registros válidos.
                  </p>
                )}
              </section>

              {/* ERRORES */}
              {preview.errores.length > 0 && (
                <section className="rounded-2xl border border-red-200 bg-white p-5">
                  <h3 className="font-semibold text-red-700">
                    Registros con errores
                  </h3>

                  <div className="mt-3 space-y-2">
                    {preview.errores.map((error, index) => (
                      <p
                        key={index}
                        className="rounded-lg bg-red-50 p-3 text-sm text-red-700"
                      >
                        Fila {error.fila}: {error.error}
                      </p>
                    ))}
                  </div>
                </section>
              )}

              <div className="flex justify-end">
                <button
                  type="button"
                  disabled={
                    loading ||
                    preview.total_validos === 0 ||
                    preview.total_errores > 0
                  }
                  onClick={handleConfirmCsv}
                  className="inline-flex items-center gap-2 rounded-xl bg-emerald-600 px-6 py-3 text-sm font-semibold text-white transition hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {loading ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Database className="h-4 w-4" />
                  )}
                  Confirmar carga en Postgres
                </button>
              </div>

              {preview.total_errores > 0 && (
                <p className="text-right text-sm text-amber-700">
                  Corrige los errores del CSV y vuelve a validarlo
                  antes de confirmar la carga.
                </p>
              )}
            </>
          )}
        </div>
      )}

      {/* CARGA MANUAL */}
      {mode === "manual" && (
        <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-200 p-5">
            <div>
              <h2 className="text-lg font-semibold text-slate-900">
                Registro manual de dispositivos
              </h2>
              <p className="mt-1 text-sm text-slate-500">
                Todos los campos son opcionales por ahora. Los valores vacíos se guardan como guion (-); EOS vacío utiliza la fecha de referencia 31/12/2099. Puedes pegar rangos desde Excel (Ctrl+V).
              </p>
            </div>

            <button
              type="button"
              onClick={addRow}
              disabled={loading || rows.length >= 500}
              className="inline-flex items-center gap-2 rounded-xl border border-violet-200 bg-violet-50 px-4 py-2 text-sm font-semibold text-violet-700 hover:bg-violet-100 disabled:opacity-50"
            >
              <Plus className="h-4 w-4" />
              Agregar fila
            </button>
          </div>

          <div className="max-h-[540px] overflow-auto">
            <table className="min-w-max border-collapse text-sm">
              <thead className="sticky top-0 z-10 bg-slate-100">
                <tr>
                  <th className="sticky left-0 z-20 bg-slate-100 px-4 py-3 text-left">
                    #
                  </th>

                  {COLUMNS.map((column) => (
                    <th
                      key={column}
                      className="min-w-[170px] px-3 py-3 text-left font-semibold text-slate-600"
                    >
                      {LABELS[column]}
                      {REQUIRED.includes(column) && (
                        <span className="ml-1 text-red-500">*</span>
                      )}
                    </th>
                  ))}

                  <th className="px-4 py-3">Acciones</th>
                </tr>
              </thead>

              <tbody>
                {rows.map((row, rowIndex) => (
                  <tr
                    key={rowIndex}
                    className="border-t border-slate-200"
                  >
                    <td className="sticky left-0 bg-white px-4 py-3 font-medium text-slate-500">
                      {rowIndex + 1}
                    </td>

                    {COLUMNS.map((column, columnIndex) => (
                      <td key={column} className="px-2 py-2">
                        <input
                          type={column === "eos" ? "date" : "text"}
                          value={row[column]}
                          onPaste={(event) => handlePasteCells(event, rowIndex, columnIndex)}
                          onChange={(event) =>
                            updateCell(
                              rowIndex,
                              column,
                              event.target.value
                            )
                          }
                          disabled={loading}
                          placeholder={LABELS[column]}
                          className="w-full min-w-[160px] rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-violet-400 focus:ring-2 focus:ring-violet-100"
                        />
                      </td>
                    ))}

                    <td className="px-4 py-2">
                      <button
                        type="button"
                        disabled={loading}
                        onClick={() => removeRow(rowIndex)}
                        className="rounded-lg p-2 text-red-500 hover:bg-red-50 disabled:opacity-50"
                        title="Eliminar fila"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-4 border-t border-slate-200 p-5">
            <p className="text-sm text-slate-500">
              {rows.length} fila(s) preparadas para registrar.
            </p>

            <button
              type="button"
              disabled={loading}
              onClick={handleSaveManual}
              className="inline-flex items-center gap-2 rounded-xl bg-violet-600 px-6 py-3 text-sm font-semibold text-white hover:bg-violet-700 disabled:opacity-50"
            >
              {loading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Database className="h-4 w-4" />
              )}
              Guardar dispositivos
            </button>
          </div>
        </section>
      )}
    </div>
  );
}