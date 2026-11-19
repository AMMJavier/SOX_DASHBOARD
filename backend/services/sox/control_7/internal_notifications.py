"""Control 7 - aviso de apertura a los gerentes de VPN INTERNAS (LDAP RDP / Aplicaciones).

Mismo comportamiento que el aviso de VPN externas (services/sox/control_7/notifications.py):
vista previa, un aviso por gerente (solo se reintenta si falló), modo prueba de correos.json,
envío en segundo plano y auditoría en AUTOM.SOX_MAIL_OUTBOX (ORIGEN='CAMPANA').

Diferencias:
  - Gerentes: AUTOM.SOX_C7_VPN_INTERNAS de la campaña activa (gerente según la cadena de jefes de Active Directory).
  - Correo: el de LDAP guardado en GERENTE_CORREO (sin buscar por nombre: no hay ambigüedad).
  - GERENTE_KEY = "int:<usuario>" y TIPO_EVIDENCIA = 'notificacion_interna': los avisos de
    internas no se mezclan con los de externas aunque sea el mismo gerente.
  - Textos: correos.json > controles.7.aviso_gerentes_internas (asunto / cuerpo).
"""
from datetime import datetime
import logging
import os
import re
import subprocess
import threading
import time
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import Integer, outparam, text
from sqlalchemy.exc import IntegrityError

from services.sox.common import mail_config
from services.sox.common import mail_service as mail
from services.sox.control_7 import notifications as ext

logger = logging.getLogger(__name__)
_batch_lock = threading.Lock()
KEY_PREFIX = "int:"
ACCESS = {"RDP": "RDP", "APLICACIONES": "Aplicaciones"}


def batch_running():
    return _batch_lock.locked()


def _managers(db, campaign_id):
    rows = db.execute(text("""
        SELECT GERENTE_USUARIO AS "usuario", MIN(GERENTE) AS "gerente", MAX(GERENTE_CORREO) AS "correo",
               COUNT(DISTINCT GERENTE_CORREO) AS "correos", COUNT(*) AS "accesos",
               SUM(CONFIRMACION) AS "confirmadas"
          FROM AUTOM.SOX_C7_VPN_INTERNAS
         WHERE ID_CAMPANA = :p_camp AND GERENTE_USUARIO IS NOT NULL
         GROUP BY GERENTE_USUARIO
    """), {"p_camp": campaign_id}).mappings()
    managers = {}
    for row in rows:
        key = KEY_PREFIX + row["usuario"].lower()
        managers[key] = {"key": key, "usuario": row["usuario"], "gerente": row["gerente"] or row["usuario"],
                         "correo": (row["correo"] or "").strip() or None, "ambiguo": int(row["correos"] or 0) > 1,
                         "vpn": int(row["accesos"] or 0), "confirmadas": int(row["confirmadas"] or 0)}
    counts = db.execute(text("""
        SELECT COUNT(*), NVL(SUM(CASE WHEN GERENTE_USUARIO IS NULL THEN 1 ELSE 0 END), 0)
          FROM AUTOM.SOX_C7_VPN_INTERNAS WHERE ID_CAMPANA = :p_camp
    """), {"p_camp": campaign_id}).first()
    return managers, int(counts[1] or 0), int(counts[0] or 0)


def _accounts(db, campaign_id, usuario):
    return [dict(r) for r in db.execute(text("""
        SELECT USUARIO AS "usuario", NOMBRE AS "nombre", TIPO_ACCESO AS "tipo"
          FROM AUTOM.SOX_C7_VPN_INTERNAS
         WHERE ID_CAMPANA = :p_camp AND LOWER(GERENTE_USUARIO) = LOWER(:p_user)
         ORDER BY NOMBRE, USUARIO, TIPO_ACCESO
    """), {"p_camp": campaign_id, "p_user": usuario}).mappings()]


def _contact(item):
    """(estado_contacto, correos) con la misma lista blanca y modo prueba que externas."""
    if ext.modo_prueba():
        emails = ext.correos_prueba()
    elif item["ambiguo"]:
        return ext.AMBIGUOUS, []
    elif not item["correo"]:
        return ext.NO_CONTACT, []
    else:
        emails = [item["correo"]]
    domains = mail.allowed_domains()
    valid = all(mail.EMAIL_RE.fullmatch(e) and e.rsplit("@", 1)[1].lower() in domains for e in emails)
    return (ext.READY if valid else ext.DOMAIN), emails


def _attempts(db, campaign_id):
    rows = db.execute(text("""
        SELECT GERENTE_KEY AS "key", ESTADO AS "estado", DESTINATARIOS AS "correo",
               DETALLE AS "detalle", FECHA_ENVIO AS "fecha_envio"
          FROM AUTOM.SOX_MAIL_OUTBOX
         WHERE ORIGEN = 'CAMPANA' AND ID_CAMPANA = :p_camp AND GERENTE_KEY LIKE 'int:%'
           AND (CASE WHEN ASUNTO LIKE '[PRUEBA]%' THEN 1 ELSE 0 END) = :p_test
         ORDER BY ID
    """), {"p_camp": campaign_id, "p_test": 1 if ext.modo_prueba() else 0}).mappings()
    result = {}
    for row in rows:
        result.setdefault(row["key"], []).append(dict(row))
    return result


def _row(item, attempts_by_key):
    contact_state, emails = _contact(item)
    all_attempts = attempts_by_key.get(item["key"], [])
    attempts = ext._for_current_email(all_attempts, emails)
    state, _ = ext._notification_state(attempts)
    last = attempts[-1] if attempts else None
    changed = bool(all_attempts) and not attempts and bool(emails)
    return {
        "gerente": item["gerente"], "clave": ext._key_hash(item["key"]), "vpn": item["vpn"],
        "pendientes": item["vpn"] - item["confirmadas"], "correo": ", ".join(emails) if emails else None,
        "contacto": contact_state, "notificacion": state, "intentos": len(all_attempts),
        "detalle": (f"Correo cambió desde el último aviso (antes: {all_attempts[-1]['correo']})"
                    if changed else (last["detalle"] if last else None)),
        "fecha_envio": ext._fmt(last["fecha_envio"]) if last else None,
        "enviable": contact_state == ext.READY and ext._can_send(state),
        "_emails": emails,
    }


def preview(db):
    campaign = ext.active_campaign(db)
    if not campaign:
        return {"campana": None, "gerentes": [], "resumen": None, "en_proceso": batch_running()}
    managers, without_manager, total = _managers(db, campaign["id"])
    attempts = _attempts(db, campaign["id"])
    items = [_row(item, attempts) for item in sorted(managers.values(), key=lambda x: x["gerente"])]
    summary = {
        "gerentes": len(items), "listos": sum(x["enviable"] for x in items),
        "notificados": sum(x["notificacion"] == "ACEPTADO" for x in items),
        "sin_confirmar": sum(x["notificacion"] == "PENDIENTE" for x in items),
        "fallidos": sum(x["notificacion"] == "FALLIDO" for x in items),
        "sin_contacto": sum(x["contacto"] == ext.NO_CONTACT for x in items),
        "ambiguos": sum(x["contacto"] == ext.AMBIGUOUS for x in items),
        "dominio_no_permitido": sum(x["contacto"] == ext.DOMAIN for x in items),
        "registros": total, "registros_sin_gerente": without_manager,
    }
    return {"campana": {k: ext._fmt(v) for k, v in campaign.items()},
            "gerentes": [{k: v for k, v in x.items() if not k.startswith("_")} for x in items],
            "resumen": summary, "envio_habilitado": mail._env_bool("SOX_MAIL_ENABLED"),
            "en_proceso": batch_running(), "modo_prueba": ext.modo_prueba(),
            "correos_prueba": ext.correos_prueba(), "copias": mail_config.cc(7)}


# ---------------------------------------------------------------- mensaje

DEFAULT_SUBJECT = "SOX Control 7 - Inicio de validación de accesos VPN internos | {periodo}"
DEFAULT_BODY = (
    "Estimado(a) {gerente}:\n\n"
    "Se ha iniciado la campaña \"{campana}\" de validación semestral de accesos VPN internos "
    "(grupos RDP y Aplicaciones) de las personas que dependen de usted en Active Directory.\n\n"
    "- Período: {periodo}\n"
    "- Accesos internos asociados a usted: {cantidad_vpn}\n"
    "- Fecha límite de validación: {fecha_limite}\n\n"
    "{linea_portal}, seleccione VPN internas y revise cada acceso indicando si debe mantenerse o "
    "eliminarse, con observaciones cuando corresponda.\n\n"
    "Este correo es una notificación de apertura. La validación solo queda registrada cuando "
    "usted la confirma en el portal.\n\n"
    "{tabla_vpn}"
    "Saludos."
)


def compose(campaign, manager_name, count, accounts):
    config = mail_config.c7_internal_notice()
    base = mail_config.c7_notice()
    deadline = campaign["fecha_limite"]
    deadline_txt = deadline.strftime("%d/%m/%Y") if isinstance(deadline, datetime) else str(deadline or "por confirmar")
    period = f"{campaign['anio']} - {'primer' if int(campaign['semestre']) == 1 else 'segundo'} semestre"
    portal = os.getenv("SOX_PORTAL_URL", "").strip()
    def clean(value):  # Python 3.9: sin barras invertidas dentro de los f-strings.
        return re.sub(r"\s+", " ", str(value or "-")).strip() or "-"
    lines = "\n".join(f"- {a['usuario']} | {clean(a['nombre'])} | {ACCESS.get(a['tipo'], a['tipo'])}"
                      for a in accounts)
    values = {
        "gerente": manager_name, "campana": campaign["nombre"], "periodo": period, "cantidad_vpn": count,
        "fecha_limite": deadline_txt, "portal": portal,
        "linea_portal": (f"Ingrese al portal SOX ({portal}) con su cuenta corporativa" if portal.startswith("https://")
                         else "Ingrese al portal SOX con su cuenta corporativa"),
        "tabla_vpn": f"Accesos internos ({len(accounts)}):\n\n{lines}\n\n" if accounts else "",
    }
    subject = mail_config.render(config["asunto"] or DEFAULT_SUBJECT, **values)
    body = mail_config.render(config["cuerpo"] or DEFAULT_BODY, **values)
    if ext.modo_prueba():
        subject = f"[PRUEBA] {subject}"
        body = mail_config.render(base["nota_prueba"] or ext.DEFAULT_TEST_NOTE, **values) + body
    return " ".join(subject.split())[:200], body


# ---------------------------------------------------------------- envío

def start_batch(db, user, *, claves=None, confirmar=False):
    campaign = ext._check_ready(db, user, confirmar)  # Mismas validaciones que externas.
    data = preview(db)
    selected = set(claves or [])
    targets = [x for x in data["gerentes"] if x["enviable"] and (not selected or x["clave"] in selected)]
    if not targets:
        raise HTTPException(409, "No hay gerentes de VPN internas pendientes de notificar con un correo válido")
    if not _batch_lock.acquire(blocking=False):
        raise HTTPException(409, "Ya hay un envío de notificaciones de VPN internas en curso")
    return campaign, [x["clave"] for x in targets]


def run_batch(campaign_id, claves, user_id, username):
    from database.oracle_database import SessionLocal
    db = SessionLocal()
    sent = failed = skipped = 0
    start = time.monotonic()
    mail.console(f"AVISOS C7 INTERNAS LOTE INICIO | campaña={campaign_id} gerentes={len(claves)} usuario={username} "
                 f"modo={'PRUEBA' if ext.modo_prueba() else 'REAL (correo LDAP)'}")
    try:
        campaign = ext.active_campaign(db)
        if not campaign or campaign["id"] != campaign_id:
            mail.console(f"AVISOS C7 INTERNAS LOTE CANCELADO: la campaña {campaign_id} ya no está activa")
            return
        wanted = set(claves)
        managers, _, _ = _managers(db, campaign_id)
        for key, item in managers.items():
            if ext._key_hash(key) not in wanted:
                continue
            current = _row(item, _attempts(db, campaign_id))  # Se recalcula: otro proceso pudo notificarlo.
            if not current["enviable"]:
                skipped += 1
                continue
            try:
                ok = _send_one(db, campaign, item, current["_emails"], user_id, username,
                               _accounts(db, campaign_id, item["usuario"]))
                sent += 1 if ok else 0
                failed += 0 if ok else 1
                mail.console(f"AVISO C7 INTERNAS {'ENVIADO' if ok else 'NO ENVIADO'} | gerente={item['gerente']!r}")
            except Exception as exc:
                db.rollback()
                failed += 1
                mail.console(f"AVISO C7 INTERNAS ERROR | gerente={item['gerente']!r}: {type(exc).__name__}: {exc}")
                logger.exception("Aviso C7 internas a %s no enviado", item["gerente"])
    finally:
        db.close()
        _batch_lock.release()
        mail.console(f"AVISOS C7 INTERNAS LOTE FIN | enviados={sent} fallidos={failed} omitidos={skipped} | "
                     f"{time.monotonic() - start:.2f}s")


def _send_one(db, campaign, item, emails, user_id, username, accounts):
    subject, body = compose(campaign, item["gerente"], item["vpn"], accounts)
    taken = {x.casefold() for x in emails}
    copies = [x for x in mail.fixed_cc(7) if x.casefold() not in taken]
    correlation = uuid4().hex
    attempt = ext._attempts_total(db, campaign["id"], item["key"]) + 1
    idem = (f"C7IP-{campaign['id']}-{ext._key_hash(item['key'])}-{correlation[:12]}" if ext.modo_prueba()
            else f"C7I-{campaign['id']}-{ext._key_hash(item['key'])}-{attempt}")
    try:
        result = db.execute(text("""
            INSERT INTO AUTOM.SOX_MAIL_OUTBOX
              (CONTROL_NUMERO, ANIO, SEMESTRE, TIPO_EVIDENCIA, ORIGEN, IDEMPOTENCY_KEY, CORRELACION,
               EMISOR, DESTINATARIOS, CC, ASUNTO, CUERPO, ESTADO, SOLICITADO_POR, FECHA_SOLICITUD,
               ID_CAMPANA, GERENTE, GERENTE_KEY)
            VALUES (7, :p_anio, :p_sem, 'notificacion_interna', 'CAMPANA', :p_idem, :p_corr,
                    :p_emisor, :p_para, :p_cc, :p_asunto, :p_cuerpo, 'PENDIENTE', :p_user, :p_fecha,
                    :p_camp, :p_gerente, :p_key)
            RETURNING ID INTO :p_returned
        """).bindparams(outparam("p_returned", Integer)), {
            "p_anio": campaign["anio"], "p_sem": campaign["semestre"], "p_idem": idem, "p_corr": correlation,
            "p_emisor": mail.sender(), "p_para": ", ".join(emails), "p_cc": "; ".join(copies) or None,
            "p_asunto": subject, "p_cuerpo": body, "p_user": user_id, "p_fecha": mail._now(),
            "p_camp": campaign["id"], "p_gerente": item["gerente"][:200], "p_key": item["key"][:200]})
        value = result.out_parameters["p_returned"]
        outbox_id = int(value[0] if isinstance(value, (tuple, list)) else value)
        db.commit()
    except IntegrityError:
        db.rollback()  # Otro proceso ya registró este intento: no se envía de nuevo.
        return False
    footer = f"\n\n--\nEnviado desde SOX Dashboard por {username}. Referencia SOX: C7I-{outbox_id}."
    try:
        code, out = mail._run_worker("enviar", {
            "emisor": mail.sender(), "destinatarios": list(emails), "cc": copies, "asunto": subject,
            "cuerpo": body + footer, "formato": "texto", "correlacion": correlation, "adjuntos": [],
        }, timeout=120)
    except subprocess.TimeoutExpired:
        mail._set_state(db, outbox_id, "PENDIENTE", "Graph no respondió a tiempo. Verificar en Elementos enviados antes de reenviar.")
        return False
    except HTTPException as exc:
        mail._set_state(db, outbox_id, "FALLIDO", f"No se envió: {exc.detail}")
        return False
    if code != 0 or not out.get("ok"):
        mail._set_state(db, outbox_id, "FALLIDO", "Microsoft Graph no aceptó el envío")
        return False
    mail._set_state(db, outbox_id, "ACEPTADO", None, FECHA_ENVIO=mail._now(),
                    INTERNET_MESSAGE_ID=(out.get("internet_message_id") or None))
    return True
