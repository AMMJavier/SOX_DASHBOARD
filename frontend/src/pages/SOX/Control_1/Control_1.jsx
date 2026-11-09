
import ControlWorkspace from "../../../components/SOX/common/ControlWorkspace";

const config = {
  number: 1,
  title: "Revisión del procedimiento SIS016",
  description: 'Control documental del procedimiento SIS016 "Control de Accesos en el Firewall", su vigencia y su aprobación por la Gerencia de Infraestructura TI.',
  frequency: "Anual · actualizaciones durante el año",
  responsible: "Jefe de Infraestructura TI · Gerencia de Infraestructura TI",
  period: "year",
  activity: "El Jefe de Infraestructura TI revisa que el procedimiento SIS016 se ajuste a las políticas de seguridad de CONECEL, gestiona las actualizaciones necesarias y obtiene su aprobación por Gerencia.",
  steps: [
    "Revisar SIS016 y verificar la alineación con las políticas de seguridad.",
    "Determinar si el procedimiento requiere modificación o permanece vigente.",
    "Si hay cambios, conservar el correo de solicitud de actualización y la aprobación gerencial.",
    "Si no hay cambios, conservar el correo que confirme que el procedimiento se mantiene.",
    "Mantener disponibles las versiones del año y presentar la evidencia aplicable cuando se solicite.",
  ],
  evidence: [
    { key: "revision", label: "Correo de revisión / sin cambios", help: "Confirma la vigencia cuando no hay actualizaciones." },
    { key: "solicitud", label: "Solicitud de actualización", help: "Correo al área responsable del proceso, cuando se modifica el procedimiento." },
    { key: "aprobacion", label: "Aprobación de Gerencia", help: "Correo con la aprobación formal de las modificaciones." },
    { key: "sis016", label: "Procedimiento SIS016", help: "Versión del documento revisado o aprobado." },
  ],
  rules: [
    "Existe una sola obligación anual, no dos campañas semestrales.",
    "Pueden existir varias evidencias y versiones dentro de un mismo año.",
    "Subir un archivo no equivale a que haya sido formalmente aprobado.",
    "Auditoría recibe la evidencia exportada; no se presupone acceso directo a esta plataforma.",
  ],
  reminders: [
    "Recordatorio preventivo a mitad de año (propuesta expresada en la reunión).",
    "Segundo recordatorio alrededor de noviembre (propuesta; no es fecha oficial).",
    "Aviso próximo al vencimiento si falta la evidencia requerida.",
  ],
  openItems: [
    "Confirmar nomenclatura documental: SIS016 en el Excel, SISERA16 en la transcripción.",
    "Definir fecha de cierre anual y responsables de las notificaciones.",
    "Definir qué evidencia cierra el año cuando hubo varias modificaciones.",
  ],
};

export default function Control_1() { return <ControlWorkspace config={config}/>; }
