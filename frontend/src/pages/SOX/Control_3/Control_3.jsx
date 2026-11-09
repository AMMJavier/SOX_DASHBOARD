
import ControlWorkspace from "../../../components/SOX/common/ControlWorkspace";

const config = {
  number: 3,
  title: "Revisión del cumplimiento del Plan",
  description: "Seguimiento semestral de las actividades y objetivos del Plan de Seguridad de firewalls elaborado y aprobado en el control 2.",
  frequency: "Semestral",
  responsible: "Jefe de Infraestructura TI · Ingeniero Líder de Infraestructura TI",
  period: "semester",
  linkedControl: 2,
  activity: "El Jefe de Infraestructura TI contrasta semestralmente las actividades ejecutadas con las programadas en el Plan de Seguridad, revisa los avances con el equipo y aprueba los objetivos cumplidos.",
  steps: [
    "Identificar el Plan de Seguridad anual aprobado en el control 2.",
    "Convocar la reunión semestral de revisión con el equipo.",
    "Comparar actividades programadas versus ejecución y documentar los objetivos alcanzados.",
    "Registrar observaciones, recomendaciones o acciones pendientes.",
    "Conservar los avances y el correo de Jefatura que aprueba los objetivos cumplidos.",
  ],
  evidence: [
    { key: "avance", label: "Matriz / informe de avances", help: "Comparación de planificado contra ejecutado." },
    { key: "reunion", label: "Acta o soporte de reunión", help: "Soporte de la revisión semestral con el equipo." },
    { key: "aprobacion", label: "Aprobación de Jefatura", help: "Correo que valida los objetivos cumplidos y observaciones." },
    { key: "referencia", label: "Referencia al Plan de Seguridad", help: "Debe enlazarse a la versión del control 2, sin duplicarla innecesariamente." },
  ],
  rules: [
    "Se gestiona un expediente por semestre y año.",
    "La revisión debe estar asociada al plan aprobado en control 2.",
    "La reunión no equivale automáticamente a la aprobación de Jefatura.",
    "El recordatorio del segundo corte debe incluir la última versión de seguimiento disponible.",
  ],
  reminders: [
    "Programar un correo previo a cada reunión de revisión semestral.",
    "En el segundo corte, adjuntar o enlazar la versión anterior de los avances.",
    "Alertar antes de cada fecha límite cuando falten evidencia y aprobación.",
  ],
  openItems: [
    "Confirmar fechas de ambos semestres (la reunión mencionó enero y octubre/noviembre, sin acuerdo definitivo).",
    "Definir plazo de carga tras cada reunión y fecha del correo de aprobación.",
    "Precisar las columnas de la matriz de seguimiento.",
  ],
};

export default function Control_3() { return <ControlWorkspace config={config}/>; }