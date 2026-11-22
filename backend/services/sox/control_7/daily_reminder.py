"""Control 7 - recordatorio diario a los gerentes con VPN por validar (externas + internas).

- Un solo correo por gerente y por día, con la cantidad que le falta validar.
- Desde el día siguiente al aviso de apertura y hasta la fecha límite de la campaña.
- Solo a gerentes que YA recibieron el aviso de apertura (externas o internas): así el
  administrador decide cuándo empieza y nunca llega un recordatorio antes que el aviso.
- Quien ya respondió todas sus VPN no lo recibe. Una VPN reportada (Otro / No pertenece) ya fue
  respondida: la tiene que corregir el administrador, no se le recuerda al gerente.
- Sin duplicados: la clave C7D-<campaña>-<gerente>-<AAAAMMDD> es única en SOX_MAIL_OUTBOX,
  aunque se reinicie la API o haya varios procesos.
Configuración: correos.json > controles.7.recordatorio_diario (apagado por defecto).
"""
from __future__ import annotations  # Python 3.9 en el servidor

from datetime import datetime, timedelta
import os
import subprocess
import threading
import time
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import Integer, outparam, text
from sqlalchemy.exc import IntegrityError

from services.sox.common import mail_config
from services.sox.common import mail_service as mail
from services.sox.control_7 import internal_notifications as internal
from services.sox.control_7 import notifications as ext

_lock = threading.Lock()
_done = None          # (campaña, día) ya recorrido por este proceso
_last_reason = None   # evita repetir cada minuto la misma traza

DEFAULT_SUBJECT = "SOX Control 7 - Recordatorio: {pendientes} VPN por validar | {periodo}"
DEFAULT_BODY = (
    "Estimado(a) {gerente}:\n\n"
    "Le recordamos que tiene {pendientes} VPN por validar en la campaña \"{campana}\".\n\n"
    "- VPN externas pendientes: {pendientes_externas}\n"
    "- VPN internas pendientes: {pendientes_internas}\n"
    "- Fecha límite de validación: {fecha_limite} (faltan {dias_restantes} día(s))\n\n"
    "{linea_portal} para validar sus accesos. Este recordatorio se envía cada día hasta que "
    "complete la validación.\n\n"
    "Saludos."
)


def _skip(reason):
    global _last_reason
    if reason != _last_reason:
        _last_reason = reason
        mail.console(f"RECORDATORIO C7: no se envía | {reason}")
    return 0


# ---------------------------------------------------------------- pendientes

def pending_by_manager(db, campaign):
    """Gerentes con VPN por validar, unidos por correo: {correo: {...}}.

    Devuelve (gerentes, sin_correo): los que no tienen un correo único no se pueden avisar.
    """
    result, without_mail = {}, []

    def add(email, name, key, field, count):
        item = result.setdefault(email.casefold(), {
            "correo": email, "gerente": name, "externas": 0, "internas": 0, "claves": set()})
        item[field] += count
        item["claves"].add(key)

    managers, _, _ = ext._campaign_managers(db)
    contacts = ext._contacts(db)
    for key, item in managers.items():
        count = item["vpn"] - item["confirmadas"] - item["reportadas"]
        if count <= 0:
            continue
        emails = list(contacts.get(key, {}).values())
        if len(emails) == 1:
            add(emails[0], item["gerente"], key, "externas", count)
        else:
            without_mail.append(item["gerente"])
    managers, _, _ = internal._managers(db, campaign["id"])
    for key, item in managers.items():
        count = item["vpn"] - item["confirmadas"] - item["reportadas"]
        if count <= 0:
            continue
        if item["correo"] and not item["ambiguo"]:
            add(item["correo"], item["gerente"], key, "internas", count)
        else:
            without_mail.append(item["gerente"])
    return result, without_mail


def _opened(attempts, now_utc):
    """El aviso de apertura se aceptó hace al menos 12 horas (el primer recordatorio es al otro día)."""
    limit = now_utc - timedelta(hours=12)
    return any(a["estado"] == "ACEPTADO" and a["fecha_envio"] and a["fecha_envio"] <= limit for a in attempts)


# ---------------------------------------------------------------- mensaje

def compose(campaign, item, today):
    config = mail_config.c7_daily_reminder()
    deadline = campaign["fecha_limite"]
    portal = os.getenv("SOX_PORTAL_URL", "").strip()
    values = {
        "gerente": item["gerente"], "campana": campaign["nombre"],
        "periodo": f"{campaign['anio']} - {'primer' if int(campaign['semestre']) == 1 else 'segundo'} semestre",
        "pendientes": item["externas"] + item["internas"], "pendientes_externas": item["externas"],
        "pendientes_internas": item["internas"], "fecha_limite": deadline.strftime("%d/%m/%Y"),
        "dias_restantes": (deadline.date() - today).days, "portal": portal,
        "linea_portal": (f"Ingrese al portal SOX ({portal}) con su cuenta corporativa" if portal.startswith("https://")
                         else "Ingrese al portal SOX con su cuenta corporativa"),
    }
    subject = mail_config.render(config["asunto"] or DEFAULT_SUBJECT, **values)
    body = mail_config.render(config["cuerpo"] or DEFAULT_BODY, **values)
    if ext.modo_prueba():
        subject = f"[PRUEBA] {subject}"
        body = mail_config.render(mail_config.c7_notice()["nota_prueba"] or ext.DEFAULT_TEST_NOTE, **values) + body
    return " ".join(subject.split())[:200], body


# ---------------------------------------------------------------- envío

def _allowed(addresses):
    domains = mail.allowed_domains()
    return all(mail.EMAIL_RE.fullmatch(e) and e.rsplit("@", 1)[1].lower() in domains for e in addresses)


def _send(db, campaign, item, today, user):
    """True = enviado, False = falló, None = ya estaba registrado hoy o no corresponde."""
    emails = ext.correos_prueba() if ext.modo_prueba() else [item["correo"]]
    if not emails or not _allowed(emails):
        mail.console(f"RECORDATORIO C7 OMITIDO | gerente={item['gerente']!r}: dominio no autorizado")
        return None
    taken = {x.casefold() for x in emails}
    copies = [x for x in mail_config.c7_daily_reminder()["copias"] if x.casefold() not in taken]
    if not _allowed(copies):
        mail.console("RECORDATORIO C7: se omiten las copias de recordatorio_diario (dominio no autorizado)")
        copies = []
    key = "dia:" + item["correo"].casefold()
    prefix = "C7DP" if ext.modo_prueba() else "C7D"
    idem = f"{prefix}-{campaign['id']}-{ext._key_hash(key)}-{today:%Y%m%d}"
    if db.execute(text("SELECT COUNT(*) FROM AUTOM.SOX_MAIL_OUTBOX WHERE IDEMPOTENCY_KEY = :p_idem"),
                  {"p_idem": idem}).scalar():
        return None
    subject, body = compose(campaign, item, today)
    correlation = uuid4().hex
    try:
        result = db.execute(text("""
            INSERT INTO AUTOM.SOX_MAIL_OUTBOX
              (CONTROL_NUMERO, ANIO, SEMESTRE, TIPO_EVIDENCIA, ORIGEN, IDEMPOTENCY_KEY, CORRELACION,
               EMISOR, DESTINATARIOS, CC, ASUNTO, CUERPO, ESTADO, SOLICITADO_POR, FECHA_SOLICITUD,
               ID_CAMPANA, GERENTE, GERENTE_KEY)
            VALUES (7, :p_anio, :p_sem, 'recordatorio_diario', 'CAMPANA', :p_idem, :p_corr,
                    :p_emisor, :p_para, :p_cc, :p_asunto, :p_cuerpo, 'PENDIENTE', :p_user, :p_fecha,
                    :p_camp, :p_gerente, :p_key)
            RETURNING ID INTO :p_returned
        """).bindparams(outparam("p_returned", Integer)), {
            "p_anio": campaign["anio"], "p_sem": campaign["semestre"], "p_idem": idem, "p_corr": correlation,
            "p_emisor": mail.sender(), "p_para": ", ".join(emails), "p_cc": "; ".join(copies) or None,
            "p_asunto": subject, "p_cuerpo": body, "p_user": user[0], "p_fecha": mail._now(),
            "p_camp": campaign["id"], "p_gerente": item["gerente"][:200], "p_key": key[:200]})
        value = result.out_parameters["p_returned"]
        outbox_id = int(value[0] if isinstance(value, (tuple, list)) else value)
        db.commit()
    except IntegrityError:
        db.rollback()  # Otro proceso ya registró el recordatorio de hoy.
        return None
    footer = f"\n\n--\nEnviado automáticamente desde SOX Dashboard. Referencia SOX: C7D-{outbox_id}."
    try:
        code, out = mail._run_worker("enviar", {
            "emisor": mail.sender(), "destinatarios": list(emails), "cc": copies, "asunto": subject,
            "cuerpo": body + footer, "formato": "texto", "correlacion": correlation, "adjuntos": [],
        }, timeout=120)
    except subprocess.TimeoutExpired:
        mail._set_state(db, outbox_id, "PENDIENTE",
                        "Graph no respondió a tiempo. Verificar en Elementos enviados.")
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


def run_once(now=None, db=None):
    """Revisa si hoy toca y envía. Se llama cada minuto; devuelve cuántos correos salieron."""
    global _done
    now = now or datetime.now()
    config = mail_config.c7_daily_reminder()
    if not config["activo"] or now.hour * 60 + now.minute < config["minuto_del_dia"]:
        return 0
    if not mail._env_bool("SOX_MAIL_ENABLED") or 7 not in mail.enabled_controls():
        return _skip("el envío del Control 7 está deshabilitado (SOX_MAIL_ENABLED / SOX_MAIL_CONTROLS)")
    if not mail.sender() or not mail.allowed_domains():
        return _skip("falta el remitente o los dominios permitidos en correos.json")
    if not _lock.acquire(blocking=False):
        return 0
    own_db = db is None
    try:
        if own_db:
            from database.oracle_database import SessionLocal
            db = SessionLocal()
        campaign = ext.active_campaign(db)
        if not campaign:
            return _skip("no hay una campaña activa")
        today = now.date()
        if _done == (campaign["id"], today):
            return 0
        deadline = campaign["fecha_limite"]
        if not isinstance(deadline, datetime) or now > deadline:
            return _skip(f"venció la fecha límite de la campaña {campaign['id']}")
        mail._graph_paths()  # Falla aquí, antes de registrar, si la integración no está instalada.

        from services.sox.common.reminder_scheduler import _system_user
        user = _system_user(db)
        pending, without_mail = pending_by_manager(db, campaign)
        notices = ext._notifications(db, campaign["id"])  # avisos de apertura (externas e internas)
        start, now_utc = time.monotonic(), mail._now()
        sent = failed = not_opened = already = 0
        for item in sorted(pending.values(), key=lambda x: x["gerente"]):
            if not any(_opened(notices.get(key, []), now_utc) for key in item["claves"]):
                not_opened += 1
                continue
            try:
                ok = _send(db, campaign, item, today, user)
            except Exception as exc:  # Un gerente con error no detiene a los demás.
                db.rollback()
                ok = False
                mail.console(f"RECORDATORIO C7 ERROR | gerente={item['gerente']!r}: {type(exc).__name__}: {exc}")
            sent += ok is True
            failed += ok is False
            already += ok is None
        _done = (campaign["id"], today)
        mail.console(
            f"RECORDATORIO C7 FIN | campaña={campaign['id']} modo={'PRUEBA' if ext.modo_prueba() else 'REAL'} "
            f"con_pendientes={len(pending)} enviados={sent} fallidos={failed} omitidos={already} "
            f"sin_aviso_de_apertura={not_opened} sin_correo={len(without_mail)} | {mail.elapsed(start)}")
        return sent
    finally:
        if own_db and db is not None:
            db.close()
        _lock.release()
