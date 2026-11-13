"""Recordatorios SOX por control mediante el script corporativo Microsoft Graph.

Sin envios automaticos: administracion solicita previsualizacion y confirma cada envio.
No almacena credenciales en el proyecto ni acepta destinatarios arbitrarios del cliente.
"""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

from fastapi import HTTPException

CONTROLS = frozenset({1, 2, 3, 5, 6})
EMAIL_RE = re.compile(r"^[^@\s,;]+@[^@\s,;]+\.[^@\s,;]+$")

TEMPLATES = {
    1: (
        "SOX Control 1 - Evidencia anual del procedimiento SIS016",
        "Se solicita revisar la vigencia del procedimiento SIS016 y conservar los correos de "
        "solicitud/actualizacion y aprobacion de Gerencia, o el correo que confirme que no "
        "hubo cambios. El control se cierra anualmente; pueden existir varias versiones."
    ),
    2: (
        "SOX Control 2 - Plan de Seguridad anual",
        "Se solicita elaborar o revisar el Plan de Seguridad anual de firewalls, gestionar "
        "su aprobacion por Gerencia y cargar el plan y el correo de aprobacion en el expediente anual."
    ),
    3: (
        "SOX Control 3 - Seguimiento semestral del Plan de Seguridad",
        "Se solicita realizar la revision semestral del avance del plan aprobado en Control 2, "
        "documentar la reunion y cargar el correo o respaldo de la aprobacion de Jefatura."
    ),
    5: (
        "SOX Control 5 - Evidencias de cambios de administradores firewall",
        "Se recuerda registrar cada alta, modificacion o baja de administradores como "
        "un evento independiente con su autorizacion y evidencia de ejecucion. "
        "El consolidado no reemplaza los respaldos por evento."
    ),
    6: (
        "SOX Control 6 - Conciliacion de cesantes y accesos VPN internos",
        "Se solicita conciliar la fuente autorizada de RR. HH. con los listados internos "
        "LDAP/RDP/aplicaciones y SASE. Los hallazgos requieren verificacion antes de realizar bajas. "
        "Conservar evidencias y comunicar resultados a la jefatura correspondiente."
    ),
}


def _recipients(control: int):
    raw = os.getenv(f"SOX_REMINDER_TO_{control}", "")
    recipients = [s.strip() for s in re.split(r"[,;]", raw) if s.strip()]
    if not recipients or len(recipients) > 15 or not all(EMAIL_RE.fullmatch(x) for x in recipients):
        raise HTTPException(503, f"Destinatarios no configurados correctamente para Control {control}")
    if len({x.casefold() for x in recipients}) != len(recipients):
        raise HTTPException(503, "La lista de destinatarios contiene duplicados")
    return recipients


def compose(control, anio, semestre=None, referencia=""):
    if control not in CONTROLS:
        raise HTTPException(404, "El control no dispone de recordatorios")
    if not 2020 <= anio <= 2100:
        raise HTTPException(422, "Año fuera de rango")
    if semestre is not None and semestre not in (1, 2):
        raise HTTPException(422, "Semestre inválido")
    if control in (1, 2, 5) and semestre is not None:
        raise HTTPException(422, "Este control no utiliza semestre para el recordatorio")
    if control in (3, 6) and semestre is None:
        raise HTTPException(422, "Indica el semestre del recordatorio")
    if len(referencia) > 150 or any(ord(x) < 32 for x in referencia):
        raise HTTPException(422, "Referencia inválida")
    sender = os.getenv("SOX_MAIL_SENDER", "").strip()
    if not EMAIL_RE.fullmatch(sender):
        raise HTTPException(503, "SOX_MAIL_SENDER no está configurado")
    recipients = _recipients(control)
    title, detail = TEMPLATES[control]
    subject = f"{title} | {anio}" + (f" | S{semestre}" if semestre else "")
    text = (
        "Estimados:\n\n" + detail +
        f"\n\nPeríodo: {anio}" + (f", semestre {semestre}" if semestre else "") +
        (f"\nReferencia interna: {referencia.strip()}" if referencia.strip() else "") +
        "\n\nEste mensaje es un recordatorio operativo; no constituye aprobación formal. "
        "Los documentos de respaldo se consultan en el repositorio privado SOX. "
        "No se adjuntan automáticamente archivos.\n\nSaludos."
    )
    return {"emisor": sender, "destinatarios": recipients, "asunto": subject,
            "cuerpo": text, "formato": "texto"}


def send_via_graph(message):
    if os.getenv("SOX_MAIL_ENABLED", "false").strip().lower() != "true":
        raise HTTPException(503, "Envío SOX desactivado. Falta aprobación/configuración")
    script = Path(os.getenv("SOX_GRAPH_SCRIPT", "/data/sisauto/buzon_prciaut/buzon_prciaut.py"))
    python = Path(os.getenv("SOX_GRAPH_PYTHON", sys.executable))
    creds = os.getenv("SOX_GRAPH_CREDENTIALS", "").strip()
    if not script.is_absolute() or not script.is_file() or not python.is_absolute() or not python.is_file():
        raise HTTPException(503, "Script o intérprete Graph no disponibles en el servidor")
    args = [str(python), str(script), "-m"]
    if creds:
        cp = Path(creds)
        if not cp.is_absolute() or not cp.is_file():
            raise HTTPException(503, "Ruta de credenciales Graph no válida")
    # Archivo temporal con permisos de lectura restringidos, en vez de JSON de la línea de comandos.
    msg_path = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", prefix="sox_graph_", suffix=".json",
                                     delete=False) as handle:
            os.chmod(handle.name, 0o600)
            json.dump(message, handle, ensure_ascii=False)
            msg_path = handle.name
        command = args + [msg_path]
        if creds:
            command += ["-c", creds]
        try:
            proc = subprocess.run(command, shell=False, capture_output=True, text=True,
                                  timeout=90, check=False)
        except subprocess.TimeoutExpired:
            raise HTTPException(504, "Graph no respondió dentro del tiempo permitido; confirmar entrega antes de reintentar")
        if proc.returncode != 0:
            # No devolver stderr: podría incluir detalles personales/operativos.
            raise HTTPException(502, "Microsoft Graph no confirmó el envío. Revisar registros restringidos del servidor")
        return {"aceptado_graph": True, "fecha_utc": datetime.now(timezone.utc).isoformat()}
    finally:
        if msg_path:
            Path(msg_path).unlink(missing_ok=True)
