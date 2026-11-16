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


ALERT_SUBJECT = "SOX Control {control} - ALERTA: falta evidencia | {periodo} | Fecha tope {fecha_tope}"
ALERT_BODY = (
    "Estimados:\n\n"
    "No se registra evidencia cargada en la plataforma SOX para el Control {control} en el período {periodo}.\n\n"
    "La fecha tope para subir la evidencia es el {fecha_tope} (faltan {dias_restantes} día(s)).\n\n"
    "Por favor, suban la evidencia correspondiente en el repositorio del control antes de esa fecha."
    "{referencia_linea}\n\nSaludos."
)


def latest_attachment(db, spec):
    """Último archivo subido en los controles/tipos indicados (correos.json > calendario.adjuntar_ultimo).

    Devuelve (nombre, contenido, ref) o None. Comprueba el SHA256 del archivo antes de adjuntarlo.
    """
    if not spec or db is None:
        return None
    from hashlib import sha256
    from sqlalchemy import text
    from routes.sox.common.evidence import _storage_root
    controls_list = [int(c) for c in spec["controles"]]
    params = {f"c{i}": c for i, c in enumerate(controls_list)}
    sql = ("SELECT ID AS \"id\", CONTROL_NUMERO AS \"control\", TIPO_EVIDENCIA AS \"tipo\", NOMBRE_ARCHIVO AS \"nombre\", "
           "ARCHIVO_KEY AS \"key\", SHA256 AS \"sha256\", CREADO_EN AS \"fecha\" FROM AUTOM.SOX_CONTROL_EVIDENCIAS "
           f"WHERE CONTROL_NUMERO IN ({', '.join(':' + k for k in params)}) AND ESTADO IN ('CARGADA', 'VERIFICADA')")
    if spec["tipos"]:
        tparams = {f"t{i}": t for i, t in enumerate(spec["tipos"])}
        sql += f" AND TIPO_EVIDENCIA IN ({', '.join(':' + k for k in tparams)})"
        params.update(tparams)
    sql += " ORDER BY CREADO_EN DESC, ID DESC FETCH FIRST 1 ROWS ONLY"
    row = db.execute(text(sql), params).mappings().first()
    if not row:
        return None
    path = _storage_root() / row["key"]
    if not path.is_file():
        raise HTTPException(503, f"Archivo físico no disponible para la evidencia #{row['id']}")
    content = path.read_bytes()
    if sha256(content).hexdigest() != row["sha256"]:
        raise HTTPException(503, f"La evidencia #{row['id']} no supera la comprobación de integridad")
    return row["nombre"], content, {"id": row["id"], "control": row["control"], "tipo": row["tipo"],
                                    "nombre": row["nombre"], "fecha": str(row["fecha"])[:19]}


def compose(control, anio, semestre=None, referencia="", *, db=None, kind="notificacion", extra=None):
    """Arma la notificación (kind="notificacion") o la alerta de evidencia faltante (kind="alerta")."""
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
        **(extra or {}),
    }
    if kind == "alerta":
        tpl = mail_config.alert_template(control)
        subject = mail_config.render(tpl["asunto"] or ALERT_SUBJECT, **values)
        body = mail_config.render(tpl["cuerpo"] or ALERT_BODY, **values)
    else:
        default_subject, default_detail = DEFAULTS.get(control, (f"SOX Control {control} | {{anio}}", ""))
        subject = mail_config.render(config["asunto"] or default_subject, **values)
        if config["cuerpo"]:
            body = mail_config.render(config["cuerpo"], **values)
        else:
            body = mail_config.render(BODY_FRAME, detalle=default_detail, **values)
    subject = " ".join(subject.split())[:mail.MAX_SUBJECT]

    # Adjunto: último archivo subido (p. ej. el plan del Control 2), si el calendario lo pide.
    attachments, refs = [], []
    spec = mail_config.calendar(control)["adjuntar_ultimo"]
    if spec:
        found = latest_attachment(db, spec)
        if found:
            name, content, ref = found
            attachments.append((name, content))
            refs.append(ref)
    return {"emisor": emisor, "destinatarios": recipients, "cc": copies,
            "asunto": subject, "cuerpo": body.strip(), "formato": "texto",
            "adjuntos": refs, "_archivos": attachments}


def public(message):
    """Mensaje sin el contenido binario de los adjuntos (para la vista previa / JSON)."""
    return {k: v for k, v in message.items() if not k.startswith("_")}


def deliver(db, *, control, anio, semestre, referencia, user_id, username, kind="notificacion",
            idempotency_key=None, extra=None):
    """Registra en SOX_MAIL_OUTBOX (ORIGEN='RECORDATORIO') y envía por Graph.

    La usan el botón "Enviar notificación" y el envío automático. Con idempotency_key
    fija (envío automático) un mismo recordatorio nunca se envía dos veces.
    Devuelve {"estado", "auditoria_id", "repetido"}.
    """
    import os
    import shutil
    import tempfile
    from uuid import uuid4
    from sqlalchemy import Integer, outparam, text
    from sqlalchemy.exc import IntegrityError

    message = compose(control, anio, semestre, referencia, db=db, kind=kind, extra=extra)
    if not mail._env_bool("SOX_MAIL_ENABLED"):
        raise HTTPException(503, "Envíos deshabilitados: configurar SOX_MAIL_ENABLED=true tras autorización")
    mail._graph_paths()  # Falla aquí, antes de registrar, si la integración no está instalada.
    files = mail._validate_attachments(message["_archivos"])

    correlation = uuid4().hex
    semestre = semestre if control in SEMESTER_CONTROLS else None
    idem = idempotency_key or f"N{control}-{correlation}"
    labels = "; ".join(f"{r['nombre']} [C{r['control']} #{r['id']}]" for r in message["adjuntos"]) or None
    try:
        result = db.execute(text("""
            INSERT INTO AUTOM.SOX_MAIL_OUTBOX
              (CONTROL_NUMERO, ANIO, SEMESTRE, TIPO_EVIDENCIA, ORIGEN, IDEMPOTENCY_KEY, CORRELACION,
               EMISOR, DESTINATARIOS, CC, ASUNTO, CUERPO, ADJUNTOS, ESTADO, SOLICITADO_POR, FECHA_SOLICITUD)
            VALUES (:p_control, :p_anio, :p_sem, :p_tipo, 'RECORDATORIO', :p_idem, :p_corr,
                    :p_emisor, :p_para, :p_cc, :p_asunto, :p_cuerpo, :p_adj, 'PENDIENTE', :p_user, :p_fecha)
            RETURNING ID INTO :p_returned
        """).bindparams(outparam("p_returned", Integer)), {
            "p_control": control, "p_anio": anio, "p_sem": semestre, "p_tipo": kind[:40],
            "p_idem": idem[:64], "p_corr": correlation,
            "p_emisor": message["emisor"], "p_para": "; ".join(message["destinatarios"]),
            "p_cc": "; ".join(message["cc"]) or None, "p_asunto": message["asunto"],
            "p_cuerpo": message["cuerpo"], "p_adj": labels and labels[:2000],
            "p_user": user_id, "p_fecha": mail._now()})
        value = result.out_parameters["p_returned"]
        outbox_id = int(value[0] if isinstance(value, (tuple, list)) else value)
        db.commit()
    except IntegrityError:
        db.rollback()
        mail.console(f"{kind.upper()} Control {control} ya registrado con clave {idem}: no se envía de nuevo")
        return {"estado": "YA_ENVIADO", "auditoria_id": None, "repetido": True}
    except Exception:
        db.rollback()
        mail.logger.exception("No se pudo registrar la notificación SOX")
        raise HTTPException(503, "Auditoría de correos no disponible; envío cancelado")

    mail.console(f"{kind.upper()} Control {control} registrada en SOX_MAIL_OUTBOX #{outbox_id} | "
                 f"para={message['destinatarios']} cc={message['cc']} adjuntos={[r['nombre'] for r in message['adjuntos']]}")
    footer = f"\n\n--\nEnviado desde SOX Dashboard por {username}. Referencia SOX: N{control}-{outbox_id}."
    attach_dir = tempfile.mkdtemp(prefix="sox_rec_")
    os.chmod(attach_dir, 0o700)
    try:
        payload_files = []
        for index, (name, content, ctype) in enumerate(files):
            path = os.path.join(attach_dir, f"{index}.bin")
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as handle:
                handle.write(content)
            payload_files.append({"nombre": name, "ruta": path, "content_type": ctype})
        outgoing = {**public(message), "cuerpo": message["cuerpo"] + footer}
        try:
            ok, detail, message_id = send_via_graph(outgoing, correlation, payload_files)
        except HTTPException as exc:
            mail._set_state(db, outbox_id, "FALLIDO", f"No se envió: {exc.detail}")
            raise
    finally:
        shutil.rmtree(attach_dir, ignore_errors=True)
    if ok is None:
        mail._set_state(db, outbox_id, "PENDIENTE", detail)
        raise HTTPException(504, "Graph no confirmó el envío a tiempo. Revisa el buzón antes de reintentar.")
    if not ok:
        mail._set_state(db, outbox_id, "FALLIDO", detail)
        raise HTTPException(502, "Microsoft Graph no aceptó el envío. Revisar registros del servidor.")
    # Notificación operativa: ACEPTADO es su estado final (no se archiva como evidencia).
    mail._set_state(db, outbox_id, "ACEPTADO", None, FECHA_ENVIO=mail._now(), INTERNET_MESSAGE_ID=message_id)
    return {"estado": "ACEPTADO", "auditoria_id": outbox_id, "repetido": False}


def send_via_graph(message, correlation, attachments=None):
    """Envía con el worker Graph. Devuelve (ok, detalle, internet_message_id)."""
    if not mail._env_bool("SOX_MAIL_ENABLED"):
        raise HTTPException(503, "Envíos deshabilitados: configurar SOX_MAIL_ENABLED=true tras autorización")
    payload = {**message, "correlacion": correlation, "adjuntos": attachments or []}
    try:
        code, out = mail._run_worker("enviar", payload, timeout=120)
    except subprocess.TimeoutExpired:
        return None, "Graph no respondió a tiempo. Verificar en Elementos enviados antes de reenviar.", None
    if code != 0 or not out.get("ok"):
        return False, "Microsoft Graph no aceptó el envío", None
    return True, None, out.get("internet_message_id")
