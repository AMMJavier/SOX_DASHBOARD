"""Control 7 - VPN internas (LDAP RDP / APLICACIONES) validadas por el gerente.

Misma campaña semestral que las VPN externas (AUTOM.CAMPANAS_SOX). Al iniciar la campaña
(o con "Cargar desde LDAP") se toma la foto de los grupos del Control 6 con el jefe de cada
cuenta según Active Directory ("manager"). El gerente solo ve y confirma SUS cuentas: la
pertenencia se comprueba en el backend con GERENTE_USUARIO = usuario en sesión.
Tablas: backend/sql/sox_c7_vpn_internas.sql.
"""
from __future__ import annotations  # Python 3.9 en el servidor

from datetime import datetime
import logging

from fastapi import HTTPException
from sqlalchemy import text

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

def load_from_ldap(db, campaign_id=None):
    """Foto LDAP de la campaña activa. Las cuentas ya confirmadas conservan su decisión y gerente."""
    from services.sox.control_6.ldap_access import LDAPAccessError, read_internal_access_with_managers

    campaign = active_campaign(db)
    if campaign_id is None:
        if not campaign:
            raise HTTPException(409, "No hay una campaña activa para cargar VPN internas")
        campaign_id = campaign["id"]
    log(f"CARGA INICIO | campaña {campaign_id} | grupos LDAP RDP y APLICACIONES con su jefe (manager)")
    try:
        report = read_internal_access_with_managers()
    except LDAPAccessError as exc:
        log(f"CARGA FALLIDA | {exc}")
        raise HTTPException(502, str(exc))

    now = datetime.utcnow()
    managers = {}
    without_manager = 0
    for row in report["filas"]:
        manager = row.get("gerente")
        if manager:
            managers[manager["usuario"]] = manager
        else:
            without_manager += 1
        db.execute(text("""
            MERGE INTO AUTOM.SOX_C7_VPN_INTERNAS d
            USING (SELECT :p_camp ID_CAMPANA, :p_user USUARIO, :p_tipo TIPO_ACCESO FROM dual) s
               ON (d.ID_CAMPANA = s.ID_CAMPANA AND d.USUARIO = s.USUARIO AND d.TIPO_ACCESO = s.TIPO_ACCESO)
            WHEN MATCHED THEN UPDATE SET
                 d.NOMBRE = :p_nombre, d.ACTIVO_AD = :p_activo,
                 d.GERENTE = CASE WHEN d.CONFIRMACION = 1 THEN d.GERENTE ELSE :p_ger END,
                 d.GERENTE_USUARIO = CASE WHEN d.CONFIRMACION = 1 THEN d.GERENTE_USUARIO ELSE :p_ger_user END,
                 d.GERENTE_CORREO = CASE WHEN d.CONFIRMACION = 1 THEN d.GERENTE_CORREO ELSE :p_ger_mail END
            WHEN NOT MATCHED THEN INSERT
                 (ID_CAMPANA, USUARIO, NOMBRE, TIPO_ACCESO, ACTIVO_AD, GERENTE, GERENTE_USUARIO, GERENTE_CORREO,
                  ESTADO, CONFIRMACION, FECHA_CARGA)
                 VALUES (:p_camp, :p_user, :p_nombre, :p_tipo, :p_activo, :p_ger, :p_ger_user, :p_ger_mail,
                         'mantener', 0, :p_now)
        """), {"p_camp": campaign_id, "p_user": row["usuario"], "p_tipo": row["tipo_acceso"],
               "p_nombre": row.get("nombre"),
               "p_activo": None if row.get("activo") is None else int(bool(row["activo"])),
               "p_ger": manager["nombre"] if manager else None,
               "p_ger_user": manager["usuario"] if manager else None,
               "p_ger_mail": manager["correo"] if manager else None, "p_now": now})
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
    summary = {"id_campana": campaign_id, "membresias": len(report["filas"]), "gerentes": len(managers),
               "sin_gerente": without_manager, "consulta_utc": report["consulta_utc"]}
    log(f"CARGA FIN | {summary}")
    return summary


# ---------------------------------------------------------------- consultas

_SELECT = """
    SELECT ID AS "id", ID_CAMPANA AS "id_campana", USUARIO AS "usuario", NOMBRE AS "nombre",
           TIPO_ACCESO AS "tipo_acceso", ACTIVO_AD AS "activo_ad", GERENTE AS "gerente",
           GERENTE_USUARIO AS "gerente_usuario", ESTADO AS "estado", OBSERVACION AS "observacion",
           CONFIRMACION AS "confirmacion", CONFIRMADO_POR AS "confirmado_por",
           FECHA_MODIFICACION AS "fecha_modificacion"
      FROM AUTOM.SOX_C7_VPN_INTERNAS
"""


def list_for_manager(db, username):
    campaign = active_campaign(db)
    if not campaign:
        return {"campana": None, "items": []}
    items = _rows(db.execute(text(_SELECT + """
        WHERE ID_CAMPANA = :p_camp AND LOWER(GERENTE_USUARIO) = LOWER(:p_user)
        ORDER BY TIPO_ACCESO, NOMBRE, USUARIO
    """), {"p_camp": campaign["id"], "p_user": username}))
    return {"campana": campaign, "items": items}


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
        where.append("CONFIRMACION = 0")
    elif estado == "confirmado":
        where.append("CONFIRMACION = 1")
    elif estado in DECISIONS:
        where.append("CONFIRMACION = 1 AND ESTADO = :p_est")
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
        SELECT COUNT(*) AS "total", NVL(SUM(CONFIRMACION), 0) AS "confirmadas",
               NVL(SUM(CASE WHEN GERENTE_USUARIO IS NULL THEN 1 ELSE 0 END), 0) AS "sin_gerente",
               NVL(SUM(CASE WHEN CONFIRMACION = 1 AND ESTADO = 'eliminar' THEN 1 ELSE 0 END), 0) AS "eliminar"
          FROM AUTOM.SOX_C7_VPN_INTERNAS WHERE ID_CAMPANA = :p_camp
    """), {"p_camp": campaign_id}).mappings().first() or {})
    gerentes = _rows(db.execute(text("""
        SELECT GERENTE_USUARIO AS "usuario", MIN(GERENTE) AS "nombre", COUNT(*) AS "total",
               SUM(CONFIRMACION) AS "confirmadas"
          FROM AUTOM.SOX_C7_VPN_INTERNAS WHERE ID_CAMPANA = :p_camp AND GERENTE_USUARIO IS NOT NULL
         GROUP BY GERENTE_USUARIO ORDER BY MIN(GERENTE)
    """), {"p_camp": campaign_id}))
    return {"campana": campaign, "items": items, "total": int(total or 0), "resumen": resumen, "gerentes": gerentes}


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


def decide(db, *, item_id, decision, observation, user, accion="MODIFICACION_VALIDACION", commit=True):
    """Guarda la decisión de una cuenta. El gerente solo puede decidir sobre SUS cuentas."""
    estado, observation = _decision(decision, observation)
    campaign = active_campaign(db)
    if not campaign:
        raise HTTPException(409, "No hay una campaña activa")
    if campaign["vencida"]:
        raise HTTPException(403, "La fecha límite de la campaña ya venció")
    row = db.execute(text("""
        SELECT ID, ID_CAMPANA, USUARIO, TIPO_ACCESO, GERENTE, GERENTE_USUARIO, ESTADO, OBSERVACION
          FROM AUTOM.SOX_C7_VPN_INTERNAS WHERE ID = :p_id
    """), {"p_id": item_id}).mappings().first()
    if not row or row["id_campana"] != campaign["id"]:
        raise HTTPException(404, "La cuenta no pertenece a la campaña activa")
    is_admin = user.rol in ("administrador", "desarrollador")
    if not is_admin and (row["gerente_usuario"] or "").lower() != user.username.lower():
        raise HTTPException(403, "Solo el gerente a cargo puede confirmar esta cuenta")
    db.execute(text("""
        UPDATE AUTOM.SOX_C7_VPN_INTERNAS
           SET ESTADO = :p_est, OBSERVACION = :p_obs, CONFIRMACION = 1, CONFIRMADO_POR = :p_user,
               FECHA_MODIFICACION = :p_now
         WHERE ID = :p_id
    """), {"p_est": estado, "p_obs": observation, "p_user": user.username, "p_now": datetime.utcnow(), "p_id": item_id})
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
    return {"id": item_id, "estado": estado, "confirmacion": 1}


def confirm_all(db, *, items, user):
    if not items:
        raise HTTPException(422, "No hay cuentas para confirmar")
    if len(items) > 2000:
        raise HTTPException(422, "Demasiadas cuentas en una sola confirmación")
    try:
        for item in items:
            decide(db, item_id=item.id, decision=item.decision, observation=item.observation, user=user,
                   accion="GUARDAR_MASIVO", commit=False)
        db.commit()
    except Exception:
        db.rollback()
        raise
    log(f"CONFIRMACION MASIVA | {user.username} confirmó {len(items)} cuenta(s)")
    return {"confirmadas": len(items)}
