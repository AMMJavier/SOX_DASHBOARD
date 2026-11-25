"""Control 7 - VPN internas (LDAP RDP / APLICACIONES) validadas por el gerente.

Misma campaña semestral que las VPN externas (AUTOM.CAMPANAS_SOX). Al iniciar la campaña
(o con "Cargar desde LDAP") se toma la foto de los grupos LDAP de VPN (RDP y Aplicaciones) con el GERENTE de cada
cuenta: el primer cargo "Gerente" en la cadena de jefes de AD. El gerente solo ve y confirma SUS cuentas: la
pertenencia se comprueba en el backend con GERENTE_USUARIO = usuario en sesión.
Tablas: backend/sql/sox_c7_vpn_internas.sql.
"""
from __future__ import annotations  # Python 3.9 en el servidor

from datetime import datetime
import logging

from fastapi import HTTPException
from sqlalchemy import text

from services.sox.control_7.decision_rules import confirmation_for, is_answered, is_confirmed, is_reported

logger = logging.getLogger(__name__)

DECISIONS = {"mantener": "mantener", "eliminar": "eliminar", "no pertenece": "no pertenece", "otro": "otro"}
MAX_OBSERVATION = 1000


def log(message):
    print(f"[SOX C7 INTERNAS {datetime.now():%Y-%m-%d %H:%M:%S}] {message}", flush=True)


def _rows(result):
    items = []
    for row in result.mappings():
        item = dict(row)
        for key, value in item.items():
            if isinstance(value, datetime):
                item[key] = value.isoformat()
        items.append(item)
    return items


def active_campaign(db):
    row = db.execute(text("""
        SELECT ID_CAMPANA AS "id", NOMBRE_CAMPANA AS "nombre", ANIO AS "anio", SEMESTRE AS "semestre",
               FECHA_LIMITE AS "fecha_limite",
               CASE WHEN SYSDATE > FECHA_LIMITE THEN 1 ELSE 0 END AS "vencida"
          FROM AUTOM.CAMPANAS_SOX WHERE ESTADO = 'ACTIVA'
         ORDER BY ID_CAMPANA DESC FETCH FIRST 1 ROWS ONLY
    """)).mappings().first()
    if not row:
        return None
    item = dict(row)
    if isinstance(item["fecha_limite"], datetime):
        item["fecha_limite"] = item["fecha_limite"].isoformat()
    item["vencida"] = bool(item["vencida"])
    return item


# ---------------------------------------------------------------- carga desde LDAP

def _manual_assignments(db, campaign_id, current):
    """Gerentes asignados a mano: los de esta campaña y, si no hay, el último de campañas anteriores.

    Devuelve {(usuario, tipo_acceso): {usuario, nombre, correo}}.
    """
    found = {}
    for key, r in current.items():
        if r["gerente_manual"] == 1 and r["gerente_usuario"]:
            found[key] = {"usuario": r["gerente_usuario"], "nombre": r["gerente"], "correo": r["gerente_correo"]}
    previous = db.execute(text("""
        SELECT USUARIO AS "usuario", TIPO_ACCESO AS "tipo_acceso", GERENTE AS "gerente",
               GERENTE_USUARIO AS "gerente_usuario", GERENTE_CORREO AS "gerente_correo"
          FROM AUTOM.SOX_C7_VPN_INTERNAS
         WHERE GERENTE_MANUAL = 1 AND GERENTE_USUARIO IS NOT NULL AND ID_CAMPANA <> :p_camp
         ORDER BY ID_CAMPANA DESC
    """), {"p_camp": campaign_id}).mappings()
    for r in previous:
        key = (r["usuario"], r["tipo_acceso"])
        if key not in found:
            found[key] = {"usuario": r["gerente_usuario"], "nombre": r["gerente"], "correo": r["gerente_correo"]}
    return found


def load_from_ldap(db, campaign_id=None, replace=False):
    """Foto LDAP de la campaña activa con el GERENTE de cada cuenta (primer cargo "Gerente"
    en la cadena de jefes de AD). Las cuentas confirmadas (Mantener / Eliminar) conservan su
    gerente y su decisión. Las demás toman el gerente de AD: si cambió, la cuenta vuelve a
    pendiente para el nuevo gerente y, si estaba reportada, el cambio queda en el seguimiento.

    replace=True BORRA la foto anterior de la campaña (cuentas y su seguimiento) y la vuelve a
    cargar desde cero. Se usa al iniciar la campaña y con "Reemplazar carga". Primero se lee LDAP:
    si LDAP falla no se borra nada. No se permite si algún gerente ya confirmó cuentas.

    Las cuentas sin gerente en AD conservan el gerente que les asignó el administrador
    (GERENTE_MANUAL = 1), también de una campaña anterior. Si AD ya tiene gerente, manda AD.
    Las cuentas con cargo "Director..." las valida el aprobador de directores (ldap_vpn.director_approver)."""
    from services.sox.control_7.ldap_vpn import LDAPAccessError, read_internal_access_with_managers

    campaign = active_campaign(db)
    if campaign_id is None:
        if not campaign:
            raise HTTPException(409, "No hay una campaña activa para cargar VPN internas")
        campaign_id = campaign["id"]
    log(f"CARGA INICIO | campaña {campaign_id} | grupos LDAP RDP y APLICACIONES con su gerente (cadena de jefes de AD)")
    try:
        report = read_internal_access_with_managers()
    except LDAPAccessError as exc:
        log(f"CARGA FALLIDA | {exc}")
        raise HTTPException(502, str(exc))

    now = datetime.utcnow()
    # Estado actual de la campaña (se lee ANTES de un posible reemplazo): para detectar
    # cambios de gerente y conservar los gerentes asignados a mano por el administrador.
    current = {(r["usuario"], r["tipo_acceso"]): r for r in db.execute(text("""
        SELECT ID AS "id", USUARIO AS "usuario", TIPO_ACCESO AS "tipo_acceso", GERENTE AS "gerente",
               GERENTE_USUARIO AS "gerente_usuario", GERENTE_CORREO AS "gerente_correo",
               GERENTE_MANUAL AS "gerente_manual", ESTADO AS "estado", OBSERVACION AS "observacion",
               CONFIRMACION AS "confirmacion"
          FROM AUTOM.SOX_C7_VPN_INTERNAS WHERE ID_CAMPANA = :p_camp
    """), {"p_camp": campaign_id}).mappings()}
    manual = _manual_assignments(db, campaign_id, current)

    deleted = 0
    if replace:
        answered = sum(1 for r in current.values() if is_answered(r["estado"], r["confirmacion"]))
        if answered:
            log(f"REEMPLAZO CANCELADO | campaña {campaign_id} | {answered} cuenta(s) ya respondidas por gerentes")
            raise HTTPException(409, f"No se puede reemplazar la carga: {answered} cuenta(s) ya fueron "
                                     "respondidas por gerentes. Usa \"Cargar desde LDAP\" para actualizarla.")
        db.execute(text("DELETE FROM AUTOM.SOX_C7_VPN_INTERNAS_LOG WHERE ID_CAMPANA = :p_camp"), {"p_camp": campaign_id})
        deleted = db.execute(text("DELETE FROM AUTOM.SOX_C7_VPN_INTERNAS WHERE ID_CAMPANA = :p_camp"),
                             {"p_camp": campaign_id}).rowcount or 0
        log(f"REEMPLAZO | campaña {campaign_id} | {deleted} registro(s) anteriores borrados")
        current = {}

    managers = {}
    without_manager = 0
    directors = 0
    kept_manual = 0
    reassigned = 0
    for row in report["filas"]:
        manager = row.get("gerente")
        is_manual = 0
        directors += bool(row.get("director"))
        if manager:
            managers[manager["usuario"]] = manager
        elif (row["usuario"], row["tipo_acceso"]) in manual:
            # Sin gerente en AD: se conserva el que asignó el administrador.
            manager, is_manual = manual[(row["usuario"], row["tipo_acceso"])], 1
            kept_manual += 1
        else:
            without_manager += 1
        before = current.get((row["usuario"], row["tipo_acceso"]))
        if before and is_confirmed(before["estado"], before["confirmacion"]):
            # Confirmada (Mantener / Eliminar): no cambia de gerente al actualizar.
            manager = {"usuario": before["gerente_usuario"], "nombre": before["gerente"],
                       "correo": before["gerente_correo"]}
            is_manual = before["gerente_manual"]
        # Cambio de gerente: el nuevo NO hereda la respuesta del anterior. Si estaba reportada
        # (Otro / No pertenece) se deja constancia en el seguimiento y vuelve a pendiente.
        new_user = (manager or {}).get("usuario")
        if before and (before["gerente_usuario"] or "").lower() != (new_user or "").lower() and is_reported(before["estado"]):
            reassigned += 1
            note = (f"Cambio de gerente: {before['gerente'] or 'sin gerente'} -> "
                    f"{(manager or {}).get('nombre') or 'sin gerente'}. La decisión anterior queda en el historial "
                    "y la cuenta vuelve a pendiente para el nuevo gerente.")
            db.execute(text("""
                INSERT INTO AUTOM.SOX_C7_VPN_INTERNAS_LOG
                  (INTERNA_ID, ID_CAMPANA, CUENTA, TIPO_ACCESO, GERENTE, ACCION, ESTADO_ANTERIOR, ESTADO_NUEVO,
                   OBSERVACION_ANTERIOR, OBSERVACION_NUEVA, USUARIO_SOX, FECHA)
                VALUES (:p_id, :p_camp, :p_cuenta, :p_tipo, :p_ger, 'REASIGNACION DE GERENTE', :p_ant, 'pendiente',
                        :p_obs_ant, :p_obs, 'LDAP', :p_now)
            """), {"p_id": before["id"], "p_camp": campaign_id, "p_cuenta": row["usuario"],
                   "p_tipo": row["tipo_acceso"], "p_ger": (manager or {}).get("nombre"), "p_ant": before["estado"],
                   "p_obs_ant": before["observacion"], "p_obs": note[:1000], "p_now": now})
        # En Oracle, las expresiones del SET usan los valores ANTERIORES de la fila.
        db.execute(text("""
            MERGE INTO AUTOM.SOX_C7_VPN_INTERNAS d
            USING (SELECT :p_camp ID_CAMPANA, :p_user USUARIO, :p_tipo TIPO_ACCESO FROM dual) s
               ON (d.ID_CAMPANA = s.ID_CAMPANA AND d.USUARIO = s.USUARIO AND d.TIPO_ACCESO = s.TIPO_ACCESO)
            WHEN MATCHED THEN UPDATE SET
                 d.NOMBRE = :p_nombre, d.ACTIVO_AD = :p_activo,
                 d.GERENTE = :p_ger, d.GERENTE_USUARIO = :p_ger_user, d.GERENTE_CORREO = :p_ger_mail,
                 d.GERENTE_MANUAL = :p_manual,
                 d.CONFIRMACION = CASE WHEN NVL(LOWER(d.GERENTE_USUARIO), '-') = NVL(LOWER(:p_ger_user), '-')
                                       THEN d.CONFIRMACION ELSE 0 END,
                 d.ESTADO = CASE WHEN NVL(LOWER(d.GERENTE_USUARIO), '-') = NVL(LOWER(:p_ger_user), '-')
                                 THEN d.ESTADO ELSE 'mantener' END,
                 d.OBSERVACION = CASE WHEN NVL(LOWER(d.GERENTE_USUARIO), '-') = NVL(LOWER(:p_ger_user), '-')
                                      THEN d.OBSERVACION ELSE NULL END,
                 d.CONFIRMADO_POR = CASE WHEN NVL(LOWER(d.GERENTE_USUARIO), '-') = NVL(LOWER(:p_ger_user), '-')
                                         THEN d.CONFIRMADO_POR ELSE NULL END,
                 -- Cambio de gerente = la cuenta cambió: se marca la fecha de modificación.
                 d.FECHA_MODIFICACION = CASE WHEN NVL(LOWER(d.GERENTE_USUARIO), '-') = NVL(LOWER(:p_ger_user), '-')
                                             THEN d.FECHA_MODIFICACION ELSE :p_now END
            WHEN NOT MATCHED THEN INSERT
                 (ID_CAMPANA, USUARIO, NOMBRE, TIPO_ACCESO, ACTIVO_AD, GERENTE, GERENTE_USUARIO, GERENTE_CORREO,
                  GERENTE_MANUAL, ESTADO, CONFIRMACION, FECHA_CARGA)
                 VALUES (:p_camp, :p_user, :p_nombre, :p_tipo, :p_activo, :p_ger, :p_ger_user, :p_ger_mail,
                         :p_manual, 'mantener', 0, :p_now)
        """), {"p_camp": campaign_id, "p_user": row["usuario"], "p_tipo": row["tipo_acceso"],
               "p_nombre": row.get("nombre"),
               "p_activo": None if row.get("activo") is None else int(bool(row["activo"])),
               "p_ger": manager["nombre"] if manager else None,
               "p_ger_user": manager["usuario"] if manager else None,
               "p_ger_mail": manager["correo"] if manager else None, "p_manual": is_manual, "p_now": now})
    # Contactos: solo se AGREGAN gerentes nuevos; no se modifica un contacto existente
    # (sus nombres deben seguir cruzando con los gerentes de las VPN externas).
    for manager in managers.values():
        db.execute(text("""
            MERGE INTO AUTOM.SOX_GERENTES_CONTACTO d
            USING (SELECT :p_user LDAP_CN FROM dual) s ON (LOWER(d.LDAP_CN) = LOWER(s.LDAP_CN))
            WHEN NOT MATCHED THEN INSERT (NOMBRE_COMPLETO, CORREO, LDAP_CN, ACTIVO, FECHA_SYNC, FECHA_ACTUALIZACION)
                 VALUES (:p_nombre, :p_correo, :p_user, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """), {"p_user": manager["usuario"], "p_nombre": manager["nombre"], "p_correo": manager["correo"]})
    db.commit()
    summary = {"id_campana": campaign_id, "reemplazo": bool(replace), "borrados": deleted,
               "membresias": len(report["filas"]), "gerentes": len(managers),
               "sin_gerente": without_manager, "directores": directors, "gerente_manual": kept_manual, "reasignadas_reportadas": reassigned,
               "consulta_utc": report["consulta_utc"]}
    log(f"CARGA FIN | {summary}")
    return summary


# ---------------------------------------------------------------- consultas

_SELECT = """
    SELECT ID AS "id", ID_CAMPANA AS "id_campana", USUARIO AS "usuario", NOMBRE AS "nombre",
           TIPO_ACCESO AS "tipo_acceso", ACTIVO_AD AS "activo_ad", GERENTE AS "gerente",
           GERENTE_USUARIO AS "gerente_usuario", ESTADO AS "estado", OBSERVACION AS "observacion",
           CASE WHEN CONFIRMACION = 1 AND ESTADO NOT IN ('no pertenece', 'otro') THEN 1 ELSE 0 END AS "confirmacion", CONFIRMADO_POR AS "confirmado_por",
           FECHA_MODIFICACION AS "fecha_modificacion", GERENTE_MANUAL AS "gerente_manual"
      FROM AUTOM.SOX_C7_VPN_INTERNAS
"""


def _first_name(display):
    """ "TIC David Álava" -> "David" (quita el prefijo de área en mayúsculas)."""
    words = str(display or "").split()
    if len(words) > 1 and words[0].isupper() and len(words[0]) <= 4:
        words = words[1:]
    return words[0] if words else ""


def list_for_manager(db, username):
    from services.sox.control_7.ldap_vpn import director_approver, director_demo_users

    username = (username or "").strip().lower()
    approver = username == director_approver()
    # Demostración: ve las VPN del aprobador de directores, sin poder guardar (ver decide()).
    demo = not approver and username in director_demo_users()
    if demo:
        username, approver = director_approver(), True
    campaign = active_campaign(db)
    if not campaign:
        return {"campana": None, "items": [], "aprobador_directores": approver, "demo": demo, "nombre_saludo": ""}
    items = _rows(db.execute(text(_SELECT + """
        WHERE ID_CAMPANA = :p_camp AND LOWER(GERENTE_USUARIO) = LOWER(:p_user)
        ORDER BY TIPO_ACCESO, NOMBRE, USUARIO
    """), {"p_camp": campaign["id"], "p_user": username}))
    # El aprobador de directores ve una página propia ("VPN de directores") con un saludo.
    return {"campana": campaign, "items": items, "aprobador_directores": approver, "demo": demo,
            "nombre_saludo": _first_name(items[0]["gerente"]) if approver and items else ""}


def list_admin(db, *, campaign_id=None, search="", gerente="", estado="", tipo="", offset=0, limit=50):
    campaign = active_campaign(db)
    campaign_id = campaign_id or (campaign or {}).get("id")
    if not campaign_id:
        return {"campana": None, "items": [], "total": 0, "resumen": {}, "gerentes": []}
    where = ["ID_CAMPANA = :p_camp"]
    params = {"p_camp": campaign_id}
    if search:
        where.append("(LOWER(USUARIO) LIKE :p_q OR LOWER(NOMBRE) LIKE :p_q OR LOWER(GERENTE) LIKE :p_q)")
        params["p_q"] = f"%{search.strip().lower()}%"
    if gerente == "__sin__":
        where.append("GERENTE_USUARIO IS NULL")
    elif gerente:
        where.append("LOWER(GERENTE_USUARIO) = LOWER(:p_ger)")
        params["p_ger"] = gerente
    if estado == "pendiente":
        where.append("(CONFIRMACION = 0 OR ESTADO IN ('no pertenece', 'otro'))")
    elif estado == "confirmado":
        where.append("CONFIRMACION = 1 AND ESTADO NOT IN ('no pertenece', 'otro')")
    elif estado in DECISIONS:
        # Otro / No pertenece se responden sin confirmar.
        where.append("ESTADO = :p_est" if is_reported(estado) else "CONFIRMACION = 1 AND ESTADO = :p_est")
        params["p_est"] = estado
    if tipo in ("RDP", "APLICACIONES"):
        where.append("TIPO_ACCESO = :p_tipo")
        params["p_tipo"] = tipo
    clause = " WHERE " + " AND ".join(where)
    total = db.execute(text("SELECT COUNT(*) FROM AUTOM.SOX_C7_VPN_INTERNAS" + clause), params).scalar()
    items = _rows(db.execute(text(_SELECT + clause + """
        ORDER BY GERENTE NULLS FIRST, NOMBRE, USUARIO, TIPO_ACCESO
        OFFSET :p_off ROWS FETCH NEXT :p_lim ROWS ONLY
    """), {**params, "p_off": max(0, offset), "p_lim": max(1, min(limit, 200))}))
    resumen = dict(db.execute(text("""
        SELECT COUNT(*) AS "total", NVL(SUM(CASE WHEN CONFIRMACION = 1 AND ESTADO NOT IN ('no pertenece', 'otro') THEN 1 ELSE 0 END), 0) AS "confirmadas",
               NVL(SUM(CASE WHEN GERENTE_USUARIO IS NULL THEN 1 ELSE 0 END), 0) AS "sin_gerente",
               NVL(SUM(CASE WHEN CONFIRMACION = 1 AND ESTADO = 'eliminar' THEN 1 ELSE 0 END), 0) AS "eliminar"
          FROM AUTOM.SOX_C7_VPN_INTERNAS WHERE ID_CAMPANA = :p_camp
    """), {"p_camp": campaign_id}).mappings().first() or {})
    gerentes = _rows(db.execute(text("""
        SELECT GERENTE_USUARIO AS "usuario", MIN(GERENTE) AS "nombre", COUNT(*) AS "total",
               SUM(CASE WHEN CONFIRMACION = 1 AND ESTADO NOT IN ('no pertenece', 'otro') THEN 1 ELSE 0 END) AS "confirmadas"
          FROM AUTOM.SOX_C7_VPN_INTERNAS WHERE ID_CAMPANA = :p_camp AND GERENTE_USUARIO IS NOT NULL
         GROUP BY GERENTE_USUARIO ORDER BY MIN(GERENTE)
    """), {"p_camp": campaign_id}))
    return {"campana": campaign, "items": items, "total": int(total or 0), "resumen": resumen, "gerentes": gerentes}


def dashboard(db, gerente=""):
    """KPI de la campaña activa (mismos indicadores que el dashboard de VPN externas)."""
    campaign = active_campaign(db)
    if not campaign:
        return {"campana": None, "kpis": {}, "responsables": [], "gerentes": []}
    params = {"p_camp": campaign["id"]}
    extra = ""
    if gerente:
        extra = " AND LOWER(GERENTE_USUARIO) = LOWER(:p_ger)"
        params["p_ger"] = gerente
    kpis = dict(db.execute(text(f"""
        SELECT COUNT(*) AS "total", NVL(SUM(CASE WHEN CONFIRMACION = 1 AND ESTADO NOT IN ('no pertenece', 'otro') THEN 1 ELSE 0 END), 0) AS "confirmed",
               NVL(SUM(1 - CASE WHEN CONFIRMACION = 1 AND ESTADO NOT IN ('no pertenece', 'otro') THEN 1 ELSE 0 END), 0) AS "pending",
               NVL(SUM(CASE WHEN GERENTE_USUARIO IS NULL THEN 1 ELSE 0 END), 0) AS "no_owner",
               NVL(SUM(CASE WHEN TIPO_ACCESO = 'RDP' THEN 1 ELSE 0 END), 0) AS "rdp",
               NVL(SUM(CASE WHEN TIPO_ACCESO = 'APLICACIONES' THEN 1 ELSE 0 END), 0) AS "aplicaciones",
               NVL(SUM(CASE WHEN CONFIRMACION = 1 AND ESTADO = 'eliminar' THEN 1 ELSE 0 END), 0) AS "eliminar"
          FROM AUTOM.SOX_C7_VPN_INTERNAS WHERE ID_CAMPANA = :p_camp{extra}
    """), params).mappings().first() or {})
    kpis = {k: int(v or 0) for k, v in kpis.items()}
    kpis["expired"] = kpis["pending"] if campaign["vencida"] else 0
    responsables = _rows(db.execute(text(f"""
        SELECT MIN(GERENTE) AS "manager", GERENTE_USUARIO AS "usuario", COUNT(*) AS "total",
               SUM(CASE WHEN CONFIRMACION = 1 AND ESTADO NOT IN ('no pertenece', 'otro') THEN 1 ELSE 0 END) AS "confirmed"
          FROM AUTOM.SOX_C7_VPN_INTERNAS
         WHERE ID_CAMPANA = :p_camp AND GERENTE_USUARIO IS NOT NULL{extra}
         GROUP BY GERENTE_USUARIO ORDER BY MIN(GERENTE)
    """), params))
    gerentes = _rows(db.execute(text("""
        SELECT GERENTE_USUARIO AS "usuario", MIN(GERENTE) AS "nombre"
          FROM AUTOM.SOX_C7_VPN_INTERNAS WHERE ID_CAMPANA = :p_camp AND GERENTE_USUARIO IS NOT NULL
         GROUP BY GERENTE_USUARIO ORDER BY MIN(GERENTE)
    """), {"p_camp": campaign["id"]}))
    return {"campana": campaign, "kpis": kpis, "responsables": responsables, "gerentes": gerentes}


def campaign_rows(db):
    """Todas las cuentas de la campaña activa (la pantalla Campaña filtra en el navegador)."""
    campaign = active_campaign(db)
    if not campaign:
        return {"campana": None, "items": []}
    items = _rows(db.execute(text(_SELECT + """
        WHERE ID_CAMPANA = :p_camp ORDER BY GERENTE NULLS FIRST, NOMBRE, USUARIO, TIPO_ACCESO
        FETCH FIRST 20000 ROWS ONLY
    """), {"p_camp": campaign["id"]}))
    return {"campana": campaign, "items": items}


def history_filters(db):
    campaigns = _rows(db.execute(text("""
        SELECT c.ID_CAMPANA AS "id", c.NOMBRE_CAMPANA AS "name", c.ANIO AS "anio", c.ESTADO AS "estado"
          FROM AUTOM.CAMPANAS_SOX c
         WHERE EXISTS (SELECT 1 FROM AUTOM.SOX_C7_VPN_INTERNAS i WHERE i.ID_CAMPANA = c.ID_CAMPANA)
         ORDER BY c.ID_CAMPANA DESC
    """)))
    managers = [r[0] for r in db.execute(text("""
        SELECT DISTINCT GERENTE FROM AUTOM.SOX_C7_VPN_INTERNAS WHERE GERENTE IS NOT NULL ORDER BY GERENTE
    """))]
    return {"campaigns": campaigns, "years": sorted({c["anio"] for c in campaigns}, reverse=True), "managers": managers}


def history(db, *, campaign_id=None, year=None, manager="", status="", tipo="", search=""):
    where, params = ["1 = 1"], {}
    if campaign_id:
        where.append("i.ID_CAMPANA = :p_camp")
        params["p_camp"] = campaign_id
    if year:
        where.append("c.ANIO = :p_year")
        params["p_year"] = year
    if manager:
        where.append("i.GERENTE = :p_ger")
        params["p_ger"] = manager
    if status == "pendiente":
        where.append("(i.CONFIRMACION = 0 OR i.ESTADO IN ('no pertenece', 'otro'))")
    elif status in DECISIONS:
        where.append("i.ESTADO = :p_est" if is_reported(status) else "i.CONFIRMACION = 1 AND i.ESTADO = :p_est")
        params["p_est"] = status
    if tipo in ("RDP", "APLICACIONES"):
        where.append("i.TIPO_ACCESO = :p_tipo")
        params["p_tipo"] = tipo
    if search:
        where.append("(LOWER(i.USUARIO) LIKE :p_q OR LOWER(i.NOMBRE) LIKE :p_q OR LOWER(i.GERENTE) LIKE :p_q)")
        params["p_q"] = f"%{search.strip().lower()}%"
    return _rows(db.execute(text(f"""
        SELECT i.ID AS "id", c.NOMBRE_CAMPANA AS "campaign_name", c.ESTADO AS "campaign_status",
               c.FECHA_LIMITE AS "deadline", c.FECHA_FIN AS "closed_at", i.USUARIO AS "usuario",
               i.NOMBRE AS "nombre", i.TIPO_ACCESO AS "tipo_acceso", i.GERENTE AS "gerente",
               i.ESTADO AS "estado", CASE WHEN i.CONFIRMACION = 1 AND i.ESTADO NOT IN ('no pertenece', 'otro') THEN 1 ELSE 0 END AS "confirmacion", i.OBSERVACION AS "observacion",
               i.CONFIRMADO_POR AS "confirmado_por", i.FECHA_MODIFICACION AS "fecha_modificacion"
          FROM AUTOM.SOX_C7_VPN_INTERNAS i JOIN AUTOM.CAMPANAS_SOX c ON c.ID_CAMPANA = i.ID_CAMPANA
         WHERE {' AND '.join(where)}
         ORDER BY i.ID_CAMPANA DESC, i.GERENTE, i.NOMBRE, i.USUARIO
         FETCH FIRST 20000 ROWS ONLY
    """), params))


def audit_log(db, limit=5000):
    """Seguimiento: acciones registradas sobre las validaciones de VPN internas (más recientes primero)."""
    return _rows(db.execute(text("""
        SELECT l.ID AS "id", l.FECHA AS "fecha_evento", l.USUARIO_SOX AS "usuario", l.GERENTE AS "gerente",
               l.CUENTA AS "cuenta", l.TIPO_ACCESO AS "tipo_acceso", l.ACCION AS "accion",
               l.ESTADO_ANTERIOR AS "estado_anterior", l.ESTADO_NUEVO AS "estado_nuevo",
               l.OBSERVACION_NUEVA AS "observacion_nueva", c.NOMBRE_CAMPANA AS "campana"
          FROM AUTOM.SOX_C7_VPN_INTERNAS_LOG l
          LEFT JOIN AUTOM.CAMPANAS_SOX c ON c.ID_CAMPANA = l.ID_CAMPANA
         ORDER BY l.FECHA DESC, l.ID DESC
         FETCH FIRST :p_lim ROWS ONLY
    """), {"p_lim": limit}))


# ---------------------------------------------------------------- decisiones

def _decision(decision, observation):
    estado = DECISIONS.get(str(decision or "").strip().lower())
    if not estado:
        raise HTTPException(422, "Decisión inválida: Mantener, Eliminar, No pertenece u Otro")
    observation = (observation or "").strip()
    if estado == "otro" and not observation:
        raise HTTPException(422, "La decisión 'Otro' requiere una observación")
    if len(observation) > MAX_OBSERVATION or any(ord(c) < 32 and c not in "\n\t" for c in observation):
        raise HTTPException(422, "Observación inválida o demasiado extensa")
    return estado, observation or None


class AlreadyAnswered(HTTPException):
    def __init__(self):
        super().__init__(409, "Esta cuenta ya fue validada y no se puede cambiar")


def decide(db, *, item_id, decision, observation, user, accion="MODIFICACION_VALIDACION", commit=True):
    """Guarda la decisión de una cuenta. El gerente solo puede decidir sobre SUS cuentas."""
    estado, observation = _decision(decision, observation)
    campaign = active_campaign(db)
    if not campaign:
        raise HTTPException(409, "No hay una campaña activa")
    if campaign["vencida"]:
        raise HTTPException(403, "La fecha límite de la campaña ya venció")
    row = db.execute(text("""
        SELECT ID, ID_CAMPANA, USUARIO, TIPO_ACCESO, GERENTE, GERENTE_USUARIO, ESTADO, OBSERVACION, CONFIRMACION
          FROM AUTOM.SOX_C7_VPN_INTERNAS WHERE ID = :p_id
    """), {"p_id": item_id}).mappings().first()
    if not row or row["id_campana"] != campaign["id"]:
        raise HTTPException(404, "La cuenta no pertenece a la campaña activa")
    from services.sox.control_7.ldap_vpn import director_demo_users

    # Usuario de demostración (LDAP7_DEMO_DIRECTORES): ve la página de directores pero no guarda.
    if ((user.username or "").lower() in director_demo_users()
            and (row["gerente_usuario"] or "").lower() != user.username.lower()):
        raise HTTPException(403, "Vista de demostración: no se pueden guardar decisiones")
    is_admin = user.rol in ("administrador", "desarrollador")
    if not is_admin and (row["gerente_usuario"] or "").lower() != user.username.lower():
        raise HTTPException(403, "Solo el gerente a cargo puede confirmar esta cuenta")
    if is_answered(row["estado"], row["confirmacion"]):
        raise AlreadyAnswered()
    # Mantener / Eliminar confirman; Otro / No pertenece dejan la cuenta pendiente (reportada).
    confirmacion = confirmation_for(estado)
    updated = db.execute(text("""
        UPDATE AUTOM.SOX_C7_VPN_INTERNAS
           SET ESTADO = :p_est, OBSERVACION = :p_obs, CONFIRMACION = :p_conf, CONFIRMADO_POR = :p_user,
               FECHA_MODIFICACION = :p_now
         WHERE ID = :p_id AND CONFIRMACION = 0 AND ESTADO NOT IN ('no pertenece', 'otro')
    """), {"p_est": estado, "p_obs": observation, "p_conf": confirmacion, "p_user": user.username, "p_now": datetime.utcnow(), "p_id": item_id}).rowcount
    if not updated:
        raise AlreadyAnswered()  # Otra sesión la respondió mientras tanto.
    db.execute(text("""
        INSERT INTO AUTOM.SOX_C7_VPN_INTERNAS_LOG
          (INTERNA_ID, ID_CAMPANA, CUENTA, TIPO_ACCESO, GERENTE, ACCION, ESTADO_ANTERIOR, ESTADO_NUEVO,
           OBSERVACION_ANTERIOR, OBSERVACION_NUEVA, USUARIO_SOX, FECHA)
        VALUES (:p_id, :p_camp, :p_cuenta, :p_tipo, :p_ger, :p_acc, :p_ant, :p_est, :p_obs_ant, :p_obs,
                :p_user, :p_now)
    """), {"p_id": item_id, "p_camp": row["id_campana"], "p_cuenta": row["usuario"], "p_tipo": row["tipo_acceso"],
           "p_ger": row["gerente"], "p_acc": accion, "p_ant": row["estado"], "p_est": estado,
           "p_obs_ant": row["observacion"], "p_obs": observation, "p_user": user.username,
           "p_now": datetime.utcnow()})
    if commit:
        db.commit()
    return {"id": item_id, "estado": estado, "confirmacion": confirmacion}


def confirm_all(db, *, items, user):
    if not items:
        raise HTTPException(422, "No hay cuentas para confirmar")
    if len(items) > 2000:
        raise HTTPException(422, "Demasiadas cuentas en una sola confirmación")
    saved, skipped = [], []
    try:
        for item in items:
            try:
                decide(db, item_id=item.id, decision=item.decision, observation=item.observation, user=user,
                       accion="GUARDAR_MASIVO", commit=False)
                saved.append(item.id)
            except AlreadyAnswered:
                skipped.append(item.id)
        db.commit()
    except Exception:
        db.rollback()
        raise
    log(f"GUARDADO MASIVO | {user.username}: {len(saved)} guardada(s), {len(skipped)} ya respondida(s)")
    return {"guardadas": saved, "omitidas": skipped}


# ---------------------------------------------------------------- gerente asignado a mano

def campaign_managers(db):
    """Gerentes que ya tienen cuentas en la campaña activa (para elegirlos al asignar a mano)."""
    campaign = active_campaign(db)
    if not campaign:
        return []
    return [dict(r) for r in db.execute(text("""
        SELECT GERENTE_USUARIO AS "usuario", MIN(GERENTE) AS "nombre", MAX(GERENTE_CORREO) AS "correo",
               COUNT(*) AS "accesos"
          FROM AUTOM.SOX_C7_VPN_INTERNAS
         WHERE ID_CAMPANA = :p_camp AND GERENTE_USUARIO IS NOT NULL
         GROUP BY GERENTE_USUARIO ORDER BY MIN(GERENTE)
    """), {"p_camp": campaign["id"]}).mappings()]


def _clean_user(value):
    value = str(value or "").strip().lower()
    if not value or len(value) > 100 or any(c.isspace() for c in value) or "@" in value:
        raise HTTPException(422, "Indica el usuario de red (AD) del gerente, sin espacios ni @")
    return value


def find_ad_manager(usuario):
    """Busca el usuario en AD para completar nombre y correo (None si LDAP no lo encuentra)."""
    from services.sox.control_7.ldap_vpn import LDAPAccessError, find_person
    try:
        return find_person(_clean_user(usuario))
    except LDAPAccessError as exc:
        raise HTTPException(502, str(exc))


def search_ad_managers(query):
    """Personas activas de AD cuya cuenta o nombre coincide con lo escrito (máx. 20)."""
    from services.sox.control_7.ldap_vpn import LDAPAccessError, search_people
    query = str(query or "").strip()[:100]
    if len(query) < 3:
        raise HTTPException(422, "Escribe al menos 3 letras de la cuenta o del nombre")
    try:
        return search_people(query)
    except LDAPAccessError as exc:
        raise HTTPException(502, str(exc))


def assign_manager(db, *, item_ids, usuario, nombre=None, correo=None, user):
    """El administrador asigna un gerente a cuentas SIN gerente en AD (casos especiales).

    Si ese gerente ya tiene cuentas en la campaña, se usan su mismo nombre y correo: las cuentas
    se suman a él y "Notificación a gerentes" lo muestra una sola vez. Si es nuevo, nombre y correo
    se toman de AD; si AD no lo tiene, de lo que escribió el administrador.
    """
    from services.sox.common.mail_service import EMAIL_RE

    campaign = active_campaign(db)
    if not campaign:
        raise HTTPException(409, "No hay una campaña activa")
    ids = sorted({int(i) for i in item_ids or []})
    if not ids:
        raise HTTPException(422, "Selecciona al menos una cuenta")
    if len(ids) > 2000:
        raise HTTPException(422, "Demasiadas cuentas en una sola asignación")
    usuario = _clean_user(usuario)

    existing = db.execute(text("""
        SELECT MIN(GERENTE) AS "nombre", MAX(GERENTE_CORREO) AS "correo"
          FROM AUTOM.SOX_C7_VPN_INTERNAS
         WHERE ID_CAMPANA = :p_camp AND LOWER(GERENTE_USUARIO) = :p_user
    """), {"p_camp": campaign["id"], "p_user": usuario}).mappings().first()
    if existing and existing["nombre"]:
        nombre, correo, origen = existing["nombre"], existing["correo"], "existente"
    else:
        try:
            person = find_ad_manager(usuario)
        except HTTPException:
            person = None  # LDAP caído: se usan los datos escritos por el administrador
        nombre = ((person or {}).get("nombre") or nombre or "").strip()[:200]
        correo = ((person or {}).get("correo") or correo or "").strip()[:254]
        origen = "AD" if person else "manual"
        if not nombre:
            raise HTTPException(422, "No se encontró el usuario en AD: escribe el nombre del gerente")
        if not correo or not EMAIL_RE.fullmatch(correo):
            raise HTTPException(422, "No se encontró el correo en AD: escribe un correo válido del gerente")

    binds = {f"p_{n}": v for n, v in enumerate(ids)}
    rows = db.execute(text("""
        SELECT ID AS "id", USUARIO AS "usuario", TIPO_ACCESO AS "tipo_acceso", GERENTE AS "gerente",
               GERENTE_USUARIO AS "gerente_usuario", GERENTE_MANUAL AS "gerente_manual",
               ESTADO AS "estado", OBSERVACION AS "observacion", CONFIRMACION AS "confirmacion"
          FROM AUTOM.SOX_C7_VPN_INTERNAS
         WHERE ID_CAMPANA = :p_camp AND ID IN (""" + ", ".join(":" + k for k in binds) + """)
    """), {"p_camp": campaign["id"], **binds}).mappings().all()
    if len(rows) != len(ids):
        raise HTTPException(404, "Alguna cuenta no pertenece a la campaña activa")
    blocked = [r["usuario"] for r in rows if r["gerente_usuario"] and r["gerente_manual"] != 1]
    if blocked:
        raise HTTPException(409, "Estas cuentas ya tienen gerente en AD: " + ", ".join(blocked[:10]))
    # Solo bloquean las confirmadas de verdad (Mantener / Eliminar). Las reportadas (Otro / No
    # pertenece) siguen pendientes y se pueden pasar a otro gerente, aunque por una regla anterior
    # tengan CONFIRMACION = 1.
    confirmed = [r["usuario"] for r in rows if is_confirmed(r["estado"], r["confirmacion"])]
    if confirmed:
        raise HTTPException(409, "Estas cuentas ya fueron confirmadas: " + ", ".join(confirmed[:10]))

    now = datetime.utcnow()
    try:
        for r in rows:
            db.execute(text("""
                UPDATE AUTOM.SOX_C7_VPN_INTERNAS
                   SET GERENTE = :p_ger, GERENTE_USUARIO = :p_user, GERENTE_CORREO = :p_mail, GERENTE_MANUAL = 1,
                       ESTADO = 'mantener', OBSERVACION = NULL, CONFIRMADO_POR = NULL, CONFIRMACION = 0,
                       FECHA_MODIFICACION = :p_now
                 WHERE ID = :p_id
            """), {"p_ger": nombre, "p_user": usuario, "p_mail": correo, "p_now": now, "p_id": r["id"]})
            before = f", antes {r['gerente']}" if r["gerente"] else ""
            db.execute(text("""
                INSERT INTO AUTOM.SOX_C7_VPN_INTERNAS_LOG
                  (INTERNA_ID, ID_CAMPANA, CUENTA, TIPO_ACCESO, GERENTE, ACCION, ESTADO_ANTERIOR, ESTADO_NUEVO,
                   OBSERVACION_ANTERIOR, OBSERVACION_NUEVA, USUARIO_SOX, FECHA)
                VALUES (:p_id, :p_camp, :p_cuenta, :p_tipo, :p_ger, 'ASIGNACION MANUAL DE GERENTE', :p_est, 'mantener',
                        :p_obs_ant, :p_obs, :p_admin, :p_now)
            """), {"p_id": r["id"], "p_camp": campaign["id"], "p_cuenta": r["usuario"], "p_tipo": r["tipo_acceso"],
                   "p_ger": nombre, "p_est": r["estado"], "p_obs_ant": r["observacion"],
                   "p_admin": user.username, "p_now": now,
                   "p_obs": f"Gerente asignado por el administrador: {nombre} ({usuario}){before}"[:1000]})
        db.commit()
    except Exception:
        db.rollback()
        raise
    log(f"ASIGNACION MANUAL | {user.username} asignó {len(rows)} cuenta(s) a {usuario} ({origen})")
    return {"asignadas": len(rows), "gerente": nombre, "usuario": usuario, "correo": correo, "origen": origen}
