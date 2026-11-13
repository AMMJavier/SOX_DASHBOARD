"""Control 7: aviso individual a cada gerente al abrir una campaña de validación VPN.

- Gerentes: solo los que tienen VPN en la campaña ACTIVA (AUTOM.CHECKPOINT_TRANSFORM).
- Correos: AUTOM.SOX_GERENTES_CONTACTO (no se consulta LDAP al enviar ni se duplican contactos).
- Auditoría: AUTOM.SOX_MAIL_OUTBOX con ORIGEN='CAMPANA' (intento, destinatario y resultado).
- Sin duplicados: un gerente con aviso ACEPTADO o sin confirmar (PENDIENTE) no vuelve a
  recibirlo; solo los FALLIDO pueden reintentarse, con un nuevo intento auditado.
- El aviso es una notificación de apertura, NO evidencia de revisión: la evidencia sigue
  siendo la validación registrada por el gerente en el portal con su cuenta.
"""
from datetime import datetime
from hashlib import sha256
import logging
import os
import re
import subprocess
import threading
import unicodedata
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import Integer, outparam, text
from sqlalchemy.exc import IntegrityError

from services.sox.common import mail_config
from services.sox.common import mail_service as mail

logger = logging.getLogger(__name__)
_batch_lock = threading.Lock()

READY, NO_CONTACT, AMBIGUOUS, DOMAIN = "LISTO", "SIN_CONTACTO", "AMBIGUO", "DOMINIO_NO_PERMITIDO"

# ---------------------------------------------------------------- MODO PRUEBA
# Se configura en backend/config/correos.json > controles.7.aviso_gerentes.modo_prueba.
# Con "activo": true y destinatarios, los avisos NO usan AUTOM.SOX_GERENTES_CONTACTO:
# el aviso de cada gerente se envía a esas direcciones con asunto [PRUEBA] y una nota.
# Para usar los correos reales de Oracle: "activo": false.


def modo_prueba():
    return mail_config.c7_notice()["modo_prueba"]


def correos_prueba():
    return mail_config.c7_notice()["destinatarios_prueba"] if modo_prueba() else []


def _resolve_contact(contacts, key):
    """Devuelve (estado_contacto, lista_de_correos) para un gerente."""
    if modo_prueba():
        emails = correos_prueba()
    else:
        found = list(contacts.get(key, {}).values())
        if not found:
            return NO_CONTACT, []
        if len(found) > 1:
            return AMBIGUOUS, []
        emails = found
    # Las direcciones fijas también pasan por la lista blanca de dominios.
    domains = mail.allowed_domains()
    valid = all(mail.EMAIL_RE.fullmatch(e) and e.rsplit("@", 1)[1].lower() in domains for e in emails)
    return (READY if valid else DOMAIN), emails


# ---------------------------------------------------------------- utilidades

def manager_key(name):
    """Normaliza como lo hace el Control 7 en Oracle: sin NBSP, espacios ni acentos, sin mayúsculas."""
    value = (name or "").replace("\xa0", " ")
    value = unicodedata.normalize("NFKD", value)
    value = "".join(c for c in value if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", value).strip().casefold()


def _key_hash(key):
    return sha256(key.encode("utf-8")).hexdigest()[:24]


def batch_running():
    return _batch_lock.locked()


def active_campaign(db):
    row = db.execute(text("""
        SELECT ID_CAMPANA AS "id", NOMBRE_CAMPANA AS "nombre", ANIO AS "anio", SEMESTRE AS "semestre",
               FECHA_INICIO AS "fecha_inicio", FECHA_LIMITE AS "fecha_limite"
          FROM AUTOM.CAMPANAS_SOX WHERE ESTADO = 'ACTIVA'
         ORDER BY ID_CAMPANA DESC FETCH FIRST 1 ROWS ONLY
    """)).mappings().first()
    return dict(row) if row else None


def _campaign_managers(db):
    rows = db.execute(text("""
        SELECT GERENTE AS "gerente", COUNT(*) AS "vpn",
               SUM(CASE WHEN NVL(CONFIRMACION, 0) = 1 THEN 1 ELSE 0 END) AS "confirmadas"
          FROM (SELECT t.GERENTE, t.CONFIRMACION,
                       ROW_NUMBER() OVER (PARTITION BY t.CHECKPOINT_UID ORDER BY t.FECHA_ALMACENADO DESC) rn
                  FROM AUTOM.CHECKPOINT_TRANSFORM t)
         WHERE rn = 1
         GROUP BY GERENTE
    """)).mappings()
    managers, without_manager, total = {}, 0, 0
    for row in rows:
        count = int(row["vpn"] or 0)
        total += count
        key = manager_key(row["gerente"])
        if not key:
            without_manager += count
            continue
        item = managers.setdefault(key, {"key": key, "gerente": re.sub(r"\s+", " ", row["gerente"].replace("\xa0", " ")).strip(),
                                         "vpn": 0, "confirmadas": 0})
        item["vpn"] += count
        item["confirmadas"] += int(row["confirmadas"] or 0)
    return managers, without_manager, total


def _vpns_by_manager(db):
    """VPN de la campaña agrupadas por gerente normalizado (misma deduplicación que _campaign_managers)."""
    rows = db.execute(text("""
        SELECT GERENTE AS "gerente", NOMBRE_VPN AS "nombre_vpn", REQ AS "req", SOLICITANTE AS "solicitante"
          FROM (SELECT t.GERENTE, t.NOMBRE_VPN, t.REQ, t.SOLICITANTE,
                       ROW_NUMBER() OVER (PARTITION BY t.CHECKPOINT_UID ORDER BY t.FECHA_ALMACENADO DESC) rn
                  FROM AUTOM.CHECKPOINT_TRANSFORM t)
         WHERE rn = 1
         ORDER BY NOMBRE_VPN
    """)).mappings()
    result = {}
    for row in rows:
        key = manager_key(row["gerente"])
        if key:
            result.setdefault(key, []).append(dict(row))
    return result


def _vpn_table(vpns):
    """Tabla en texto plano (el aviso se envía en formato texto)."""
    def cell(value):
        return re.sub(r"\s+", " ", str(value or "-")).strip() or "-"
    rows = [(cell(v["nombre_vpn"]), cell(v["req"]), cell(v["solicitante"])) for v in vpns]
    head = ("NOMBRE VPN", "REQ", "SOLICITANTE")
    widths = [max(len(head[i]), *(len(r[i]) for r in rows)) for i in range(3)] if rows else [len(h) for h in head]
    line = lambda r: "  " + "   ".join(r[i].ljust(widths[i]) for i in range(3)).rstrip()
    return "\n".join([line(head), line(tuple("-" * w for w in widths))] + [line(r) for r in rows])


def _contacts(db):
    rows = db.execute(text("""
        SELECT NOMBRE_COMPLETO AS "nombre", CORREO AS "correo"
          FROM AUTOM.SOX_GERENTES_CONTACTO WHERE ACTIVO = 1 AND CORREO IS NOT NULL
    """)).mappings()
    contacts = {}
    for row in rows:
        email = (row["correo"] or "").strip()
        if email:
            contacts.setdefault(manager_key(row["nombre"]), {})[email.casefold()] = email
    return contacts


def _notifications(db, campaign_id):
    rows = db.execute(text("""
        SELECT ID AS "id", GERENTE_KEY AS "key", ESTADO AS "estado", DESTINATARIOS AS "correo",
               DETALLE AS "detalle", FECHA_SOLICITUD AS "fecha_solicitud", FECHA_ENVIO AS "fecha_envio"
          FROM AUTOM.SOX_MAIL_OUTBOX
         WHERE ORIGEN = 'CAMPANA' AND ID_CAMPANA = :p_camp
         ORDER BY ID
    """), {"p_camp": campaign_id}).mappings()
    result = {}
    for row in rows:
        result.setdefault(row["key"], []).append(dict(row))
    return result


def _notification_state(attempts):
    """Estado que decide si se puede (re)enviar a un gerente."""
    if not attempts:
        return None, 0
    states = {a["estado"] for a in attempts}
    if "ACEPTADO" in states:
        return "ACEPTADO", len(attempts)
    if "PENDIENTE" in states:
        return "PENDIENTE", len(attempts)
    return "FALLIDO", len(attempts)


def _fmt(value):
    if isinstance(value, datetime):
        return value.isoformat()
    return value


# ---------------------------------------------------------------- vista previa

def preview(db):
    campaign = active_campaign(db)
    if not campaign:
        return {"campana": None, "gerentes": [], "resumen": None, "en_proceso": batch_running()}
    managers, without_manager, total = _campaign_managers(db)
    contacts = {} if modo_prueba() else _contacts(db)
    sent = _notifications(db, campaign["id"])
    items = []
    for key, item in sorted(managers.items(), key=lambda kv: kv[1]["gerente"]):
        contact_state, emails = _resolve_contact(contacts, key)
        email = ", ".join(emails) if emails else None
        attempts = sent.get(key, [])
        state, count = _notification_state(attempts)
        last = attempts[-1] if attempts else None
        items.append({
            "gerente": item["gerente"], "clave": _key_hash(key), "vpn": item["vpn"],
            "pendientes": item["vpn"] - item["confirmadas"], "correo": email,
            "correos_encontrados": len(emails), "contacto": contact_state,
            "notificacion": state, "intentos": count,
            "detalle": last["detalle"] if last else None,
            "fecha_envio": _fmt(last["fecha_envio"]) if last else None,
            "enviable": contact_state == READY and state in (None, "FALLIDO"),
        })
    summary = {
        "gerentes": len(items),
        "listos": sum(x["enviable"] for x in items),
        "notificados": sum(x["notificacion"] == "ACEPTADO" for x in items),
        "sin_confirmar": sum(x["notificacion"] == "PENDIENTE" for x in items),
        "fallidos": sum(x["notificacion"] == "FALLIDO" for x in items),
        "sin_contacto": sum(x["contacto"] == NO_CONTACT for x in items),
        "ambiguos": sum(x["contacto"] == AMBIGUOUS for x in items),
        "dominio_no_permitido": sum(x["contacto"] == DOMAIN for x in items),
        "registros": total,
        "registros_sin_gerente": without_manager,
    }
    return {"campana": {k: _fmt(v) for k, v in campaign.items()}, "gerentes": items, "resumen": summary,
            "envio_habilitado": mail._env_bool("SOX_MAIL_ENABLED"), "en_proceso": batch_running(),
            "modo_prueba": modo_prueba(), "correos_prueba": correos_prueba(),
            "copias": mail_config.cc(7)}


# ---------------------------------------------------------------- mensaje

DEFAULT_SUBJECT = "SOX Control 7 - Inicio de validación de accesos VPN | {periodo} | Fecha límite {fecha_limite}"
DEFAULT_BODY = (
    "Estimado(a) {gerente}:\n\n"
    "Se ha iniciado la campaña \"{campana}\" de validación semestral de accesos VPN "
    "(comunidades administradas en Check Point).\n\n"
    "- Período: {periodo}\n"
    "- Accesos VPN asociados a usted: {cantidad_vpn}\n"
    "- Fecha límite de validación: {fecha_limite}\n\n"
    "{linea_portal} para revisar cada acceso e indicar si debe mantenerse o eliminarse, "
    "agregando observaciones cuando corresponda.\n\n"
    "Este correo es una notificación de apertura. La validación solo queda registrada cuando "
    "usted la confirma en el portal.\n\n"
    "{tabla_vpn}"
    "Saludos."
)
DEFAULT_TEST_NOTE = ("*** CORREO DE PRUEBA ***\nEste aviso corresponde al gerente: {gerente}.\n"
                     "No se envió al gerente: el sistema está en modo prueba con destinatarios fijos.\n\n")


def compose(campaign, manager_name, vpn_count, vpns=None):
    """Asunto y cuerpo del aviso; los textos salen de correos.json > controles.7.aviso_gerentes."""
    config = mail_config.c7_notice()
    deadline = campaign["fecha_limite"]
    deadline_txt = deadline.strftime("%d/%m/%Y") if isinstance(deadline, datetime) else str(deadline or "por confirmar")
    period = f"{campaign['anio']} - {'primer' if int(campaign['semestre']) == 1 else 'segundo'} semestre"
    portal = os.getenv("SOX_PORTAL_URL", "").strip()
    values = {
        "gerente": manager_name, "campana": campaign["nombre"], "periodo": period,
        "cantidad_vpn": vpn_count, "fecha_limite": deadline_txt, "portal": portal,
        "linea_portal": (f"Ingrese al portal SOX ({portal}) con su cuenta corporativa" if portal.startswith("https://")
                         else "Ingrese al portal SOX con su cuenta corporativa"),
        "tabla_vpn": f"Sus VPN ({len(vpns)}):\n\n{_vpn_table(vpns)}\n\n" if vpns else "",
    }
    subject = mail_config.render(config["asunto"] or DEFAULT_SUBJECT, **values)
    body = mail_config.render(config["cuerpo"] or DEFAULT_BODY, **values)
    if modo_prueba():
        subject = f"[PRUEBA] {subject}"
        body = mail_config.render(config["nota_prueba"] or DEFAULT_TEST_NOTE, **values) + body
    return " ".join(subject.split())[:200], body


# ---------------------------------------------------------------- envío

def _check_ready(db, user, confirmar):
    if user.rol != "administrador":
        raise HTTPException(403, "Solo un administrador SOX puede notificar a los gerentes")
    if confirmar is not True:
        raise HTTPException(422, "Requiere confirmación explícita")
    if not mail._env_bool("SOX_MAIL_ENABLED"):
        raise HTTPException(503, "Envíos deshabilitados: configurar SOX_MAIL_ENABLED=true tras autorización")
    if 7 not in mail.enabled_controls():
        raise HTTPException(503, "Las notificaciones del Control 7 no están habilitadas (SOX_MAIL_CONTROLS)")
    if not mail.sender():
        raise HTTPException(503, "No hay remitente válido (correos.json > remitente)")
    if not mail.allowed_domains():
        raise HTTPException(503, "No hay dominios permitidos (correos.json > dominios_permitidos); envío bloqueado")
    mail._graph_paths()  # Falla aquí, antes de encolar, si la integración no está instalada
    campaign = active_campaign(db)
    if not campaign:
        raise HTTPException(409, "No existe una campaña activa")
    deadline = campaign["fecha_limite"]
    if isinstance(deadline, datetime) and deadline.date() < datetime.now().date():
        raise HTTPException(409, "La fecha límite de la campaña ya venció; no se envían avisos de apertura")
    return campaign


def start_batch(db, user, *, claves=None, confirmar=False):
    """Valida y devuelve qué gerentes se notificarán; el envío se ejecuta en segundo plano."""
    campaign = _check_ready(db, user, confirmar)
    data = preview(db)
    selected = set(claves or [])
    targets = [x for x in data["gerentes"] if x["enviable"] and (not selected or x["clave"] in selected)]
    if not targets:
        raise HTTPException(409, "No hay gerentes pendientes de notificar con un contacto válido")
    if not _batch_lock.acquire(blocking=False):
        raise HTTPException(409, "Ya hay un envío de notificaciones en curso")
    return campaign, [x["clave"] for x in targets]


def run_batch(campaign_id, claves, user_id, username):
    """Ejecución en segundo plano (BackgroundTasks). Libera el bloqueo al terminar."""
    from database.oracle_database import SessionLocal
    db = SessionLocal()
    sent = failed = skipped = 0
    try:
        campaign = active_campaign(db)
        if not campaign or campaign["id"] != campaign_id:
            logger.warning("Lote C7 cancelado: la campaña %s ya no está activa", campaign_id)
            return
        wanted = set(claves)
        managers, _, _ = _campaign_managers(db)
        vpns = _vpns_by_manager(db)
        for key, item in managers.items():
            if _key_hash(key) not in wanted:
                continue
            # Se recalcula por gerente: otro proceso pudo haberlo notificado mientras tanto.
            current = preview_one(db, campaign, key, item)
            if not current:
                skipped += 1
                continue
            try:
                ok = _send_one(db, campaign, item, current["correo"], current["intento"], user_id, username,
                               vpns.get(key, []))
                sent += 1 if ok else 0
                failed += 0 if ok else 1
            except Exception:
                db.rollback()
                failed += 1
                logger.exception("Aviso C7 a %s no enviado", item["gerente"])
    finally:
        db.close()
        _batch_lock.release()
        logger.info("Lote C7 campaña %s: enviados=%s fallidos=%s omitidos=%s", campaign_id, sent, failed, skipped)


def preview_one(db, campaign, key, item):
    contacts = {} if modo_prueba() else _contacts(db)
    contact_state, emails = _resolve_contact(contacts, key)
    if contact_state != READY:
        return None
    state, count = _notification_state(_notifications(db, campaign["id"]).get(key, []))
    if state not in (None, "FALLIDO"):
        return None
    return {"correo": emails, "intento": count + 1}


def _send_one(db, campaign, item, emails, attempt, user_id, username, vpns=None):
    subject, body = compose(campaign, item["gerente"], item["vpn"], vpns)
    taken = {x.casefold() for x in emails}
    copies = [x for x in mail.fixed_cc(7) if x.casefold() not in taken]
    email = ", ".join(emails)
    correlation = uuid4().hex
    idem = f"C7-{campaign['id']}-{_key_hash(item['key'])}-{attempt}"
    try:
        result = db.execute(text("""
            INSERT INTO AUTOM.SOX_MAIL_OUTBOX
              (CONTROL_NUMERO, ANIO, SEMESTRE, TIPO_EVIDENCIA, ORIGEN, IDEMPOTENCY_KEY, CORRELACION,
               EMISOR, DESTINATARIOS, CC, ASUNTO, CUERPO, ESTADO, SOLICITADO_POR, FECHA_SOLICITUD,
               ID_CAMPANA, GERENTE, GERENTE_KEY)
            VALUES (7, :p_anio, :p_sem, 'notificacion', 'CAMPANA', :p_idem, :p_corr,
                    :p_emisor, :p_para, :p_cc, :p_asunto, :p_cuerpo, 'PENDIENTE', :p_user, :p_fecha,
                    :p_camp, :p_gerente, :p_key)
            RETURNING ID INTO :p_returned
        """).bindparams(outparam("p_returned", Integer)), {
            "p_anio": campaign["anio"], "p_sem": campaign["semestre"], "p_idem": idem, "p_corr": correlation,
            "p_emisor": mail.sender(), "p_para": email, "p_cc": "; ".join(copies) or None,
            "p_asunto": subject, "p_cuerpo": body,
            "p_user": user_id, "p_fecha": mail._now(), "p_camp": campaign["id"],
            "p_gerente": item["gerente"][:200], "p_key": item["key"][:200]})
        value = result.out_parameters["p_returned"]
        outbox_id = int(value[0] if isinstance(value, (tuple, list)) else value)
        db.commit()
    except IntegrityError:
        db.rollback()  # Otro proceso ya registró este intento: no se envía de nuevo.
        return False

    footer = f"\n\n--\nEnviado desde SOX Dashboard por {username}. Referencia SOX: C7-{outbox_id}."
    try:
        code, out = mail._run_worker("enviar", {
            "emisor": mail.sender(), "destinatarios": list(emails), "cc": copies, "asunto": subject,
            "cuerpo": body + footer, "formato": "texto", "correlacion": correlation, "adjuntos": [],
        }, timeout=120)
    except subprocess.TimeoutExpired:
        mail._set_state(db, outbox_id, "PENDIENTE",
                        "Graph no respondió a tiempo. Verificar en Elementos enviados antes de reenviar.")
        return False
    except HTTPException as exc:
        mail._set_state(db, outbox_id, "FALLIDO", f"No se envió: {exc.detail}")
        return False
    if code != 0 or not out.get("ok"):
        logger.error("Aviso C7 #%s rechazado: %s", outbox_id, out.get("error"))
        mail._set_state(db, outbox_id, "FALLIDO", "Microsoft Graph no aceptó el envío")
        return False
    # Aviso de apertura: ACEPTADO es su estado final (no se archiva como evidencia).
    mail._set_state(db, outbox_id, "ACEPTADO", None, FECHA_ENVIO=mail._now(),
                    INTERNET_MESSAGE_ID=(out.get("internet_message_id") or None))
    return True


def start_summary(db):
    """Resumen sin envío para la respuesta de /campaign/start."""
    try:
        data = preview(db)
    except Exception:
        logger.exception("No se pudo preparar el resumen de notificaciones C7")
        return {"estado": "NO_DISPONIBLE",
                "mensaje": "No se pudo preparar el resumen de notificaciones; revisar desde Campañas."}
    summary = data["resumen"] or {}
    return {"estado": "PREPARADO", "resumen": summary,
            "mensaje": "Notificaciones preparadas, sin enviar. Revisar y enviar desde Campañas > Notificación a gerentes."}
