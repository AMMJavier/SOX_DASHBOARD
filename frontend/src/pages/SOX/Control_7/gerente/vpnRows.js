/** Filas comunes del panel del gerente: VPN externas (Check Point) e internas (LDAP). */

// Opciones del gerente. "No pertenece" ya no se ofrece; solo se muestra si una VPN ya se guardó así.
export const DECISIONS = ["Mantener", "Eliminar", "Otro"];
export const CONFIRMED = "confirmada";
export const REPORTED = "reportada"; // Otro / No pertenece: pendiente, en manos del administrador
export const PENDING = "pendiente";
export const SCOPES = {
  externas: { title: "VPN externas", lower: "VPN externas" },
  internas: { title: "VPN internas", lower: "VPN internas" },
};

const INTERNAL_LABEL = { mantener: "Mantener", eliminar: "Eliminar", "no pertenece": "No pertenece", otro: "Otro" };

/** Estado con el que queda una fila según la decisión guardada. */
export const statusFor = (decision) => (["Otro", "No pertenece"].includes(decision) ? REPORTED : CONFIRMED);

export function externalRow(x) {
  return {
    id: x.id, cells: [x.req, x.nombre_vpn || "-", x.solicitante || "-", x.manager],
    decision: x.decision || "", observation: x.observation || "",
    status: x.confirmed === 1 ? CONFIRMED : x.reported ? REPORTED : PENDING,
  };
}

export function internalRow(x) {
  const reported = ["otro", "no pertenece"].includes(x.estado);
  const status = x.confirmacion === 1 ? CONFIRMED : reported ? REPORTED : PENDING;
  return {
    id: x.id, cells: [x.usuario, x.nombre || "-", x.tipo_acceso === "RDP" ? "RDP" : "Aplicaciones"],
    director: !!x.director, // vista del aprobador de directores: cuadro directores o colaboradores
    note: x.activo_ad === 0 ? "Deshabilitada en AD" : "",
    // Interna pendiente: sin decisión elegida, el gerente la marca una por una.
    decision: status === PENDING ? "" : INTERNAL_LABEL[x.estado] || "", observation: x.observacion || "", status,
  };
}

export const needsObservation = (r) => r.decision === "Otro" && !r.observation.trim();

/** Qué se guardaría del cuadro: pendientes con decisión; y cuántas faltan por decidir. */
export function summarize(rows) {
  const pending = rows.filter((r) => r.status === PENDING);
  const toSave = pending.filter((r) => r.decision);
  return {
    pending: pending.length, toSave, undecided: pending.length - toSave.length,
    invalid: toSave.filter(needsObservation),
    reported: toSave.filter((r) => statusFor(r.decision) === REPORTED).length,
  };
}

/** Plan del guardado masivo: solo los cuadros con interacción. */
export function buildPlan(boxes, touched) {
  const plan = { scopes: [], missing: [], invalid: [] };
  for (const key of Object.keys(SCOPES)) {
    const s = summarize(boxes[key]);
    if (touched[key] && s.toSave.length) {
      plan.scopes.push({ key, ...s });
      plan.invalid.push(...s.invalid.map((r) => ({ key, name: r.cells[1] !== "-" ? r.cells[1] : r.cells[0] })));
      if (s.undecided) plan.missing.push({ key, count: s.undecided });
    } else if (s.pending) {
      plan.missing.push({ key, count: s.pending });
    }
  }
  return plan;
}
