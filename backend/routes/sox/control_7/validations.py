from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth.dependencies import get_current_user
from database.oracle_connection import OracleConnection
from models import Usuario
from services.sox.control_7.decision_rules import (
    DECISIONS, REPORTED_SQL, confirmation_for, is_answered, is_confirmed, is_reported, manager_key, normalize,
)

router = APIRouter(tags=["SOX - Validation"])
ADMINS = {"administrador", "desarrollador"}


class ValidationConfirmItem(BaseModel):
    """Decisión del gerente sobre una VPN: Mantener, Eliminar, No pertenece u Otro
    (Otro exige observación)."""
    decision: str
    observation: Optional[str] = None


class ValidationConfirmAllItem(ValidationConfirmItem):
    checkpoint_uid: str


class ValidationConfirmAllRequest(BaseModel):
    validations: List[ValidationConfirmAllItem]


# ---------------------------------------------------------------- utilidades

def _my_manager_names(cursor, username):
    """Nombres de gerente (tal como vienen de Check Point) vinculados al usuario en sesión.

    El vínculo es SOX_GERENTES_CONTACTO.LDAP_CN = usuario LDAP (sAMAccountName), que llena la
    sincronización de contactos. Así el usuario pgalecio valida las VPN de "TIC Paola Galecio".
    """
    cursor.execute("""
        SELECT NOMBRE_COMPLETO
          FROM AUTOM.SOX_GERENTES_CONTACTO
         WHERE LOWER(TRIM(LDAP_CN)) = LOWER(TRIM(:usuario)) AND ACTIVO = 1
    """, {"usuario": username})
    return [row[0] for row in cursor.fetchall() if row[0]]


def _active_deadline(cursor):
    """Fecha límite de la campaña activa (única fuente: CAMPANAS_SOX) o None."""
    cursor.execute("""
        SELECT FECHA_LIMITE FROM AUTOM.CAMPANAS_SOX
         WHERE ESTADO = 'ACTIVA' ORDER BY ID_CAMPANA DESC FETCH FIRST 1 ROWS ONLY
    """)
    row = cursor.fetchone()
    return row[0] if row else None


def _check_open(cursor):
    deadline = _active_deadline(cursor)
    if deadline is None:
        raise HTTPException(409, "No hay una campaña activa")
    if datetime.now() > deadline:
        raise HTTPException(400, "La campaña ya finalizó, no se permiten validaciones")


def _clean(decision, observation):
    estado = DECISIONS.get(normalize(decision))
    if not estado:
        raise HTTPException(422, "Decisión inválida: Mantener, Eliminar, No pertenece u Otro")
    observation = (observation or "").strip() or None
    if estado == "Otro" and not observation:
        raise HTTPException(422, "La decisión 'Otro' requiere una observación")
    return estado, observation


def _rows(cursor):
    cursor.execute("""
        SELECT CHECKPOINT_UID, NOMBRE_VPN, REQ, SOLICITANTE, GERENTE, ESTADO, OBSERVACION, CONFIRMACION,
               FECHA_ALMACENADO
          FROM (SELECT t.*, ROW_NUMBER() OVER (PARTITION BY CHECKPOINT_UID ORDER BY FECHA_ALMACENADO DESC) rn
                  FROM AUTOM.CHECKPOINT_TRANSFORM t)
         WHERE rn = 1
         ORDER BY NOMBRE_VPN
    """)
    columns = [col[0].lower() for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def _item(row, deadline):
    return {
        "id": row["checkpoint_uid"],
        "nombre_vpn": row["nombre_vpn"],
        "req": row["req"],
        "solicitante": row["solicitante"],
        "manager": row["gerente"],
        "decision": DECISIONS.get(normalize(row["estado"]), ""),
        "observation": row["observacion"] or "",
        # 1 = confirmada (Mantener / Eliminar); 0 = pendiente.
        "confirmed": 1 if is_confirmed(row["estado"], row["confirmacion"]) else 0,
        # Otro / No pertenece: pendiente hasta que el administrador corrija el gerente.
        "reported": is_reported(row["estado"]),
        "fecha_almacenado": row["fecha_almacenado"].strftime("%d-%b-%Y") if row["fecha_almacenado"] else "",
        "fecha_limite": deadline.strftime("%d-%b-%Y") if deadline else "",
    }


def _save(cursor, current, uid, estado, observation, accion, own_keys):
    """Guarda la decisión. Devuelve None (guardada), "no_encontrada" u "omitida" (ya respondida)."""
    cursor.execute("""
        SELECT REQ, NOMBRE_VPN, GERENTE, ESTADO, OBSERVACION, CONFIRMACION
          FROM AUTOM.CHECKPOINT_TRANSFORM WHERE CHECKPOINT_UID = :p_uid
    """, {"p_uid": uid})
    old = cursor.fetchone()
    if not old:
        return "no_encontrada"
    req, nombre_vpn, gerente, estado_anterior, observacion_anterior, confirmacion = old
    # El gerente solo valida SUS VPN; se comprueba aquí, no solo en pantalla.
    if current.rol not in ADMINS and manager_key(gerente) not in own_keys:
        raise HTTPException(403, "Solo el gerente asignado puede validar esta VPN")
    if is_answered(estado_anterior, confirmacion):
        return "omitida"
    cursor.execute(f"""
        UPDATE AUTOM.CHECKPOINT_TRANSFORM
           SET ESTADO = :p_estado, OBSERVACION = :p_obs, CONFIRMACION = :p_conf, FECHA_MODIFICACION = SYSDATE
         WHERE CHECKPOINT_UID = :p_uid AND NVL(CONFIRMACION, 0) = 0 AND NOT ({REPORTED_SQL})
    """, {"p_estado": estado, "p_obs": observation, "p_conf": confirmation_for(estado), "p_uid": uid})
    if cursor.rowcount < 1:
        return "omitida"  # Otra sesión la respondió mientras tanto.
    cursor.execute("""
        INSERT INTO AUTOM.LOG_VALIDACION_SOX
          (CHECKPOINT_UID, REQ, NOMBRE_VPN, GERENTE, ACCION, ESTADO_ANTERIOR, ESTADO_NUEVO,
           DECISION_ANTERIOR, DECISION_NUEVA, OBSERVACION_ANTERIOR, OBSERVACION_NUEVA, USUARIO)
        VALUES (:p_uid, :p_req, :p_vpn, :p_ger, :p_acc, :p_ant, :p_est, :p_dant, :p_dest, :p_obs_ant, :p_obs, :p_user)
    """, {"p_uid": uid, "p_req": req, "p_vpn": nombre_vpn, "p_ger": gerente, "p_acc": accion,
          "p_ant": estado_anterior, "p_est": estado, "p_dant": estado_anterior, "p_dest": estado,
          "p_obs_ant": observacion_anterior, "p_obs": observation, "p_user": current.username})
    return None


# ---------------------------------------------------------------- consultas

@router.get("/managers/mine")
def get_my_managers(current: Usuario = Depends(get_current_user)):
    """Nombres de gerente vinculados al usuario en sesión."""
    oracle = OracleConnection()
    try:
        names = _my_manager_names(oracle.connect().cursor(), current.username)
        print(f"[SOX GERENTES] Usuario {current.username!r} vinculado a: {names or 'ningún gerente'}", flush=True)
        return {"usuario": current.username, "gerentes": names}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"No se pudo consultar los gerentes del usuario: {e}")
    finally:
        oracle.close()


@router.get("/validations/mine")
def get_my_validations(current: Usuario = Depends(get_current_user)):
    """VPN externas del gerente en sesión (sin elegir su nombre en un desplegable)."""
    oracle = OracleConnection()
    try:
        cursor = oracle.connect().cursor()
        names = _my_manager_names(cursor, current.username)
        keys = {manager_key(n) for n in names}
        deadline = _active_deadline(cursor)
        items = [_item(r, deadline) for r in _rows(cursor) if manager_key(r["gerente"]) in keys] if keys else []
        print(f"[SOX GERENTES] {current.username!r} -> {names or 'ningún gerente'}: {len(items)} VPN externas",
              flush=True)
        return {"usuario": current.username, "gerentes": names, "items": items}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"No se pudieron consultar tus VPN externas: {e}")
    finally:
        oracle.close()


@router.get("/managers")
def get_managers():
    oracle = OracleConnection()
    try:
        cursor = oracle.connect().cursor()
        cursor.execute("""
            SELECT MIN(GERENTE) GERENTE
              FROM CHECKPOINT_TRANSFORM
             GROUP BY UPPER(TRANSLATE(TRIM(REPLACE(GERENTE, CHR(160), ' ')), 'ÁÉÍÓÚáéíóú', 'AEIOUaeiou'))
             ORDER BY 1
        """)
        return [{"id": index, "name": row[0]} for index, row in enumerate(cursor.fetchall(), start=1)]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        oracle.close()


@router.get("/validations/manager/{manager}")
def get_validations_by_manager(manager: str, current: Usuario = Depends(get_current_user)):
    """VPN de un gerente por nombre (solo administración; el gerente usa /validations/mine)."""
    if current.rol not in ADMINS:
        raise HTTPException(403, "Solo administradores SOX")
    oracle = OracleConnection()
    try:
        cursor = oracle.connect().cursor()
        deadline, key = _active_deadline(cursor), manager_key(manager)
        return [_item(r, deadline) for r in _rows(cursor) if manager_key(r["gerente"]) == key]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        oracle.close()


# ---------------------------------------------------------------- decisiones

@router.patch("/validations/confirm-all")
def confirm_all_validations(request: ValidationConfirmAllRequest, current: Usuario = Depends(get_current_user)):
    if not request.validations:
        raise HTTPException(422, "No hay VPN para guardar")
    # Se valida todo antes de escribir: o se guarda el lote completo o nada.
    items = [(x.checkpoint_uid,) + _clean(x.decision, x.observation) for x in request.validations]
    oracle = OracleConnection()
    connection = None
    try:
        connection = oracle.connect()
        cursor = connection.cursor()
        _check_open(cursor)
        keys = {manager_key(n) for n in _my_manager_names(cursor, current.username)}
        saved, skipped, missing = [], [], []
        for uid, estado, observation in items:
            result = _save(cursor, current, uid, estado, observation, "GUARDAR_MASIVO", keys)
            target = saved if result is None else skipped if result == "omitida" else missing
            target.append(uid)
        connection.commit()
        print(f"[SOX C7 EXTERNAS] GUARDADO MASIVO | {current.username}: {len(saved)} guardadas, "
              f"{len(skipped)} ya respondidas, {len(missing)} no encontradas", flush=True)
        return {"ok": True, "mensaje": "Validaciones guardadas", "total_recibidos": len(items),
                "actualizados": len(saved), "guardadas": saved, "omitidas": skipped, "no_encontrados": missing}
    except HTTPException:
        if connection is not None:
            connection.rollback()
        raise
    except Exception as e:
        if connection is not None:
            connection.rollback()
        print(f"[SOX C7 EXTERNAS] ERROR GUARDADO MASIVO | {current.username}: {e}", flush=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        oracle.close()


@router.patch("/validations/{checkpoint_uid}")
def update_validation(checkpoint_uid: str, data: ValidationConfirmItem, current: Usuario = Depends(get_current_user)):
    estado, observation = _clean(data.decision, data.observation)
    oracle = OracleConnection()
    connection = None
    try:
        connection = oracle.connect()
        cursor = connection.cursor()
        _check_open(cursor)
        keys = {manager_key(n) for n in _my_manager_names(cursor, current.username)}
        result = _save(cursor, current, checkpoint_uid, estado, observation, "MODIFICACION_VALIDACION", keys)
        if result == "no_encontrada":
            raise HTTPException(404, "CHECKPOINT_UID no encontrado")
        if result == "omitida":
            raise HTTPException(409, "Esta VPN ya fue validada y no se puede cambiar")
        connection.commit()
        return {"message": "Validación guardada", "checkpoint_uid": checkpoint_uid,
                "confirmacion": confirmation_for(estado)}
    except HTTPException:
        if connection is not None:
            connection.rollback()
        raise
    except Exception as e:
        if connection is not None:
            connection.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        oracle.close()
