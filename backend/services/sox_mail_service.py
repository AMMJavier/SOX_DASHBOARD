"""Correo formal SOX: envío por Microsoft Graph y archivado automático como evidencia.

Flujo (una solicitud = un correo):
  1. Se registra la solicitud en AUTOM.SOX_MAIL_OUTBOX como PENDIENTE (si no se
     puede auditar, no se envía).
  2. sox_graph_mail.py crea y envía el mensaje con una cabecera de correlación.
     -> ACEPTADO / FALLIDO. Un timeout deja PENDIENTE: confirmar antes de reenviar.
  3. Se localiza la copia en Elementos enviados, se descarga el MIME (.eml), se
     genera un PDF legible y ambos se guardan en el repositorio privado como
     evidencias del control (estado CARGADA, pendiente de revisión) -> ARCHIVADO.
     Si el archivado falla, el correo NO se reenvía: se reintenta solo el archivado.

La clave de idempotencia (generada por el navegador para cada borrador) evita
que un doble clic o un reintento de red envíe dos veces el mismo correo.
"""
from datetime import datetime, timedelta, timezone
import email
from email import policy
from hashlib import sha256
import html
from io import BytesIO
import json
import logging
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import Integer, outparam, text
from sqlalchemy.exc import IntegrityError

from routes.SOX.core.evidence import EVIDENCE_TYPES, MAX_BYTES, _check_control, _storage_root

logger = logging.getLogger(__name__)

EMAIL_RE = re.compile(r"^[^@\s,;<>\"']+@[^@\s,;<>\"']+\.[^@\s,;<>\"']+$")
IDEMPOTENCY_RE = re.compile(r"^[A-Za-z0-9-]{16,64}$")
ATTACHMENT_EXTENSIONS = {".pdf", ".doc", ".docx", ".xlsx", ".png", ".jpg", ".jpeg", ".msg", ".eml"}
CONTENT_TYPES = {
    ".pdf": "application/pdf", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".msg": "application/vnd.ms-outlook", ".eml": "message/rfc822",
}
MAX_RECIPIENTS = 10
MAX_ATTACHMENTS = 5
MAX_SUBJECT = 200
MAX_BODY = 10000
STALE_ARCHIVING = timedelta(minutes=5)


# ---------------------------------------------------------------- configuración

def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _env_bool(name):
    return os.getenv(name, "false").strip().lower() == "true"


def enabled_controls():
    raw = os.getenv("SOX_MAIL_CONTROLS", "1,2,3,5")
    return {int(x) for x in re.split(r"[,;\s]+", raw) if x.strip().isdigit()}


def mail_types(control):
    """Tipos con los que puede archivarse un correo SALIENTE del control.

    Control 5: la aprobación la emite Jefatura (respuesta), no el correo enviado desde
    SOX; y el consolidado no corresponde a un evento. Así el indicador "Falta
    aprobación" del evento no se da por cumplido con una simple solicitud.
    """
    types = set(EVIDENCE_TYPES.get(control, ()))
    if control == 5:
        types -= {"aprobacion", "consolidado"}
    return types


def check_event(db, control, anio, evento_id):
    if control != 5:
        if evento_id is not None:
            raise HTTPException(422, "evento_id solo corresponde al Control 5")
        return None
    if evento_id is None or evento_id < 1:
        raise HTTPException(422, "El correo del Control 5 debe asociarse a un evento")
    event = db.execute(text("""
        SELECT ID AS "id", CUENTA AS "cuenta", OPERACION AS "operacion"
          FROM AUTOM.SOX_CONTROL5_EVENTOS WHERE ID = :p_id AND ANIO = :p_anio
    """), {"p_id": int(evento_id), "p_anio": anio}).mappings().first()
    if not event:
        raise HTTPException(404, "El evento de Control 5 no existe en el año seleccionado")
    return dict(event)


def allowed_domains():
    raw = os.getenv("SOX_MAIL_ALLOWED_DOMAINS", "")
    return sorted({x.strip().lower().lstrip("@") for x in re.split(r"[,;\s]+", raw) if x.strip()})


def max_attachment_bytes():
    try:
        mb = float(os.getenv("SOX_MAIL_MAX_ATTACH_MB", "3"))
    except ValueError:
        mb = 3
    # Graph admite ~4 MB por solicitud con adjuntos en línea (base64 suma ~33 %).
    return int(max(0.1, min(mb, 3)) * 1024 * 1024)


def sender():
    value = os.getenv("SOX_MAIL_SENDER", "").strip()
    return value if EMAIL_RE.fullmatch(value) else ""


def config_status(control):
    return {
        "control_habilitado": control in enabled_controls(),
        "envio_habilitado": _env_bool("SOX_MAIL_ENABLED"),
        "emisor": sender() or None,
        "dominios_permitidos": allowed_domains(),
        "max_adjuntos": MAX_ATTACHMENTS,
        "max_adjuntos_mb": round(max_attachment_bytes() / 1024 / 1024, 1),
        "extensiones": sorted(ATTACHMENT_EXTENSIONS),
        "tipos_evidencia": sorted(mail_types(control)),
    }


def _graph_paths():
    script = Path(os.getenv("SOX_GRAPH_SCRIPT", "/data/sisauto/buzon_prciaut/buzon_prciaut.py"))
    python = Path(os.getenv("SOX_GRAPH_PYTHON", sys.executable))
    worker = Path(os.getenv("SOX_GRAPH_MAIL_WORKER",
                            str(Path(__file__).resolve().parent.parent / "scripts" / "sox_graph_mail.py")))
    creds = os.getenv("SOX_GRAPH_CREDENTIALS", "").strip()
    for p in (script, python, worker):
        if not p.is_absolute() or not p.is_file():
            raise HTTPException(503, "Integración Graph no disponible en el servidor (script, intérprete o worker)")
    if creds and (not Path(creds).is_absolute() or not Path(creds).is_file()):
        raise HTTPException(503, "Ruta de credenciales Graph no válida")
    return python, worker, script, creds


def _run_worker(command, payload, timeout):
    python, worker, script, creds = _graph_paths()
    workdir = tempfile.mkdtemp(prefix="sox_mail_")
    os.chmod(workdir, 0o700)
    try:
        msg_path = os.path.join(workdir, "payload.json")
        fd = os.open(msg_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False)
        args = [str(python), str(worker), "--script", str(script)]
        if creds:
            args += ["-c", creds]
        args += [command, "-m", msg_path]
        proc = subprocess.run(args, shell=False, capture_output=True, text=True, timeout=timeout, check=False)
        if proc.stderr:
            logger.info("sox_graph_mail %s stderr: %s", command, proc.stderr[-2000:])
        try:
            result = json.loads((proc.stdout or "").strip().splitlines()[-1])
        except (IndexError, ValueError):
            result = {"ok": False, "error": "Respuesta no interpretable del worker Graph"}
        return proc.returncode, result
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


# ---------------------------------------------------------------- validaciones

def _clean_line(value, field, max_len, required=True):
    value = (value or "").strip()
    if required and not value:
        raise HTTPException(422, f"Indica {field}")
    if len(value) > max_len or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise HTTPException(422, f"{field.capitalize()} inválido o demasiado extenso")
    return value


def parse_addresses(raw, field, required):
    items = [x.strip() for x in re.split(r"[,;\s]+", raw or "") if x.strip()]
    if required and not items:
        raise HTTPException(422, f"Indica al menos un destinatario en {field}")
    if len(items) > MAX_RECIPIENTS:
        raise HTTPException(422, f"Máximo {MAX_RECIPIENTS} direcciones en {field}")
    domains = allowed_domains()
    if not domains:
        raise HTTPException(503, "SOX_MAIL_ALLOWED_DOMAINS no está configurado; envío bloqueado")
    seen = set()
    for address in items:
        if not EMAIL_RE.fullmatch(address):
            raise HTTPException(422, f"Dirección inválida en {field}: {address}")
        if address.rsplit("@", 1)[1].lower() not in domains:
            raise HTTPException(422, f"Dominio no autorizado en {field}: {address}")
        if address.casefold() in seen:
            raise HTTPException(422, f"Dirección repetida en {field}: {address}")
        seen.add(address.casefold())
    return items


def _validate_attachments(files):
    files = files or []
    if len(files) > MAX_ATTACHMENTS:
        raise HTTPException(422, f"Máximo {MAX_ATTACHMENTS} adjuntos")
    total = 0
    clean = []
    for name, content in files:
        original = Path((name or "").replace("\\", "/")).name.strip()
        ext = Path(original).suffix.lower()
        if not original or len(original) > 200 or any(ord(c) < 32 or ord(c) == 127 for c in original) or ext not in ATTACHMENT_EXTENSIONS:
            raise HTTPException(422, f"Adjunto no admitido: {original or 'sin nombre'}")
        if not content:
            raise HTTPException(422, f"Adjunto vacío: {original}")
        total += len(content)
        clean.append((original, content, CONTENT_TYPES.get(ext, "application/octet-stream")))
    if total > max_attachment_bytes():
        raise HTTPException(413, f"Los adjuntos superan {round(max_attachment_bytes() / 1024 / 1024, 1)} MB en total")
    return clean


def parse_evidence_ids(raw):
    ids = []
    for chunk in re.split(r"[,;\s]+", raw or ""):
        if not chunk:
            continue
        if not chunk.isdigit() or int(chunk) < 1:
            raise HTTPException(422, "Identificador de evidencia inválido")
        if int(chunk) not in ids:
            ids.append(int(chunk))
    if len(ids) > MAX_ATTACHMENTS:
        raise HTTPException(422, f"Máximo {MAX_ATTACHMENTS} adjuntos")
    return ids


def load_repository_attachments(db, control, anio, ids, evento_id=None):
    """Adjunta documentos ya almacenados, sin copiarlos ni duplicarlos en Oracle.

    Se permiten evidencias del mismo control y año. El Control 3 puede adjuntar
    además el Plan de Seguridad VERIFICADO del Control 2 del mismo año. En el
    Control 5 solo las evidencias del mismo evento (no se mezclan expedientes).
    """
    files, refs = [], []
    for evidence_id in ids:
        row = db.execute(text("""
            SELECT ID AS "id", CONTROL_NUMERO AS "control", ANIO AS "anio", TIPO_EVIDENCIA AS "tipo",
                   ESTADO AS "estado", NOMBRE_ARCHIVO AS "nombre", ARCHIVO_KEY AS "key", SHA256 AS "sha256",
                   EVENTO_ID AS "evento_id"
              FROM AUTOM.SOX_CONTROL_EVIDENCIAS WHERE ID = :p_id
        """), {"p_id": evidence_id}).mappings().first()
        allowed = bool(row) and row["anio"] == anio and (
            (row["control"] == control and (control != 5 or row["evento_id"] == evento_id))
            or (control == 3 and row["control"] == 2 and row["tipo"] == "plan" and row["estado"] == "VERIFICADA"))
        if not allowed:
            raise HTTPException(422, f"La evidencia #{evidence_id} no puede adjuntarse a este control y año")
        if not re.fullmatch(r"[0-9a-f]{32}", row["key"] or ""):
            raise HTTPException(503, "Identificador de almacenamiento inválido")
        path = _storage_root() / row["key"]
        if not path.is_file():
            raise HTTPException(503, f"Archivo físico no disponible para la evidencia #{evidence_id}")
        content = path.read_bytes()
        if sha256(content).hexdigest() != row["sha256"]:
            raise HTTPException(503, f"La evidencia #{evidence_id} no supera la comprobación de integridad")
        files.append((row["nombre"], content))
        refs.append({"id": row["id"], "control": row["control"], "nombre": row["nombre"]})
    return files, refs


# ---------------------------------------------------------------- consultas

_SELECT = """
    SELECT o.ID AS "id", o.CONTROL_NUMERO AS "control", o.ANIO AS "anio", o.SEMESTRE AS "semestre",
           o.TIPO_EVIDENCIA AS "tipo", o.ORIGEN AS "origen", o.EMISOR AS "emisor",
           o.DESTINATARIOS AS "destinatarios", o.CC AS "cc", o.ASUNTO AS "asunto",
           o.ADJUNTOS AS "adjuntos", o.ESTADO AS "estado", o.DETALLE AS "detalle",
           o.EVIDENCIA_EML_ID AS "evidencia_eml_id", o.EVIDENCIA_PDF_ID AS "evidencia_pdf_id",
           eml.NOMBRE_ARCHIVO AS "eml_nombre", pdf.NOMBRE_ARCHIVO AS "pdf_nombre",
           o.INTENTOS_ARCHIVO AS "intentos_archivo", o.FECHA_SOLICITUD AS "fecha_solicitud",
           o.FECHA_ENVIO AS "fecha_envio", o.FECHA_ARCHIVO AS "fecha_archivo",
           u.USERNAME AS "solicitado_por", o.SOLICITADO_POR AS "solicitado_por_id",
           o.EVENTO_ID AS "evento_id"
      FROM AUTOM.SOX_MAIL_OUTBOX o
      JOIN AUTOM.USUARIOS u ON u.ID = o.SOLICITADO_POR
      LEFT JOIN AUTOM.SOX_CONTROL_EVIDENCIAS eml ON eml.ID = o.EVIDENCIA_EML_ID
      LEFT JOIN AUTOM.SOX_CONTROL_EVIDENCIAS pdf ON pdf.ID = o.EVIDENCIA_PDF_ID
"""


def _serialize(row):
    item = dict(row)
    for key, value in item.items():
        if isinstance(value, datetime):
            item[key] = value.isoformat()
    return item


def _get(db, outbox_id=None, idem=None):
    if outbox_id is not None:
        row = db.execute(text(_SELECT + " WHERE o.ID = :p_id"), {"p_id": int(outbox_id)}).mappings().first()
    else:
        row = db.execute(text(_SELECT + " WHERE o.IDEMPOTENCY_KEY = :p_idem"), {"p_idem": idem}).mappings().first()
    return _serialize(row) if row else None


def list_outbox(db, control, anio, semestre, evento_id=None):
    _check_control(control, anio, semestre)
    rows = db.execute(text(_SELECT + """
         WHERE o.CONTROL_NUMERO = :p_control AND o.ANIO = :p_anio
           AND ((:p_semestre IS NULL AND o.SEMESTRE IS NULL) OR o.SEMESTRE = :p_semestre)
           AND (:p_evento IS NULL OR o.EVENTO_ID = :p_evento)
         ORDER BY o.FECHA_SOLICITUD DESC, o.ID DESC FETCH FIRST 100 ROWS ONLY
    """), {"p_control": control, "p_anio": anio, "p_semestre": semestre, "p_evento": evento_id}).mappings()
    return [_serialize(r) for r in rows]


def _set_state(db, outbox_id, estado, detalle=None, **extra):
    sets = ["ESTADO = :p_estado", "DETALLE = :p_detalle"]
    params = {"p_estado": estado, "p_detalle": (detalle or None) and detalle[:500], "p_id": outbox_id}
    for column, value in extra.items():
        sets.append(f"{column} = :p_{column.lower()}")
        params[f"p_{column.lower()}"] = value
    db.execute(text(f"UPDATE AUTOM.SOX_MAIL_OUTBOX SET {', '.join(sets)} WHERE ID = :p_id"), params)
    db.commit()


# ---------------------------------------------------------------- envío

def send_mail(db, *, control, anio, semestre, tipo, para, cc, asunto, cuerpo, adjuntos, idempotency_key, user,
              evidencias_ids=None, evento_id=None):
    if control not in enabled_controls():
        raise HTTPException(404, "El envío de correos no está habilitado para este control")
    _check_control(control, anio, semestre)
    if control == 5 and semestre is not None:
        raise HTTPException(422, "El correo de un evento no lleva semestre")
    if tipo not in mail_types(control):
        raise HTTPException(422, "Tipo documental no admitido para un correo enviado desde este control")
    event = check_event(db, control, anio, evento_id)
    if not IDEMPOTENCY_RE.fullmatch(idempotency_key or ""):
        raise HTTPException(422, "Clave de idempotencia inválida")

    previous = _get(db, idem=idempotency_key)
    if previous:
        if previous["solicitado_por_id"] != user.id:
            raise HTTPException(409, "La solicitud ya existe")
        return {**previous, "repetido": True}

    if not _env_bool("SOX_MAIL_ENABLED"):
        raise HTTPException(503, "Envíos deshabilitados: configurar SOX_MAIL_ENABLED=true tras autorización")
    emisor = sender()
    if not emisor:
        raise HTTPException(503, "SOX_MAIL_SENDER no está configurado")
    to_list = parse_addresses(para, "Para", True)
    cc_list = parse_addresses(cc, "CC", False)
    if {x.casefold() for x in to_list} & {x.casefold() for x in cc_list}:
        raise HTTPException(422, "Una dirección no puede estar en Para y CC a la vez")
    asunto = _clean_line(asunto, "el asunto", MAX_SUBJECT)
    cuerpo = (cuerpo or "").replace("\r\n", "\n").strip()
    if not cuerpo or len(cuerpo) > MAX_BODY or any(ord(c) < 32 and c not in "\n\t" for c in cuerpo):
        raise HTTPException(422, f"El mensaje es obligatorio y admite hasta {MAX_BODY} caracteres")
    repo_files, repo_refs = load_repository_attachments(db, control, anio, evidencias_ids or [], evento_id)
    files = _validate_attachments(list(adjuntos or []) + repo_files)  # Límites sobre el total
    labels = [n for n, _, _ in files[:len(files) - len(repo_files)]]
    labels += [f"{r['nombre']} [repositorio C{r['control']} #{r['id']}]" for r in repo_refs]

    correlacion = uuid4().hex
    try:
        result = db.execute(text("""
            INSERT INTO AUTOM.SOX_MAIL_OUTBOX
              (CONTROL_NUMERO, ANIO, SEMESTRE, TIPO_EVIDENCIA, ORIGEN, IDEMPOTENCY_KEY, CORRELACION,
               EMISOR, DESTINATARIOS, CC, ASUNTO, CUERPO, ADJUNTOS, ESTADO, SOLICITADO_POR, FECHA_SOLICITUD,
               EVENTO_ID)
            VALUES (:p_control, :p_anio, :p_semestre, :p_tipo, 'MANUAL', :p_idem, :p_corr,
                    :p_emisor, :p_para, :p_cc, :p_asunto, :p_cuerpo, :p_adjuntos, 'PENDIENTE', :p_user, :p_fecha,
                    :p_evento)
            RETURNING ID INTO :p_returned
        """).bindparams(outparam("p_returned", Integer)), {
            "p_control": control, "p_anio": anio, "p_semestre": semestre, "p_tipo": tipo, "p_evento": evento_id,
            "p_idem": idempotency_key, "p_corr": correlacion, "p_emisor": emisor,
            "p_para": "; ".join(to_list), "p_cc": "; ".join(cc_list) or None, "p_asunto": asunto,
            "p_cuerpo": cuerpo, "p_adjuntos": ("; ".join(labels))[:2000] or None,
            "p_user": user.id, "p_fecha": _now()})
        value = result.out_parameters["p_returned"]
        outbox_id = int(value[0] if isinstance(value, (tuple, list)) else value)
        # Trazabilidad en la evidencia original: se consultó para adjuntarla a un correo.
        for ref in repo_refs:
            db.execute(text("""
                INSERT INTO AUTOM.SOX_CONTROL_EVIDENCIA_AUD (EVIDENCIA_ID, ACCION, USUARIO_ID, FECHA, DETALLE)
                VALUES (:p_evid, 'DESCARGA', :p_user, :p_fecha, :p_det)
            """), {"p_evid": ref["id"], "p_user": user.id, "p_fecha": _now(),
                   "p_det": f"Adjuntada al correo SOX #{outbox_id} (Control {control})"})
        db.commit()
    except IntegrityError:
        db.rollback()
        previous = _get(db, idem=idempotency_key)
        if previous and previous["solicitado_por_id"] == user.id:
            return {**previous, "repetido": True}
        raise HTTPException(409, "La solicitud ya existe")
    except Exception:
        db.rollback()
        logger.exception("No se pudo registrar la solicitud de correo SOX")
        raise HTTPException(503, "Auditoría de correos no disponible; envío cancelado")

    footer = (f"\n\n--\nEnviado desde SOX Dashboard por {user.username}. "
              f"Referencia SOX: C{control}-{outbox_id}"
              + (f" · Evento #{event['id']} ({event['operacion']} {event['cuenta']})" if event else "") + ".")
    attach_dir = tempfile.mkdtemp(prefix="sox_adj_")
    os.chmod(attach_dir, 0o700)
    try:
        attach_payload = []
        for index, (name, content, ctype) in enumerate(files):
            path = os.path.join(attach_dir, f"{index}.bin")
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as handle:
                handle.write(content)
            attach_payload.append({"nombre": name, "ruta": path, "content_type": ctype})
        payload = {"emisor": emisor, "destinatarios": to_list, "cc": cc_list, "asunto": asunto,
                   "cuerpo": cuerpo + footer, "formato": "texto", "correlacion": correlacion,
                   "adjuntos": attach_payload}
        try:
            code, out = _run_worker("enviar", payload, timeout=120)
        except subprocess.TimeoutExpired:
            _set_state(db, outbox_id, "PENDIENTE",
                       "Graph no respondió a tiempo. Verificar en Elementos enviados antes de volver a enviar.")
            raise HTTPException(504, "Graph no confirmó el envío a tiempo. Revisa el buzón antes de reintentar.")
        except HTTPException as exc:  # Integración no disponible: el worker no llegó a ejecutarse.
            _set_state(db, outbox_id, "FALLIDO", f"No se envió: {exc.detail}")
            raise
        if code != 0 or not out.get("ok"):
            logger.error("Correo SOX #%s rechazado: %s", outbox_id, out.get("error"))
            _set_state(db, outbox_id, "FALLIDO", "Microsoft Graph no aceptó el envío")
            raise HTTPException(502, "Microsoft Graph no aceptó el envío. Revisar registros restringidos del servidor.")
        _set_state(db, outbox_id, "ACEPTADO", None, FECHA_ENVIO=_now(),
                   INTERNET_MESSAGE_ID=(out.get("internet_message_id") or None))
    finally:
        shutil.rmtree(attach_dir, ignore_errors=True)

    # El archivado nunca provoca un segundo envío: si falla queda ACEPTADO para reintentar.
    try:
        archive_mail(db, control=control, outbox_id=outbox_id, user=user)
    except HTTPException as exc:
        logger.warning("Correo SOX #%s enviado; archivado pendiente: %s", outbox_id, exc.detail)
    return _get(db, outbox_id=outbox_id)


# ---------------------------------------------------------------- archivado

def archive_mail(db, *, control, outbox_id, user):
    row = db.execute(text("""
        SELECT ANIO AS "anio", SEMESTRE AS "semestre", TIPO_EVIDENCIA AS "tipo_evidencia",
               EMISOR AS "emisor", ASUNTO AS "asunto", CORRELACION AS "correlacion",
               INTERNET_MESSAGE_ID AS "internet_message_id", ESTADO AS "estado",
               FECHA_SOLICITUD AS "fecha_solicitud", SOLICITADO_POR AS "solicitado_por",
               EVENTO_ID AS "evento_id", ORIGEN AS "origen"
          FROM AUTOM.SOX_MAIL_OUTBOX WHERE ID = :p_id AND CONTROL_NUMERO = :p_control
    """), {"p_id": int(outbox_id), "p_control": control}).mappings().first()
    if not row:
        raise HTTPException(404, "Correo inexistente")
    if row["origen"] != "MANUAL":
        raise HTTPException(409, "Las notificaciones automáticas no se archivan como evidencia documental")
    if row["estado"] == "ARCHIVADO":
        return _get(db, outbox_id=outbox_id)
    now = _now()
    locked = db.execute(text("""
        UPDATE AUTOM.SOX_MAIL_OUTBOX
           SET ESTADO = 'ARCHIVANDO', FECHA_ULTIMO_INTENTO = :p_now, INTENTOS_ARCHIVO = INTENTOS_ARCHIVO + 1
         WHERE ID = :p_id
           AND (ESTADO = 'ACEPTADO' OR (ESTADO = 'ARCHIVANDO' AND FECHA_ULTIMO_INTENTO < :p_limite))
    """), {"p_now": now, "p_id": int(outbox_id), "p_limite": now - STALE_ARCHIVING})
    if locked.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "El correo no está pendiente de archivar o el archivado ya está en curso")
    db.commit()

    workdir = tempfile.mkdtemp(prefix="sox_eml_")
    os.chmod(workdir, 0o700)
    stored = []
    try:
        eml_path = os.path.join(workdir, "mensaje.eml")
        desde = (row["fecha_solicitud"] - timedelta(minutes=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
        try:
            code, out = _run_worker("archivar", {
                "emisor": row["emisor"], "internet_message_id": row["internet_message_id"],
                "correlacion": row["correlacion"], "desde_utc": desde, "salida": eml_path,
                "espera_seg": int(os.getenv("SOX_MAIL_ARCHIVE_WAIT", "20")),
            }, timeout=150)
        except subprocess.TimeoutExpired:
            code, out = 1, {"ok": False, "error": "timeout"}
        if code == 3:
            _set_state(db, outbox_id, "ACEPTADO",
                       "La copia aún no aparece en Elementos enviados; reintentar el archivado en unos minutos.")
            raise HTTPException(409, "La copia del correo todavía no está disponible. Reintenta el archivado en unos minutos.")
        if code != 0 or not out.get("ok"):
            logger.error("Archivado correo SOX #%s falló: %s", outbox_id, out.get("error"))
            _set_state(db, outbox_id, "ACEPTADO", "No se pudo recuperar la copia desde Graph; reintentar archivado.")
            raise HTTPException(502, "No se pudo recuperar la copia del correo desde Graph.")

        eml = Path(eml_path).read_bytes()
        if not eml or len(eml) > MAX_BYTES:
            _set_state(db, outbox_id, "ACEPTADO", "La copia del correo está vacía o supera 15 MB.")
            raise HTTPException(413, "La copia del correo está vacía o supera el límite de evidencia")
        pdf = eml_to_pdf(eml, outbox_id=outbox_id, control=control)

        stamp = now.strftime("%Y%m%d_%H%M%S")
        safe_subject = re.sub(r"[^A-Za-z0-9_-]+", "_", row["asunto"])[:60].strip("_") or "correo"
        base_name = f"Control{control}_Correo{outbox_id}_{stamp}_{safe_subject}"
        referencia = f"Correo SOX #{outbox_id} · {row['asunto']}"[:250]
        observaciones = ("Copia archivada automáticamente desde Elementos enviados (Microsoft Graph). "
                         "Que Graph aceptara el envío no implica recepción ni aprobación de Gerencia.")
        common = {"control": control, "anio": row["anio"], "semestre": row["semestre"], "tipo": row["tipo_evidencia"],
                  "referencia": referencia, "observaciones": observaciones,
                  "autor": row["solicitado_por"], "actor": user.id, "outbox_id": outbox_id,
                  "evento_id": row["evento_id"]}  # Control 5: queda dentro del expediente del evento
        eml_id = _store_evidence(db, stored, filename=f"{base_name}.eml", content=eml, **common)
        pdf_id = _store_evidence(db, stored, filename=f"{base_name}.pdf", content=pdf, **common)
        db.execute(text("""
            UPDATE AUTOM.SOX_MAIL_OUTBOX
               SET ESTADO = 'ARCHIVADO', DETALLE = NULL, EVIDENCIA_EML_ID = :p_eml, EVIDENCIA_PDF_ID = :p_pdf,
                   GRAPH_MESSAGE_ID = :p_gid, INTERNET_MESSAGE_ID = NVL(INTERNET_MESSAGE_ID, :p_imid),
                   FECHA_ARCHIVO = :p_now
             WHERE ID = :p_id AND ESTADO = 'ARCHIVANDO'
        """), {"p_eml": eml_id, "p_pdf": pdf_id, "p_gid": (out.get("graph_message_id") or "")[:500] or None,
               "p_imid": (out.get("internet_message_id") or "")[:500] or None, "p_now": _now(), "p_id": int(outbox_id)})
        db.commit()
        stored.clear()
        return _get(db, outbox_id=outbox_id)
    except HTTPException:
        # Liberar el bloqueo si la causa no lo hizo (p. ej. integración no disponible).
        db.rollback()
        db.execute(text("""
            UPDATE AUTOM.SOX_MAIL_OUTBOX SET ESTADO = 'ACEPTADO'
             WHERE ID = :p_id AND ESTADO = 'ARCHIVANDO'
        """), {"p_id": int(outbox_id)})
        db.commit()
        raise
    except Exception:
        db.rollback()
        logger.exception("Archivado correo SOX #%s falló", outbox_id)
        try:
            _set_state(db, outbox_id, "ACEPTADO", "Error al guardar la evidencia del correo; reintentar archivado.")
        except Exception:
            db.rollback()
        raise HTTPException(500, "Error al guardar la evidencia del correo; el correo NO se reenviará.")
    finally:
        for path in stored:  # Solo quedan aquí si no se confirmó la transacción.
            path.unlink(missing_ok=True)
        shutil.rmtree(workdir, ignore_errors=True)


def _store_evidence(db, stored, *, control, anio, semestre, tipo, referencia, observaciones,
                    filename, content, autor, actor, outbox_id, evento_id=None):
    root = _storage_root()
    key = uuid4().hex
    path = root / key
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(content)
    stored.append(path)
    result = db.execute(text("""
        INSERT INTO AUTOM.SOX_CONTROL_EVIDENCIAS
          (CONTROL_NUMERO, ANIO, SEMESTRE, TIPO_EVIDENCIA, REFERENCIA, OBSERVACIONES,
           NOMBRE_ARCHIVO, ARCHIVO_KEY, TAMANIO_BYTES, SHA256, ESTADO, CREADO_POR, CREADO_EN, EVENTO_ID)
        VALUES (:p_control, :p_anio, :p_semestre, :p_tipo, :p_ref, :p_obs,
                :p_nombre, :p_key, :p_size, :p_sha, 'CARGADA', :p_autor, :p_fecha, :p_evento)
        RETURNING ID INTO :p_returned
    """).bindparams(outparam("p_returned", Integer)), {
        "p_control": control, "p_anio": anio, "p_semestre": semestre, "p_tipo": tipo,
        "p_ref": referencia, "p_obs": observaciones, "p_nombre": filename[:255], "p_key": key,
        "p_size": len(content), "p_sha": sha256(content).hexdigest(), "p_autor": autor, "p_fecha": _now(),
        "p_evento": evento_id})
    value = result.out_parameters["p_returned"]
    evidence_id = int(value[0] if isinstance(value, (tuple, list)) else value)
    db.execute(text("""
        INSERT INTO AUTOM.SOX_CONTROL_EVIDENCIA_AUD (EVIDENCIA_ID, ACCION, USUARIO_ID, FECHA, DETALLE)
        VALUES (:p_evid, 'CARGA', :p_user, :p_fecha, :p_det)
    """), {"p_evid": evidence_id, "p_user": actor, "p_fecha": _now(),
           "p_det": f"Archivado automático del correo SOX #{outbox_id}"})
    return evidence_id


# ---------------------------------------------------------------- PDF legible

def _latin(value):
    # Las fuentes estándar de ReportLab usan WinAnsi; se sustituye lo no representable.
    value = "".join(c if (ord(c) >= 32 or c == "\n") else " " for c in str(value or ""))
    return value.encode("cp1252", "replace").decode("cp1252")


def _html_to_text(markup):
    markup = re.sub(r"(?is)<(script|style).*?</\1>", "", markup)
    markup = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</tr>|</li>", "\n", markup)
    markup = re.sub(r"<[^>]+>", "", markup)
    return re.sub(r"\n{3,}", "\n\n", html.unescape(markup)).strip()


def eml_to_pdf(eml_bytes, *, outbox_id, control):
    """Representación legible del correo; el original íntegro es el archivo EML."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.utils import simpleSplit
        from reportlab.pdfgen.canvas import Canvas
    except ImportError as exc:
        raise RuntimeError("Falta instalar reportlab en el backend") from exc

    msg = email.message_from_bytes(eml_bytes, policy=policy.default)
    body_part = msg.get_body(preferencelist=("plain", "html"))
    body = ""
    if body_part is not None:
        body = body_part.get_content()
        if body_part.get_content_subtype() == "html":
            body = _html_to_text(body)
    attachments = []
    for part in msg.iter_attachments():
        data = part.get_payload(decode=True) or b""
        attachments.append(f"{part.get_filename() or 'sin nombre'} ({len(data) / 1024:.1f} KB)")

    buf = BytesIO()
    width, height = A4
    pdf = Canvas(buf, pagesize=A4, pageCompression=1)
    margin = 45
    usable = width - 2 * margin
    state = {"y": 0, "page": 0}

    def header():
        state["page"] += 1
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(margin, height - 35, _latin(f"HITSS | SOX Control {control} - Correo archivado como evidencia"))
        pdf.setStrokeColor(colors.HexColor("#D7DEE8"))
        pdf.line(margin, height - 45, width - margin, height - 45)
        pdf.setFont("Helvetica", 7)
        pdf.drawString(margin, 22, _latin(f"Correo SOX #{outbox_id} · SHA256 EML: {sha256(eml_bytes).hexdigest()}"))
        pdf.drawRightString(width - margin, 22, f"Página {state['page']}")
        state["y"] = height - 65

    def write(value, bold=False, size=9, gap=3):
        font = "Helvetica-Bold" if bold else "Helvetica"
        for paragraph in _latin(value).split("\n"):
            for chunk in simpleSplit(paragraph, font, size, usable) or [""]:
                if state["y"] < 45:
                    pdf.showPage()
                    header()
                pdf.setFont(font, size)
                pdf.drawString(margin, state["y"], chunk)
                state["y"] -= size + gap

    header()
    for label, key in (("De", "From"), ("Para", "To"), ("CC", "Cc"), ("Asunto", "Subject"),
                       ("Fecha", "Date"), ("Message-ID", "Message-ID")):
        if msg.get(key):
            write(f"{label}: {msg.get(key)}", bold=(label == "Asunto"))
    write(f"Adjuntos: {', '.join(attachments) if attachments else 'ninguno'}")
    state["y"] -= 6
    pdf.line(margin, state["y"] + 8, width - margin, state["y"] + 8)
    write(body or "(sin contenido de texto)", size=10, gap=4)
    state["y"] -= 8
    write("Representación PDF generada por SOX Dashboard. El original íntegro (con adjuntos) es el archivo "
          "EML asociado al mismo correo. El envío aceptado por Microsoft Graph no acredita recepción ni aprobación.",
          size=7)
    pdf.save()
    content = buf.getvalue()
    if not content.startswith(b"%PDF-") or len(content) > MAX_BYTES:
        raise RuntimeError("PDF del correo inválido o demasiado grande")
    return content
