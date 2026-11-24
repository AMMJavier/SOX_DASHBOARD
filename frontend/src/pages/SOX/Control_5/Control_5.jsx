
import ControlWorkspace from "../../../components/SOX/common/ControlWorkspace";

const config = {
  number: 5,
  title: "Modificaciones de administradores Firewall",
  description: "Aprobación, por parte de Jefatura, de la lista de administradores de las plataformas de seguridad (firewalls).",
  frequency: "Por definir (sin envío automático)",
  responsible: "Líder de Seguridad Operativa y Redes · Jefe de Seguridad Operacional y Redes",
  period: "year",
  activity: "El Líder de Seguridad Operativa y Redes realiza los cambios de perfiles de administración de firewalls únicamente sobre la base de la aprobación del Jefe de Seguridad Operacional y Redes. Para ello envía por correo la lista de administradores de las plataformas de seguridad y el Jefe responde con su OK, que queda como evidencia.",
  steps: [],
  evidence: [
    { key: "solicitud", label: "Correo con la lista de administradores", help: "Correo enviado al Jefe de Seguridad Operacional y Redes con la lista adjunta." },
    { key: "aprobacion", label: "Respuesta con el OK de Jefatura", help: "Respuesta del Jefe de Seguridad Operacional y Redes aprobando la lista." },
    { key: "ejecucion", label: "Soporte adicional", help: "Otro respaldo del cambio, sin divulgar contraseñas ni secretos." },
  ],
  rules: [
    "El correo se envía desde SOX con el código 005 en el asunto; la respuesta debe conservar ese asunto.",
    "La respuesta con \"OK\", \"Okay\" o \"Aprobado\" deja el correo en verde (Aprobado).",
    "Se puede descargar tanto el correo enviado como la respuesta con sus adjuntos.",
  ],
  reminders: [
    "Sin recordatorios automáticos por ahora (pendiente de definir la frecuencia).",
  ],
  openItems: [
    "Definir la frecuencia del correo y las fechas de recordatorio.",
    "Agregar el texto de la evidencia del control según el Excel SOIT.",
  ],
};

export default function Control_5() { return <ControlWorkspace config={config}/>; }
