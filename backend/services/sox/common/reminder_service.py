"""Notificaciones / recordatorios SOX por control (Microsoft Graph corporativo).

Sin envíos automáticos: un administrador previsualiza y confirma cada envío.
Destinatarios, copias y textos vienen de backend/config/correos.json
(controles.<n>.notificacion); el cliente no puede enviar destinatarios ni plantillas.
El envío usa el mismo worker que el correo formal (scripts/sox_graph_mail.py).
"""
import subprocess

from fastapi import HTTPException

from services.sox.common import mail_config
from services.sox.common import mail_service as mail

MAX_RECIPIENTS = 15

# Textos por defecto si correos.json no define la notificación del control.
DEFAULTS = {
    1: ("SOX Control 1 - Evidencia anual del procedimiento SIS016 | {anio}",
        "Se solicita revisar la vigencia del procedimiento SIS016 y conservar los correos de "
        "solicitud/actualizacion y aprobacion de Gerencia, o el correo que confirme que no "
        "hubo cambios. El control se cierra anualmente; pueden existir varias versiones."),
    2: ("SOX Control 2 - Plan de Seguridad anual | {anio}",
        "Se solicita elaborar o revisar el Plan de Seguridad anual de firewalls, gestionar "
        "su aprobacion por Gerencia y cargar el plan y el correo de aprobacion en el expediente anual."),
    3: ("SOX Control 3 - Seguimiento semestral del Plan de Seguridad | {anio} | S{semestre}",
        "Se solicita realizar la revision semestral del avance del plan aprobado en Control 2, "
        "documentar la reunion y cargar el correo o respaldo de la aprobacion de Jefatura."),
    5: ("SOX Control 5 - Evidencias de cambios de administradores firewall | {anio}",
        "Se recuerda registrar cada alta, modificacion o baja de administradores como "
        "un evento independiente con su autorizacion y evidencia de ejecucion. "
        "El consolidado no reemplaza los respaldos por evento."),
    6: ("SOX Control 6 - Conciliacion de cesantes y accesos VPN internos | {anio} | S{semestre}",
        "Se solicita conciliar la fuente autorizada de RR. HH. con los listados internos "
        "LDAP/RDP/aplicaciones y SASE. Los hallazgos requieren verificacion antes de realizar bajas. "
        "Conservar evidencias y comunicar resultados a la jefatura correspondiente."),
}
BODY_FRAME = (
    "Estimados:\n\n{detalle}\n\nPeríodo: {periodo}{referencia_linea}\n\n"
    "Este mensaje es un recordatorio operativo; no constituye aprobación formal. "
    "Los documentos de respaldo se consultan en el repositorio privado SOX. "
    "No se adjuntan automáticamente archivos.\n\nSaludos."
)
SEMESTER_CONTROLS = {3, 6}


def controls():
    return set(DEFAULTS) | mail_config.notification_controls()


def compose(control, anio, semestre=None, referencia=""):
    if control not in controls():
        raise HTTPException(404, "El control no dispone de notificaciones")
    if not 2020 <= anio <= 2100:
        raise HTTPException(422, "Año fuera de rango")
    if semestre is not None and semestre not in (1, 2):
        raise HTTPException(422, "Semestre inválido")
    if control in SEMESTER_CONTROLS and semestre is None:
        raise HTTPException(422, "Indica el semestre del recordatorio")
    if control not in SEMESTER_CONTROLS:
        semestre = None
    if len(referencia) > 150 or any(ord(x) < 32 for x in referencia):
        raise HTTPException(422, "Referencia inválida")

    emisor = mail.sender()
    if not emisor:
        raise HTTPException(503, "No hay remitente válido (correos.json > remitente)")
    config = mail_config.notification(control)
    recipients = config["destinatarios"]
    if not recipients:
        raise HTTPException(503, f"Sin destinatarios para el Control {control} (correos.json > controles.{control}.notificacion.destinatarios)")
    if len(recipients) > MAX_RECIPIENTS:
        raise HTTPException(503, f"Máximo {MAX_RECIPIENTS} destinatarios por notificación")
    recipients = mail.parse_addresses(";".join(recipients), f"destinatarios del Control {control}", True)
    taken = {x.casefold() for x in recipients}
    copies = [x for x in mail.fixed_cc(control) if x.casefold() not in taken]

    referencia = referencia.strip()
    values = {
        "control": control, "anio": anio, "semestre": semestre or "",
        "periodo": f"{anio}" + (f", semestre {semestre}" if semestre else ""),
        "referencia": referencia,
        "referencia_linea": f"\nReferencia interna: {referencia}" if referencia else "",
    }
    default_subject, default_detail = DEFAULTS.get(control, (f"SOX Control {control} | {{anio}}", ""))
    subject = mail_config.render(config["asunto"] or default_subject, **values)
    if config["cuerpo"]:
        body = mail_config.render(config["cuerpo"], **values)
    else:
        body = mail_config.render(BODY_FRAME, detalle=default_detail, **values)
    subject = " ".join(subject.split())[:mail.MAX_SUBJECT]
    return {"emisor": emisor, "destinatarios": recipients, "cc": copies,
            "asunto": subject, "cuerpo": body.strip(), "formato": "texto"}


def send_via_graph(message, correlation):
    """Envía con el worker Graph. Devuelve (ok, detalle, internet_message_id)."""
    if not mail._env_bool("SOX_MAIL_ENABLED"):
        raise HTTPException(503, "Envíos deshabilitados: configurar SOX_MAIL_ENABLED=true tras autorización")
    payload = {**message, "correlacion": correlation, "adjuntos": []}
    try:
        code, out = mail._run_worker("enviar", payload, timeout=120)
    except subprocess.TimeoutExpired:
        return None, "Graph no respondió a tiempo. Verificar en Elementos enviados antes de reenviar.", None
    if code != 0 or not out.get("ok"):
        return False, "Microsoft Graph no aceptó el envío", None
    return True, None, out.get("internet_message_id")
