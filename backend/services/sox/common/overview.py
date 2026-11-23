"""Resumen general SOX: estado de los controles 1, 2, 3, 5, 6 y 7 en una sola consulta.

Período vigente: año en curso; los controles semestrales (3 y 6) usan el semestre en curso
y el Control 7 su campaña activa. Cada control se lee por separado: si una tabla falta o una
consulta falla, ese control muestra el error y los demás se ven igual.
"""
from __future__ import annotations  # Python 3.9 en el servidor

from datetime import date, datetime
import logging

from sqlalchemy import text

from services.sox.common.reminder_scheduler import period_status
from services.sox.common.reminder_service import SEMESTER_CONTROLS

logger = logging.getLogger(__name__)

NAMES = {
    1: "Cambios en la SIS016",
    2: "Plan de Seguridad OK de Gerencia",
    3: "Revisión del Plan de Seguridades",
    5: "Administradores del Firewall",
    6: "Personal cesante vs VPN",
    7: "Evidencias VPN (externas e internas)",
}
SENT = ("ACEPTADO", "ARCHIVANDO", "ARCHIVADO")
REPLY_ORDER = {"APROBADO": 3, "RESPONDIDO": 2, "PENDIENTE": 1}


def _iso(value):
    return value.isoformat() if isinstance(value, (datetime, date)) else value


def _period(control, today):
    semestre = (1 if today.month <= 6 else 2) if control in SEMESTER_CONTROLS else None
    label = f"{'Primer' if semestre == 1 else 'Segundo'} semestre {today.year}" if semestre else f"Año {today.year}"
    return today.year, semestre, label


def _mails(db, control, anio, semestre):
    """Último aviso (notificación/recordatorio) y último correo formal del período, y la confirmación."""
    rows = db.execute(text("""
        SELECT ORIGEN AS "origen", TIPO_EVIDENCIA AS "tipo", ESTADO AS "estado", ASUNTO AS "asunto",
               FECHA_SOLICITUD AS "fecha_solicitud", FECHA_ENVIO AS "fecha_envio",
               CODIGO AS "codigo", ESTADO_RESPUESTA AS "estado_respuesta", FECHA_RESPUESTA AS "fecha_respuesta"
          FROM AUTOM.SOX_MAIL_OUTBOX
         WHERE CONTROL_NUMERO = :p_c AND ANIO = :p_a AND ORIGEN IN ('MANUAL', 'RECORDATORIO')
           AND ((:p_s IS NULL AND SEMESTRE IS NULL) OR SEMESTRE = :p_s)
         ORDER BY FECHA_SOLICITUD DESC, ID DESC
    """), {"p_c": control, "p_a": anio, "p_s": semestre}).mappings().all()
    rows = [{k: _iso(v) for k, v in dict(r).items()} for r in rows]
    notice = next((r for r in rows if r["origen"] == "RECORDATORIO" and r["tipo"] != "alerta"), None)
    alert = next((r for r in rows if r["origen"] == "RECORDATORIO" and r["tipo"] == "alerta"), None)
    formal = next((r for r in rows if r["origen"] == "MANUAL"), None)
    coded = [r for r in rows if r["codigo"] and r["estado"] in SENT]
    best = max(coded, key=lambda r: REPLY_ORDER.get(r["estado_respuesta"] or "PENDIENTE", 0), default=None)
    return {
        "notificacion": notice and {"enviada": notice["estado"] in SENT, "estado": notice["estado"],
                                    "fecha": notice["fecha_envio"] or notice["fecha_solicitud"]},
        "alerta": alert and {"enviada": alert["estado"] in SENT, "fecha": alert["fecha_envio"] or alert["fecha_solicitud"]},
        "correo_formal": formal and {"enviado": formal["estado"] in SENT, "estado": formal["estado"],
                                     "asunto": formal["asunto"], "fecha": formal["fecha_envio"] or formal["fecha_solicitud"]},
        # Confirmación por respuesta al correo con código: APROBADO, RESPONDIDO (revisar) o PENDIENTE.
        "confirmacion": best and {"estado": best["estado_respuesta"] or "PENDIENTE", "codigo": best["codigo"],
                                  "fecha": best["fecha_respuesta"]},
        "correos_enviados": sum(r["estado"] in SENT for r in rows),
    }


def _documental(db, control, today):
    anio, semestre, label = _period(control, today)
    item = {"control": control, "nombre": NAMES[control], "periodo": label, "anio": anio, "semestre": semestre,
            "frecuencia": "Semestral" if semestre else ("Por evento" if control == 5 else "Anual")}
    item.update({k: v for k, v in period_status(db, control, anio, semestre, today).items()
                 if k in ("fecha_tope", "dias_restantes", "vencido", "evidencias")})
    item.update(_mails(db, control, anio, semestre))
    if control == 5:
        item["eventos"] = int(db.execute(text(
            "SELECT COUNT(*) FROM AUTOM.SOX_CONTROL5_EVENTOS WHERE ANIO = :p_a"), {"p_a": anio}).scalar() or 0)
    if control == 6:
        row = db.execute(text("""
            SELECT CREADO_EN AS "fecha", TOTAL_RRHH AS "total_rrhh", COINCIDENCIAS AS "coincidencias",
                   SIN_COINCIDENCIA AS "sin_coincidencia", AMBIGUOS AS "ambiguos"
              FROM AUTOM.SOX_C6_CONCILIACIONES WHERE ANIO = :p_a AND SEMESTRE = :p_s
             ORDER BY CREADO_EN DESC FETCH FIRST 1 ROWS ONLY
        """), {"p_a": anio, "p_s": semestre}).mappings().first()
        item["conciliacion"] = row and {k: _iso(v) for k, v in dict(row).items()}
    return item


def _control7(db):
    from services.sox.control_7 import internal_notifications as internal
    from services.sox.control_7 import notifications as ext
    from services.sox.control_7.decision_rules import REPORTED_SQL

    campaign = ext.active_campaign(db)
    item = {"control": 7, "nombre": NAMES[7], "frecuencia": "Semestral (campaña)", "campana": None}
    if not campaign:
        return item
    deadline = campaign["fecha_limite"]
    item.update({
        "campana": campaign["nombre"], "anio": campaign["anio"], "semestre": campaign["semestre"],
        "periodo": f"{'Primer' if int(campaign['semestre']) == 1 else 'Segundo'} semestre {campaign['anio']}",
        "fecha_inicio": _iso(campaign["fecha_inicio"]), "fecha_tope": _iso(deadline),
        "dias_restantes": (deadline.date() - date.today()).days if isinstance(deadline, datetime) else None,
        "vencido": bool(isinstance(deadline, datetime) and datetime.now() > deadline),
    })
    ext_row = db.execute(text(f"""
        SELECT COUNT(*) AS "total",
               NVL(SUM(CASE WHEN NVL(CONFIRMACION, 0) = 1 AND NOT ({REPORTED_SQL}) THEN 1 ELSE 0 END), 0) AS "confirmadas",
               NVL(SUM(CASE WHEN {REPORTED_SQL} THEN 1 ELSE 0 END), 0) AS "reportadas"
          FROM (SELECT t.*, ROW_NUMBER() OVER (PARTITION BY CHECKPOINT_UID ORDER BY FECHA_ALMACENADO DESC) rn
                  FROM AUTOM.CHECKPOINT_TRANSFORM t)
         WHERE rn = 1
    """)).mappings().first()
    int_row = db.execute(text("""
        SELECT COUNT(*) AS "total",
               NVL(SUM(CASE WHEN CONFIRMACION = 1 AND ESTADO NOT IN ('no pertenece', 'otro') THEN 1 ELSE 0 END), 0) AS "confirmadas",
               NVL(SUM(CASE WHEN ESTADO IN ('no pertenece', 'otro') THEN 1 ELSE 0 END), 0) AS "reportadas"
          FROM AUTOM.SOX_C7_VPN_INTERNAS WHERE ID_CAMPANA = :p_camp
    """), {"p_camp": campaign["id"]}).mappings().first()

    def counts(row, notices):
        total, conf, rep = (int(row[k] or 0) for k in ("total", "confirmadas", "reportadas"))
        summary = notices.get("resumen") or {}
        return {"total": total, "confirmadas": conf, "reportadas": rep, "pendientes": total - conf - rep,
                "gerentes": summary.get("gerentes", 0), "gerentes_notificados": summary.get("notificados", 0),
                "gerentes_por_notificar": summary.get("listos", 0)}

    item["externas"] = counts(ext_row, ext.preview(db))
    item["internas"] = counts(int_row, internal.preview(db))
    return item


def overview(db, today=None):
    today = today or date.today()
    items = []
    for control in (1, 2, 3, 5, 6, 7):
        try:
            items.append(_control7(db) if control == 7 else _documental(db, control, today))
        except Exception as exc:  # Un control con error no oculta a los demás.
            db.rollback()
            logger.exception("Resumen SOX: no se pudo leer el Control %s", control)
            items.append({"control": control, "nombre": NAMES[control], "error": f"{type(exc).__name__}: {str(exc)[:200]}"})
    return {"fecha": today.isoformat(), "controles": items}
