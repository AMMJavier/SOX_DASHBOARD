

import ControlWorkspace from "../../../components/SOX/common/ControlWorkspace";

const config = {
  number: 2,
  title: "Plan de Seguridad de Firewalls",
  description: "Elaboración del Plan de Seguridad anual de los elementos perimetrales, revisión por Jefatura y aprobación por Gerencia de Infraestructura TI.",
  frequency: "Anual",
  responsible: "Ingeniero Líder de Network · Jefe de Infraestructura TI · Gerencia de Infraestructura TI",
  period: "year",
  activity: "El Ingeniero Líder de Network elabora cada año el Plan de Seguridad de firewalls. El Jefe de Infraestructura TI lo revisa y la Gerencia de Infraestructura TI aprueba el plan por correo si satisface las necesidades del negocio.",
  steps: [
    "Obtener el plan de referencia del año anterior o la plantilla vigente.",
    "Elaborar el nuevo Plan de Seguridad de firewalls.",
    "Enviar el documento a Jefatura para revisión.",
    "Gestionar la aprobación de Gerencia mediante correo electrónico.",
    "Conservar el documento final y la aprobación en un único expediente anual.",
  ],
  evidence: [
    { key: "plan", label: "Plan de Seguridad anual", help: "Documento vigente aprobado para el año del control." },
    { key: "revision", label: "Revisión de Jefatura", help: "Correo de revisión y observaciones, si existen." },
    { key: "aprobacion", label: "Correo de aprobación gerencial", help: "Evidencia indispensable para acreditar la aprobación." },
  ],
  rules: [
    "El control 2 acredita la elaboración y aprobación anual del plan.",
    "La revisión de avances no se gestiona aquí, sino en el control 3.",
    "El plan aprobado sirve como referencia para el seguimiento semestral.",
    "No generar dos obligaciones por año, aunque exista seguimiento en ambos semestres.",
  ],
  reminders: [
    "Correo de inicio de año solicitando la elaboración del plan y adjuntando el modelo de referencia.",
    "Aviso previo a la fecha máxima de aprobación si falta el documento o el correo gerencial.",
    "La actualización y seguimiento posteriores corresponden al control 3.",
  ],
  openItems: [
    "Confirmar fecha anual de entrega y aprobación del Plan de Seguridad.",
    "Precisar dónde se almacenará la plantilla y cómo se identificará la versión oficial.",
    "Definir destinatarios del correo de recordatorio.",
  ],
};

export default function Control_2() { return <ControlWorkspace config={config}/>; }