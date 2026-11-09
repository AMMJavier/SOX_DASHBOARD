
import ControlWorkspace from "../../../components/SOX/common/ControlWorkspace";

const config = {
  number: 5,
  title: "Modificaciones de administradores Firewall",
  description: "Trazabilidad individual de altas, modificaciones y bajas de perfiles administradores, respaldadas por la autorización de Jefatura de Infraestructura TI.",
  frequency: "Por evento",
  responsible: "Ingeniero Líder de Infraestructura TI · Jefe de Infraestructura TI",
  period: "event",
  activity: "El Ingeniero Líder de Infraestructura TI realiza cambios en perfiles de usuarios administradores de firewalls únicamente sobre la base de la aprobación del Jefe de Infraestructura TI por correo electrónico.",
  steps: [
    "Identificar la cuenta administradora, grupo afectado y tipo de operación.",
    "Obtener y conservar la aprobación correspondiente del Jefe de Infraestructura TI.",
    "Ejecutar el alta, modificación o baja autorizada en el firewall.",
    "Guardar el detalle y la evidencia por cada evento y cuenta afectada.",
    "Preparar un consolidado por periodo solo como evidencia complementaria.",
  ],
  evidence: [
    { key: "aprobacion", label: "Correo de aprobación individual", help: "Autorización de Jefatura asociada a cada cambio de administrador." },
    { key: "ejecucion", label: "Soporte de modificación ejecutada", help: "Datos del cambio en la consola, sin divulgar contraseñas ni secretos." },
    { key: "solicitud", label: "Solicitud o referencia del evento", help: "Correo o ticket relacionado con la operación." },
    { key: "consolidado", label: "Consolidado de cambios del periodo", help: "Opcional: no sustituye las aprobaciones individuales." },
  ],
  rules: [
    "Una evidencia por evento, aunque existan varios eventos para la misma cuenta.",
    "El correo de aprobación debe corresponder al cambio solicitado.",
    "Una captura consolidada semestral no reemplaza el expediente individual.",
    "Los registros de la cuenta y perfil se manejarán como información administrativa restringida.",
  ],
  reminders: [
    "Recordatorio periódico para comprobar que se hayan archivado todos los eventos del periodo.",
    "Alerta sobre eventos identificados sin aprobación o evidencia de ejecución.",
    "No se asumirá periodicidad semestral como sustituto de la obligación por evento.",
  ],
  openItems: [
    "Definir plazo máximo para registrar evidencia después de cada cambio.",
    "Definir fuente de eventos de firewall que permita verificar completitud.",
    "Definir nomenclatura para asociar correo, cuenta administradora y ticket de cambio.",
  ],
};

export default function Control_5() { return <ControlWorkspace config={config}/>; }
