import { useEffect, useState } from "react";
import {
  Activity,
  AlertTriangle,
  BarChart3,
  CheckCircle2,
  Clock3,
  Database,
  MapPin,
  Monitor,
  RefreshCw,
  Server,
  XCircle,
} from "lucide-react";

import {
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Tooltip,
  Legend,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
} from "recharts";

import { getAssetsDashboard } from "../../services/assets/assetsApi";

// Colores del dashboard
const COLORS = {
  vigentes: "#16a34a",
  inactivos: "#f59e0b",
  danados: "#ef4444",
  eos: "#8b5cf6",
  principal: "#7c3aed",
  neutro: "#e2e8f0",
};

const STATUS_COLORS = {
  "activo/vigente": "#16a34a",
  "inactivo/no vigente": "#f59e0b",
  "inactivo/dañado": "#ef4444",
  "inactivo/danado": "#ef4444",
};

const EXTRA_COLORS = [
  "#3b82f6",
  "#8b5cf6",
  "#06b6d4",
  "#ec4899",
  "#64748b",
];

// Componente de tarjeta KPI
function KpiCard({
  title,
  value,
  icon: Icon,
  color,
  background,
  description,
}) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <div
        className={`mb-4 flex h-14 w-14 items-center justify-center rounded-full ${background}`}
      >
        <Icon size={30} className="text-white" />
      </div>

      <p className="text-sm font-bold text-slate-700">
        {title}
      </p>

      <h2 className="mt-2 text-3xl font-bold text-slate-900">
        {Number(value || 0).toLocaleString("es-EC")}
      </h2>
    </div>
  );
}

// Componente para mostrar gráficos sin registros
function EmptyChart({ message }) {
  return (
    <div className="flex h-full min-h-[250px] flex-col items-center justify-center text-center">
      <BarChart3 className="mb-3 h-10 w-10 text-slate-300" />

      <p className="text-sm font-medium text-slate-500">
        {message}
      </p>

      <p className="mt-1 text-xs text-slate-400">
        El gráfico se actualizará al registrar dispositivos.
      </p>
    </div>
  );
}

// Dashboard principal
export default function AssetsDashboard() {
  const [data, setData] = useState(null);
  const [ciudad, setCiudad] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    let cancelled = false;

    async function loadDashboard() {
      setLoading(true);
      setError("");

      try {
        const result = await getAssetsDashboard(ciudad);

        if (!cancelled) {
          setData(result);
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            err.message || "No se pudo cargar el dashboard."
          );
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    loadDashboard();

    return () => {
      cancelled = true;
    };
  }, [ciudad, refreshKey]);

  const kpis = data?.kpis ?? {};

  const total = Number(kpis.total || 0);
  const vigentes = Number(kpis.activos_vigentes || 0);
  const inactivos = Number(kpis.inactivos_no_vigentes || 0);
  const danados = Number(kpis.danados || 0);
  const eos = Number(kpis.eos_vencido || 0);

  const porcentajeVigentes =
    total > 0 ? Math.round((vigentes / total) * 100) : 0;

  // Distribución real de dispositivos por estado.
  // Los valores provienen directamente de Oracle.
  const estados = data?.estados ?? [];

  const pieData = estados
    .filter((item) => Number(item.cantidad || 0) > 0)
    .map((item, index) => {
      const nombre = String(item.nombre || "Sin especificar").trim();

      const estadoNormalizado = nombre.toLowerCase();

      return {
        name: nombre,
        value: Number(item.cantidad || 0),
        color:
          STATUS_COLORS[estadoNormalizado] ??
          EXTRA_COLORS[index % EXTRA_COLORS.length],
      };
    });

  const totalGrafico = pieData.reduce(
    (sum, item) => sum + item.value,
    0
  );

const chartData =
  totalGrafico > 0
    ? pieData
    : [
        {
          name: "Sin registros",
          value: 1,
          color: COLORS.neutro,
        },
      ];

  const ciudades = data?.ciudades ?? [];

  const tiposData = (data?.tipos ?? []).map((item) => ({
    nombre: item.nombre,
    cantidad: Number(item.cantidad || 0),
  }));

  const plataformasData = (data?.plataformas ?? []).map(
    (item) => ({
      nombre: item.nombre,
      cantidad: Number(item.cantidad || 0),
    })
  );

  return (
    <div className="space-y-6 pb-8">
      {/* ENCABEZADO */}
      <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-center">
        <div>
          <div className="mb-2 flex items-center gap-3">
            <div>
              <h1 className="text-2xl font-bold text-slate-900">
                Dashboard Control de Activos
              </h1>

              <p className="mt-1 text-sm text-slate-500">
                Monitoreo y estadísticas del inventario tecnológico
              </p>
            </div>
          </div>
        </div>

        <button
          type="button"
          onClick={() => setRefreshKey((prev) => prev + 1)}
          disabled={loading}
          className="flex items-center justify-center gap-2 rounded-xl bg-violet-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-violet-700 disabled:opacity-50"
        >
          <RefreshCw
            className={`h-4 w-4 ${
              loading ? "animate-spin" : ""
            }`}
          />

          Actualizar datos
        </button>
      </div>

      {/* FILTRO POR CIUDAD */}
      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div className="flex items-center gap-3">
            <div className="rounded-xl bg-violet-50 p-3">
              <MapPin className="h-5 w-5 text-violet-600" />
            </div>

            <div>
              <h2 className="font-semibold text-slate-900">
                Filtros del inventario
              </h2>

              <p className="text-xs text-slate-500">
                Consulta las estadísticas por ubicación
              </p>
            </div>
          </div>

          <div className="w-full md:w-72">
            <label className="mb-1 block text-xs font-semibold text-slate-600">
              Ciudad
            </label>

            <select
              value={ciudad}
              onChange={(event) =>
                setCiudad(event.target.value)
              }
              className="w-full rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-sm text-slate-700 outline-none focus:border-violet-500 focus:ring-2 focus:ring-violet-100"
            >
              <option value="">Todas las ciudades</option>

              {ciudades.map((item) => (
                <option
                  key={item.nombre}
                  value={item.nombre}
                >
                  {item.nombre} ({item.cantidad})
                </option>
              ))}
            </select>
          </div>
        </div>
      </section>

      {/* ERROR */}
      {error && (
        <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5" />
            <span>{error}</span>
          </div>
        </div>
      )}

      {/* TARJETAS KPI */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <KpiCard
          title="Total dispositivos"
          value={total}
          icon={Database}
          background="bg-blue-600"
          description="Equipos registrados en inventario"
        />

        <KpiCard
          title="Activos vigentes"
          value={vigentes}
          icon={CheckCircle2}
          background="bg-green-600"
          description="Dispositivos operativos y vigentes"
        />

        <KpiCard
          title="Inactivos / no vigentes"
          value={inactivos}
          icon={XCircle}
          background="bg-amber-600"
          description="Equipos fuera de vigencia"
        />

        <KpiCard
          title="Dispositivos dañados"
          value={danados}
          icon={AlertTriangle}
          background="bg-red-600"
          description="Equipos reportados con daños"
        />

        <KpiCard
          title="EOS vencido"
          value={eos}
          icon={Clock3}
          background="bg-violet-600"
          description="Equipos con fin de soporte vencido"
        />
      </div>

      {/* GRÁFICOS PRINCIPALES */}
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        {/* GRÁFICO CIRCULAR */}
        <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="mb-5 flex items-center gap-3">
            <div className="rounded-lg bg-violet-50 p-2">
              <Activity className="h-5 w-5 text-violet-600" />
            </div>

            <div>
              <h2 className="text-lg font-bold text-slate-900">
                Estado general de dispositivos
              </h2>

              <p className="text-xs text-slate-500">
                Distribución de dispositivos según su estado registrado
              </p>
            </div>
          </div>

          <div className="relative h-[320px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={chartData}
                  dataKey="value"
                  nameKey="name"
                  cx="50%"
                  cy="45%"
                  innerRadius={75}
                  outerRadius={105}
                  paddingAngle={total > 0 ? 3 : 0}
                  stroke="none"
                  isAnimationActive={total > 0}
                >
                  {chartData.map((entry, index) => (
                    <Cell
                      key={`cell-${index}`}
                      fill={entry.color}
                    />
                  ))}
                </Pie>

                {totalGrafico > 0 && (
                  <Tooltip
                    formatter={(value, name) => [
                      `${value} dispositivo${Number(value) === 1 ? "" : "s"} (${(
                        (Number(value) / totalGrafico) *
                        100
                      ).toFixed(1)}%)`,
                      name,
                    ]}
                  />
                )}
                {totalGrafico > 0 && (
                  <Legend
                    verticalAlign="bottom"
                    formatter={(value) => {
                      const item = pieData.find((estado) => estado.name === value);

                      return `${value} (${item?.value ?? 0})`;
                    }}
                  />
                )}
              </PieChart>
            </ResponsiveContainer>

            {/* PORCENTAJE CENTRAL */}
            <div className="pointer-events-none absolute left-1/2 top-[45%] -translate-x-1/2 -translate-y-1/2 text-center">
              <p className="text-3xl font-bold text-slate-900">
                {porcentajeVigentes}%
              </p>

              <p className="text-xs text-slate-500">
                Vigentes
              </p>
            </div>
          </div>

          {total === 0 && (
            <p className="mt-2 text-center text-sm text-slate-400">
              Aún no existen dispositivos registrados.
            </p>
          )}
        </section>

        {/* GRÁFICO POR CIUDAD */}
        <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="mb-5 flex items-center gap-3">
            <div className="rounded-lg bg-blue-50 p-2">
              <MapPin className="h-5 w-5 text-blue-600" />
            </div>

            <div>
              <h2 className="text-lg font-bold text-slate-900">
                Dispositivos por tipo
              </h2>

              <p className="text-xs text-slate-500">
                Distribución de equipos según su tipo tecnológico
              </p>
            </div>
          </div>

          <div className="h-[320px] w-full">
            {tiposData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={tiposData}
                  margin={{
                    top: 10,
                    right: 10,
                    left: -15,
                    bottom: 30,
                  }}
                >
                  <CartesianGrid
                    strokeDasharray="3 3"
                    vertical={false}
                  />

                  <XAxis
                    dataKey="nombre"
                    tick={{ fontSize: 11 }}
                    angle={-20}
                    textAnchor="end"
                    interval={0}
                  />

                  <YAxis
                    allowDecimals={false}
                    tick={{ fontSize: 12 }}
                  />

                  <Tooltip />

                  <Bar
                    dataKey="cantidad"
                    name="Dispositivos"
                    fill={COLORS.principal}
                    radius={[6, 6, 0, 0]}
                    maxBarSize={55}
                  />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <EmptyChart message="Sin tipos de dispositivos registrados" />
            )}
          </div>
        </section>
      </div>

      {/* GRÁFICO DE PLATAFORMAS */}
      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="mb-5 flex items-center gap-3">
          <div className="rounded-lg bg-indigo-50 p-2">
            <Server className="h-5 w-5 text-indigo-600" />
          </div>

          <div>
            <h2 className="text-lg font-bold text-slate-900">
              Dispositivos por plataforma
            </h2>

            <p className="text-xs text-slate-500">
              Clasificación de equipos según plataforma tecnológica
            </p>
          </div>
        </div>

        <div className="h-[300px] w-full">
          {plataformasData.length > 0 ? (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={plataformasData}
                layout="vertical"
                margin={{
                  top: 5,
                  right: 30,
                  left: 25,
                  bottom: 5,
                }}
              >
                <CartesianGrid
                  strokeDasharray="3 3"
                  horizontal={false}
                />

                <XAxis
                  type="number"
                  allowDecimals={false}
                />

                <YAxis
                  type="category"
                  dataKey="nombre"
                  width={110}
                  tick={{ fontSize: 12 }}
                />

                <Tooltip />

                <Bar
                  dataKey="cantidad"
                  name="Dispositivos"
                  fill="#6366f1"
                  radius={[0, 6, 6, 0]}
                  maxBarSize={35}
                />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <EmptyChart message="Sin plataformas registradas" />
          )}
        </div>
      </section>

      {/* RESUMEN INFERIOR */}
      <div className="rounded-2xl border border-violet-100 bg-violet-50 p-5">
        <div className="flex items-start gap-3">
          <BarChart3 className="mt-0.5 h-5 w-5 text-violet-600" />

          <div>
            <h3 className="font-semibold text-violet-900">
              Resumen del inventario
            </h3>

            <p className="mt-1 text-sm leading-relaxed text-violet-700">
              {total === 0
                ? "Actualmente no existen dispositivos registrados en el inventario. Los indicadores y gráficos se actualizarán automáticamente cuando se incorporen equipos."
                : `Se encuentran registrados ${total} dispositivos, de los cuales ${vigentes} están vigentes, ${inactivos} figuran como inactivos o no vigentes, ${danados} presentan daños y ${eos} tienen el EOS vencido.`}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}