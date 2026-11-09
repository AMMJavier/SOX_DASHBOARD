import { useEffect, useState } from "react";
import {
  MapPin,
  Building2,
  Boxes,
  RefreshCw,
  AlertTriangle,
  Search,
} from "lucide-react";

import {
  MapContainer,
  TileLayer,
  CircleMarker,
  Popup,
  Tooltip,
} from "react-leaflet";

import "leaflet/dist/leaflet.css";

import { getLocations } from "../../services/assets/catalog";

// Coordenadas aproximadas del centro de cada ciudad.
const CITY_COORDINATES = {
  quito: [-0.1807, -78.4678],
  tulcan: [0.8119, -77.7173],
  "santo domingo": [-0.2531, -79.1754],
  guayaquil: [-2.1894, -79.8891],
};

// Normaliza nombres para consultar las coordenadas.
function normalizeCityName(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .trim()
    .replace(/\s+/g, " ")
    .toLowerCase();
}

// Las ciudades desconocidas se consultan una vez y se guardan en el navegador.
// Nominatim exige limitar la frecuencia de solicitudes; no se consulta por cada render.
const CACHE_KEY = "assets-city-coordinates-v1";
function readCoordinateCache() {
  try { return JSON.parse(localStorage.getItem(CACHE_KEY) || "{}"); }
  catch { return {}; }
}
function sleep(ms) { return new Promise((resolve) => setTimeout(resolve, ms)); }

export default function Locations() {
  const [cities, setCities] = useState([]);
  const [withoutCity, setWithoutCity] = useState(0);
  const [coordinates, setCoordinates] = useState(() => ({ ...CITY_COORDINATES, ...readCoordinateCache() }));
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [refresh, setRefresh] = useState(0);

  useEffect(() => {
    let active = true;

    async function load() {
      setLoading(true);
      setError("");

      try {
        const data = await getLocations();

        if (!active) return;

        const items = Array.isArray(data?.items) ? data.items : [];
        setWithoutCity(Number(data?.sin_ciudad ?? 0));
        setCities(
        items.map((item) => ({
            nombre: item.ciudad ?? item.nombre ?? "Sin especificar",
            cantidad: Number(
            item.total_dispositivos ?? item.cantidad ?? 0
            ),
        }))
        );
      } catch (err) {
        if (active) {
          setError(err.message || "Error al consultar ubicaciones.");
          setCities([]);
          setWithoutCity(0);
        }
      } finally {
        if (active) setLoading(false);
      }
    }

    load();

    return () => {
      active = false;
    };
  }, [refresh]);

  useEffect(() => {
    let cancelled = false;
    async function resolveCities() {
      const cache = { ...CITY_COORDINATES, ...readCoordinateCache() };
      const pending = cities.filter((city) => {
        const key = normalizeCityName(city.nombre);
        return key && !Object.prototype.hasOwnProperty.call(cache, key);
      });
      for (const city of pending) {
        if (cancelled) break;
        const key = normalizeCityName(city.nombre);
        try {
          const url = new URL("https://nominatim.openstreetmap.org/search");
          url.searchParams.set("q", `${city.nombre}, Ecuador`);
          url.searchParams.set("format", "jsonv2");
          url.searchParams.set("limit", "1");
          url.searchParams.set("countrycodes", "ec");
          const response = await fetch(url.toString(), { headers: { Accept: "application/json" } });
          if (!response.ok) throw new Error(`Geocodificación HTTP ${response.status}`);
          const results = await response.json();
          const first = results[0];
          if (first && Number.isFinite(Number(first.lat)) && Number.isFinite(Number(first.lon))) {
            cache[key] = [Number(first.lat), Number(first.lon)];
            if (!cancelled) {
              setCoordinates((current) => ({ ...current, [key]: cache[key] }));
              try { localStorage.setItem(CACHE_KEY, JSON.stringify(cache)); } catch { /* sin almacenamiento */ }
            }
          }
        } catch (error) {
          console.warn("No se pudieron obtener coordenadas para", city.nombre, error);
        }
        // Respetar un máximo de una petición por segundo.
        if (!cancelled) await sleep(1100);
      }
    }
    resolveCities();
    return () => { cancelled = true; };
  }, [cities]);

  const filtered = cities.filter((city) =>
    String(city.nombre || "")
      .toLowerCase()
      .includes(search.toLowerCase())
  );

  const totalDevices = cities.reduce(
    (sum, city) => sum + city.cantidad,
    0
  );

  const topCity = [...cities].sort(
    (a, b) => b.cantidad - a.cantidad
  )[0];

  return (
    <div className="space-y-6 pb-10">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-sm font-semibold text-violet-600">
            Assets Management
          </p>

          <h1 className="mt-1 text-3xl font-bold text-slate-900">
            Ubicaciones
          </h1>

          <p className="mt-2 text-sm text-slate-500">
            Distribución geográfica de los activos tecnológicos.
          </p>
        </div>

        <button
          onClick={() => setRefresh((value) => value + 1)}
          disabled={loading}
          className="flex items-center gap-2 rounded-xl bg-violet-600 px-4 py-3 text-sm font-semibold text-white hover:bg-violet-700 disabled:opacity-50"
        >
          <RefreshCw
            size={17}
            className={loading ? "animate-spin" : ""}
          />
          Actualizar
        </button>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-violet-600 text-white">
            <MapPin size={24} />
          </div>
          <p className="text-sm font-medium text-slate-600">
            Ciudades registradas
          </p>
          <p className="mt-1 text-3xl font-bold text-slate-900">
            {cities.length}
          </p>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-blue-600 text-white">
            <Boxes size={24} />
          </div>
          <p className="text-sm font-medium text-slate-600">
            Dispositivos con ciudad
          </p>
          <p className="mt-1 text-3xl font-bold text-slate-900">
            {totalDevices.toLocaleString("es-EC")}
          </p>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-emerald-600 text-white">
            <Building2 size={24} />
          </div>
          <p className="text-sm font-medium text-slate-600">
            Ciudad con más dispositivos
          </p>
          <p className="mt-2 truncate text-xl font-bold text-slate-900">
            {topCity?.nombre || "Sin registros"}
          </p>
          <p className="mt-1 text-xs text-slate-500">
            {topCity ? `${topCity.cantidad} dispositivos` : ""}
          </p>
        </div>
      </div>

      {withoutCity > 0 && !loading && (
        <div role="status" className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
          Hay {withoutCity} activos sin ciudad registrada (vacía o «-»). No aparecen en los marcadores ni en el resumen por ciudad; revisa su ubicación en Inventario.
        </div>
      )}

      {error && (
        <div className="flex items-center gap-2 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          <AlertTriangle size={19} />
          {error}
        </div>
      )}

      <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="p-6">
          <h2 className="text-lg font-semibold text-slate-900">
            Mapa de dispositivos en Ecuador
          </h2>

          <p className="mt-1 text-sm text-slate-500">
            Distribución geográfica de los activos tecnológicos por ciudad.
          </p>
        </div>

        <div className="h-[500px] w-full">
          <MapContainer
            center={[-1.6, -78.5]}
            zoom={7}
            minZoom={5}
            scrollWheelZoom={true}
            className="h-full w-full"
          >
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />

            {filtered.map((city) => {
              const pointCoordinates =
                coordinates[normalizeCityName(city.nombre)];

              if (!pointCoordinates) return null;

              return (
                <CircleMarker
                  key={city.nombre}
                  center={pointCoordinates}
                  radius={Math.max(9, Math.min(24, 8 + city.cantidad * 2))}
                  pathOptions={{
                    color: "#6d28d9",
                    fillColor: "#7c3aed",
                    fillOpacity: 0.8,
                    weight: 2,
                  }}
                >
                  <Tooltip direction="top">
                    {city.nombre}: {city.cantidad} dispositivos
                  </Tooltip>

                  <Popup>
                    <strong>{city.nombre}</strong>
                    <p>Dispositivos registrados: {city.cantidad}</p>
                  </Popup>
                </CircleMarker>
              );
            })}
          </MapContainer>
        </div>

        <div className="border-t border-slate-200 px-6 py-3 text-xs text-slate-500">
          Los marcadores representan ubicaciones aproximadas por ciudad.
          Las ciudades nuevas se ubican automáticamente cuando el servicio de geocodificación responde. Si no se encuentra una ciudad, permanece en el listado.
        </div>
      </section>

      <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-200 p-5">
          <div>
            <h2 className="text-lg font-semibold text-slate-900">
              Listado de ciudades
            </h2>
            <p className="mt-1 text-xs text-slate-500">
              Resumen de activos por ubicación.
            </p>
          </div>

          <div className="relative w-full sm:w-72">
            <Search
              size={17}
              className="absolute left-3 top-3 text-slate-400"
            />
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Buscar ciudad..."
              className="w-full rounded-xl border border-slate-300 py-2.5 pl-10 pr-3 text-sm outline-none focus:border-violet-500"
            />
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full min-w-[500px] text-left text-sm">
            <thead className="bg-slate-100 text-slate-600">
              <tr>
                <th className="px-5 py-3">Ciudad</th>
                <th className="px-5 py-3">Dispositivos</th>
                <th className="px-5 py-3">Participación</th>
              </tr>
            </thead>

            <tbody>
              {filtered.map((city, index) => {
                const percent =
                  totalDevices > 0
                    ? (city.cantidad / totalDevices) * 100
                    : 0;

                return (
                  <tr
                    key={`${city.nombre}-${index}`}
                    className="border-t border-slate-100"
                  >
                    <td className="px-5 py-4 font-semibold text-slate-800">
                      {city.nombre || "Sin especificar"}
                    </td>

                    <td className="px-5 py-4 text-slate-700">
                      {city.cantidad}
                    </td>

                    <td className="px-5 py-4">
                      <div className="flex items-center gap-3">
                        <div className="h-2 w-28 overflow-hidden rounded-full bg-slate-200">
                          <div
                            className="h-full rounded-full bg-violet-600"
                            style={{ width: `${percent}%` }}
                          />
                        </div>
                        <span className="text-xs text-slate-600">
                          {percent.toFixed(1)}%
                        </span>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {!loading && filtered.length === 0 && (
          <p className="p-8 text-center text-sm text-slate-500">
            No se encontraron ciudades.
          </p>
        )}
      </section>
    </div>
  );
}