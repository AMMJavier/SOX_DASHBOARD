import { useEffect, useState } from "react";
import { Save } from "lucide-react";
import { confirmAllValidations, getMyValidations, updateValidation } from "../../../services/sox/control_7/validationService";
import { getCampaignStatus } from "../../../services/sox/control_7/campaignService";
import {
  confirmAllInternal, errorText, getMyInternalAccounts, saveInternalDecision,
} from "../../../services/sox/control_7/internalVpnService";
import SaveAllModal, { SaveOneModal } from "./gerente/SaveAllModal";
import VpnBox from "./gerente/VpnBox";
import { PENDING, SCOPES, buildPlan, externalRow, internalRow, needsObservation, statusFor } from "./gerente/vpnRows";

const SEMAPHORE = {
  verde: { color: "bg-green-500", text: "En plazo" },
  amarillo: { color: "bg-yellow-400", text: "Próximo a vencer" },
  rojo: { color: "bg-red-500", text: "Tiempo agotado" },
};

// Cómo se lee y se guarda cada cuadro.
const API = {
  externas: {
    load: async () => ((await getMyValidations()).items || []).map(externalRow),
    saveOne: (r) => updateValidation(r.id, { decision: r.decision, observation: r.observation }),
    saveAll: (rows) => confirmAllValidations({
      validations: rows.map((r) => ({ checkpoint_uid: r.id, decision: r.decision, observation: r.observation })),
    }),
  },
  internas: {
    load: async () => ((await getMyInternalAccounts()).items || []).map(internalRow),
    saveOne: (r) => saveInternalDecision(r.id, { decision: r.decision, observation: r.observation }),
    saveAll: (rows) => confirmAllInternal(rows.map((r) => ({ id: r.id, decision: r.decision, observation: r.observation }))),
  },
};
const KEYS = Object.keys(SCOPES);
const EMPTY = { rows: [], loading: true, error: "" };

/** Panel del gerente: SUS VPN externas e internas en una sola página. */
export default function ManagerDashboard() {
  const [boxes, setBoxes] = useState({ externas: EMPTY, internas: EMPTY });
  const [touched, setTouched] = useState({ externas: false, internas: false });
  const [campaign, setCampaign] = useState(null);
  const [plan, setPlan] = useState(null);
  const [confirmOne, setConfirmOne] = useState(null); // { key, row } a la espera de Aceptar / Cancelar
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState(null);

  const setBox = (key, patch) => setBoxes((b) => ({ ...b, [key]: { ...b[key], ...patch } }));
  const setRows = (key, update) => setBoxes((b) => ({ ...b, [key]: { ...b[key], rows: update(b[key].rows) } }));

  async function load(key) {
    try { setBox(key, { rows: await API[key].load(), loading: false, error: "" }); }
    catch (e) { setBox(key, { loading: false, error: errorText(e, `No se pudieron cargar tus ${SCOPES[key].lower}.`) }); }
  }

  useEffect(() => {
    KEYS.forEach(load);
    getCampaignStatus().then(setCampaign).catch((e) => console.error("Estado de campaña:", e));
  }, []);

  const expired = !!campaign?.expired;
  const semaphore = SEMAPHORE[campaign?.semaforo];
  const rowsByScope = { externas: boxes.externas.rows, internas: boxes.internas.rows };
  // Sin VPN por validar en ningún cuadro (ya cargados): "Guardar todas" se deshabilita.
  const allSaved = KEYS.every((k) => !boxes[k].loading && !boxes[k].error)
    && KEYS.every((k) => !boxes[k].rows.some((r) => r.status === PENDING));

  // Un cuadro sin VPN asignadas no se muestra (mientras carga o si falló, sí).
  const shown = (key) => boxes[key].loading || !!boxes[key].error || boxes[key].rows.length > 0;

  const change = (key) => (id, field, value) => setRows(key, (rows) => rows.map((r) => (
    r.id !== id ? r : { ...r, [field]: value, ...(field === "decision" && value !== "Otro" ? { observation: "" } : {}) })));
  const touch = (key) => () => setTouched((t) => (t[key] ? t : { ...t, [key]: true }));
  const markSaved = (key, ids) => setRows(key, (rows) => rows.map((r) => (
    ids.includes(r.id) ? { ...r, status: statusFor(r.decision) } : r)));

  // Guardado individual: primero se valida y se pide confirmación; guarda solo con "Aceptar".
  const saveOne = (key) => (row) => {
    if (!row.decision) { setFeedback({ error: true, text: "Debe seleccionar una decisión antes de guardar." }); return; }
    if (needsObservation(row)) { setFeedback({ error: true, text: "Debe ingresar una observación cuando seleccione \"Otro\"." }); return; }
    setFeedback(null); setConfirmOne({ key, row });
  };

  async function confirmSaveOne() {
    const { key, row } = confirmOne;
    setBusy(true); setFeedback(null);
    try {
      await API[key].saveOne(row);
      markSaved(key, [row.id]);
      setFeedback({ error: false, text: statusFor(row.decision) === "reportada"
        ? `Guardada. La VPN queda pendiente hasta que el administrador la revise ("${row.decision}").`
        : "Validación guardada correctamente." });
    } catch (e) { setFeedback({ error: true, text: errorText(e, "No se pudo guardar la validación.") }); }
    finally { setBusy(false); setConfirmOne(null); }
  }

  async function saveAll() {
    setBusy(true); setFeedback(null);
    const done = [], failed = [];
    for (const scope of plan.scopes) { // Cada cuadro se guarda por separado: si uno falla, el otro queda guardado.
      try {
        const r = await API[scope.key].saveAll(scope.toSave);
        const ids = r.guardadas || [];
        markSaved(scope.key, ids);
        setTouched((t) => ({ ...t, [scope.key]: false }));
        const skipped = scope.toSave.length - ids.length;
        done.push(`${SCOPES[scope.key].title}: ${ids.length} guardada(s)${skipped ? `, ${skipped} no se guardaron porque ya estaban respondidas o cambiaron` : ""}`);
        if (skipped) await load(scope.key);
      } catch (e) { failed.push(`${SCOPES[scope.key].title}: ${errorText(e, "no se pudieron guardar")}`); }
    }
    const missing = plan.missing.map((m) => `faltan ${m.count} de ${SCOPES[m.key].lower}`);
    setFeedback({ error: failed.length > 0, text: [...done, ...failed, ...missing].join(" · ") });
    setPlan(null); setBusy(false);
  }

  return (
    <div>
      <h1 className="text-2xl font-bold">Dashboard Gerente</h1>
      <p className="mt-1 text-slate-500">Valida tus VPN externas e internas de la campaña activa.</p>

      <div className="mt-6 rounded-2xl border border-amber-200 bg-amber-50 p-5">
        <h3 className="text-base font-bold text-amber-800">Instrucciones para la validación</h3>
        <ul className="mt-3 list-disc space-y-2 pl-5 text-sm text-amber-700">
          <li>Solo ves las VPN asignadas a tu usuario: las <b className="text-sky-700">externas</b> en el cuadro azul y las <b className="text-violet-700">internas</b> en el cuadro violeta.</li>
          <li>En la columna <b>Decisión</b>, seleccione una opción: Mantener, Eliminar u Otro.</li>
          <li>Con la opción <b>Otro</b>, el campo <b>Observación</b> se pone en blanco: escriba el motivo (es obligatorio).</li>
          <li>Con <b>Otro</b> la VPN queda <b>pendiente</b> hasta que el administrador la revise.</li>
          <li>Una vez guardada la decisión <b>no se puede cambiar</b>.</li>
          <li><b>Guardar todas</b> guarda solo el cuadro en el que trabajaste.</li>
        </ul>
      </div>

      {campaign?.active && <div className="mt-6 flex items-center gap-3 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <span className={`h-4 w-4 shrink-0 rounded-full ${semaphore?.color || "bg-slate-300"}`}/>
        <div>
          <p className="font-bold">Estado de campaña: {semaphore?.text || "-"}</p>
          <p className="text-sm text-slate-500">Fecha límite: {campaign.fecha_limite} ({Math.max(campaign.dias_restantes, 0)} días restantes)</p>
        </div>
      </div>}
      {campaign && !campaign.active && <p className="mt-6 rounded-2xl bg-amber-50 p-5 text-sm text-amber-800">No hay una campaña activa.</p>}

      {shown("externas") && <VpnBox tone="externas" title="Cliente VPN Externos" headers={["VPN", "Nombre VPN", "Solicitante", "Gerente Asignado"]} {...boxes.externas}
        expired={expired} busy={busy} deadline={campaign?.fecha_limite} emptyText="No tienes VPN externas asignadas a tu usuario en esta campaña."
        onChange={change("externas")} onSave={saveOne("externas")} onTouch={touch("externas")}/>}

      {shown("internas") && <VpnBox tone="internas" title="VPN Internas" headers={["Cuenta", "Nombre", "Acceso"]} {...boxes.internas}
        expired={expired} busy={busy} deadline={campaign?.fecha_limite} emptyText="No tienes cuentas con VPN interna a cargo en esta campaña."
        onChange={change("internas")} onSave={saveOne("internas")} onTouch={touch("internas")}/>}

      {!KEYS.some(shown) && <p className="mt-6 rounded-2xl border border-slate-200 bg-white p-8 text-center text-slate-500 shadow-sm">
        No tienes VPN externas ni internas asignadas a tu usuario en esta campaña.</p>}

      <div className="sticky bottom-4 z-10 mt-6 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-lg">
        <p className={`text-sm ${feedback ? (feedback.error ? "font-semibold text-red-700" : "font-semibold text-emerald-700") : "text-slate-500"}`} role="status">
          {feedback?.text || (allSaved ? "Ya guardaste todas tus VPN de esta campaña." : "Guardar todas guarda solo el cuadro en el que trabajaste (externas, internas o ambos).")}</p>
        <button type="button" disabled={expired || busy || !campaign?.active || allSaved} onClick={() => { setFeedback(null); setPlan(buildPlan(rowsByScope, touched)); }}
          className="flex items-center gap-2 rounded-lg bg-amber-500 px-5 py-2 font-bold text-white hover:bg-amber-600 disabled:cursor-not-allowed disabled:bg-slate-400">
          <Save size={16}/>{expired ? "Campaña cerrada" : allSaved ? "Todas guardadas" : "Guardar todas"}</button>
      </div>

      {plan && <SaveAllModal plan={plan} touchedAny={touched.externas || touched.internas} busy={busy}
        onClose={() => setPlan(null)} onConfirm={saveAll}/>}
      {confirmOne && <SaveOneModal row={confirmOne.row} scopeTitle={confirmOne.key === "externas" ? "VPN externa" : "Cuenta interna"} busy={busy}
        onClose={() => setConfirmOne(null)} onConfirm={confirmSaveOne}/>}
    </div>
  );
}
