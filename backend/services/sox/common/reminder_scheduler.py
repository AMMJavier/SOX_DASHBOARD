"""Envío automático de recordatorios y alertas de evidencia faltante por control.

Configuración (backend/config/correos.json, se relee sola):
  "automatico": {"activo": true, "hora_desde": "09:15", "usuario": "dev_user"}
  "controles": {"1": {"calendario": {
        "recordatorios": ["06-15", "11-15"],     # días de envío (MM-DD)
        "fecha_tope": ["12-15"],                 # anual: 1 fecha; semestral: 1 por semestre
        "alerta_dias_antes": 14,                 # alerta si falta evidencia N días antes
        "adjuntar_ultimo": {"controles": [2], "tipos": ["plan"]}   # opcional
  }}}

Funcionamiento:
  - Un hilo dentro de la API revisa cada minuto y envía desde "hora_desde" (HH:MM).
  - Recordatorio: se envía el día indicado o, si la API estuvo apagada, hasta 7 días después.
  - Alerta: entre (fecha_tope - alerta_dias_antes) y la fecha tope, solo si el período no
    tiene ninguna evidencia cargada o verificada.
  - Cada envío usa una clave fija en SOX_MAIL_OUTBOX (AUTO-R-... / AUTO-A-...): aunque se
    reinicie la API o haya varios procesos, el mismo recordatorio nunca sale dos veces.
  - Con "activo": false no se envía nada (el botón manual sigue funcionando).
"""
import threading
import time
from datetime import date, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import text

from services.sox.common import mail_config
from services.sox.common import mail_service as mail
from services.sox.common.reminder_service import SEMESTER_CONTROLS, controls, deliver

CHECK_EVERY_SECONDS = 60  # Revisa cada minuto: permite horas exactas como "09:15".
REMINDER_GRACE_DAYS = 7
_started = False
_lock = threading.Lock()


# ---------------------------------------------------------------- calendario

def _to_date(year, mmdd):
    month, day = (int(x) for x in mmdd.split("-"))
    while True:  # 02-29 en años no bisiestos -> 02-28
        try:
            return date(year, month, day)
        except ValueError:
            day -= 1


def deadline_for(control, anio, semestre=None):
    """Fecha tope del período (año, o año+semestre en controles semestrales); None si no hay."""
    tops = [_to_date(anio, d) for d in mail_config.calendar(control)["fecha_tope"]]
    if not tops:
        return None
    if control in SEMESTER_CONTROLS and semestre in (1, 2):
        in_semester = [d for d in tops if (d.month <= 6) == (semestre == 1)]
        return in_semester[-1] if in_semester else None
    return tops[-1]


def evidence_count(db, control, anio, semestre=None):
    row = db.execute(text("""
        SELECT COUNT(*) FROM AUTOM.SOX_CONTROL_EVIDENCIAS
         WHERE CONTROL_NUMERO = :c AND ANIO = :a
           AND (:s IS NULL OR SEMESTRE = :s)
           AND ESTADO IN ('CARGADA', 'VERIFICADA')
    """), {"c": control, "a": anio, "s": semestre}).scalar()
    return int(row or 0)


def period_status(db, control, anio, semestre=None, today=None):
    """Estado del período para la pantalla: fecha tope, días restantes y si venció."""
    today = today or date.today()
    cal = mail_config.calendar(control)
    semestre = semestre if control in SEMESTER_CONTROLS else None
    top = deadline_for(control, anio, semestre)
    return {
        "control": control, "anio": anio, "semestre": semestre,
        "fecha_tope": top.isoformat() if top else None,
        "dias_restantes": (top - today).days if top else None,
        "vencido": bool(top and today > top),
        "evidencias": evidence_count(db, control, anio, semestre),
        "alerta_dias_antes": cal["alerta_dias_antes"],
        "recordatorios": cal["recordatorios"],
        "automatico": mail_config.automatic()["activo"],
    }


# ---------------------------------------------------------------- envío automático

def _system_user(db):
    """Usuario que figura como solicitante de los envíos automáticos (SOLICITADO_POR)."""
    wanted = mail_config.automatic()["usuario"]
    if wanted:
        row = db.execute(text("SELECT ID, USERNAME FROM AUTOM.USUARIOS WHERE LOWER(USERNAME) = LOWER(:u)"),
                         {"u": wanted}).first()
        if row:
            return int(row[0]), row[1]
        mail.console(f"AUTOMATICO: el usuario {wanted!r} de correos.json no existe; se usa un administrador activo")
    row = db.execute(text("""
        SELECT ID, USERNAME FROM AUTOM.USUARIOS WHERE ROL = 'administrador' AND ACTIVO = 1
         ORDER BY ID FETCH FIRST 1 ROWS ONLY
    """)).first()
    if not row:
        raise RuntimeError("No hay un usuario administrador activo para registrar los envíos automáticos")
    return int(row[0]), row[1]


def _already_registered(db, key):
    """Consulta liviana: si la clave ya está en SOX_MAIL_OUTBOX no se vuelve a armar el correo."""
    return bool(db.execute(text("SELECT COUNT(*) FROM AUTOM.SOX_MAIL_OUTBOX WHERE IDEMPOTENCY_KEY = :k"),
                           {"k": key}).scalar())


def _send(db, user, *, control, anio, semestre, kind, key, extra=None):
    if _already_registered(db, key):
        return
    start = time.monotonic()
    try:
        result = deliver(db, control=control, anio=anio, semestre=semestre, referencia="Envío automático",
                         user_id=user[0], username=f"{user[1]} (automático)", kind=kind,
                         idempotency_key=key, extra=extra)
        if result.get("repetido"):
            return
        mail.console(f"AUTOMATICO {kind.upper()} Control {control} ENVIADA ({key}) en {mail.elapsed(start)}")
    except HTTPException as exc:
        mail.console(f"AUTOMATICO {kind.upper()} Control {control} NO ENVIADA ({key}) | HTTP {exc.status_code}: {exc.detail}")
    except Exception as exc:  # Un control con error no detiene a los demás.
        db.rollback()
        mail.console(f"AUTOMATICO {kind.upper()} Control {control} ERROR ({key}) | {type(exc).__name__}: {exc}")


def run_once(now=None, db=None):
    """Revisa y envía lo que corresponda hoy. Devuelve cuántos envíos se intentaron."""
    now = now or datetime.now()
    auto = mail_config.automatic()
    if not auto["activo"] or now.hour * 60 + now.minute < auto["minuto_del_dia"]:
        return 0
    today = now.date()
    own_db = db is None
    if own_db:
        from database.oracle_database import SessionLocal
        db = SessionLocal()
    attempts = 0
    try:
        user = _system_user(db)
        for control in sorted(controls()):
            cal = mail_config.calendar(control)
            # 1) Recordatorios programados
            for mmdd in cal["recordatorios"]:
                when = _to_date(today.year, mmdd)
                if when <= today <= when + timedelta(days=REMINDER_GRACE_DAYS):
                    semestre = (1 if when.month <= 6 else 2) if control in SEMESTER_CONTROLS else None
                    attempts += 1
                    _send(db, user, control=control, anio=today.year, semestre=semestre, kind="notificacion",
                          key=f"AUTO-R-C{control}-{today.year}-{mmdd}")
            # 2) Alerta de evidencia faltante antes de la fecha tope
            days = cal["alerta_dias_antes"]
            if days and cal["fecha_tope"]:
                semestre = (1 if today.month <= 6 else 2) if control in SEMESTER_CONTROLS else None
                top = deadline_for(control, today.year, semestre)
                if top and top - timedelta(days=days) <= today <= top and evidence_count(db, control, today.year, semestre) == 0:
                    attempts += 1
                    _send(db, user, control=control, anio=today.year, semestre=semestre, kind="alerta",
                          key=f"AUTO-A-C{control}-{top.isoformat()}",
                          extra={"fecha_tope": top.strftime("%d/%m/%Y"), "dias_restantes": (top - today).days})
    finally:
        if own_db:
            db.close()
    return attempts


def _loop():
    time.sleep(15)  # Deja terminar el arranque de la API.
    while True:
        try:
            run_once()
        except Exception as exc:
            mail.console(f"AUTOMATICO: error en la revisión programada | {type(exc).__name__}: {exc}")
        time.sleep(CHECK_EVERY_SECONDS)


def start():
    """Arranca el hilo una sola vez por proceso (se llama al iniciar la API)."""
    global _started
    with _lock:
        if _started:
            return
        _started = True
    auto = mail_config.automatic()
    mail.console(f"AUTOMATICO: programador iniciado (revisa cada {CHECK_EVERY_SECONDS} s) | "
                 f"activo={auto['activo']} hora_desde={auto['hora_desde']}")
    threading.Thread(target=_loop, name="sox-recordatorios", daemon=True).start()
