"""Auditoría de activos: listado histórico completo y resumen por dispositivo.

Los endpoints heredan la protección de autenticación del router /assets en main.py.
El registro histórico permanece inalterado: solo se modifica su presentación.
"""

from datetime import date, timedelta
from typing import Optional
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from assets_database import get_assets_db

router = APIRouter()
logger = logging.getLogger(__name__)

FROM_SQL = """
    FROM inventario_dispositivos_log l
    LEFT JOIN inventario_dispositivos d ON d.ID = l.DISPOSITIVO_ID
"""

# Un guion o un texto vacío equivalen a "sin valor". No mostrar como cambio
# valores iguales después de quitar espacios, aunque el trigger los registre.
REAL_CHANGE = """
    COALESCE(NULLIF(NULLIF(TRIM(l.VALOR_ANTERIOR), '-'), ''), CHR(1)) <>
    COALESCE(NULLIF(NULLIF(TRIM(l.VALOR_NUEVO), '-'), ''), CHR(1))
"""

LOG_FIELDS = """
    l.LOG_ID AS "log_id",
    l.DISPOSITIVO_ID AS "dispositivo_id",
    d.DISPOSITIVO AS "dispositivo",
    d.SERIAL AS "serial",
    l.FECHA_CAMBIO AS "fecha_cambio",
    l.USUARIO AS "usuario",
    l.OPERACION AS "operacion",
    l.CAMPO_MODIFICADO AS "campo_modificado",
    l.VALOR_ANTERIOR AS "valor_anterior",
    l.VALOR_NUEVO AS "valor_nuevo",
    l.ORIGEN AS "origen"
"""


def _filters(search=None, campo=None, serial=None, operacion=None,
             fecha_inicio=None, fecha_fin=None, device_id=None):
    conditions = [REAL_CHANGE]
    params = {}

    if search and search.strip():
        conditions.append("""(
            UPPER(COALESCE(d.DISPOSITIVO, ' ')) LIKE :search
            OR UPPER(COALESCE(d.SERIAL, ' ')) LIKE :search
            OR CAST(l.DISPOSITIVO_ID AS TEXT) LIKE :search
        )""")
        params["search"] = f"%{search.strip().upper()}%"

    if serial and serial.strip():
        conditions.append("UPPER(TRIM(d.SERIAL)) = :serial_exacto")
        params["serial_exacto"] = serial.strip().upper()

    if campo and campo.strip():
        conditions.append("UPPER(TRIM(l.CAMPO_MODIFICADO)) = :campo")
        params["campo"] = campo.strip().upper()

    if operacion and operacion.strip():
        conditions.append("UPPER(TRIM(l.OPERACION)) = :operacion")
        params["operacion"] = operacion.strip().upper()

    if fecha_inicio:
        conditions.append("l.FECHA_CAMBIO >= :fecha_inicio")
        params["fecha_inicio"] = fecha_inicio
    if fecha_fin:
        conditions.append("l.FECHA_CAMBIO < :fecha_fin_exclusiva")
        params["fecha_fin_exclusiva"] = fecha_fin + timedelta(days=1)
    if device_id is not None:
        conditions.append("l.DISPOSITIVO_ID = :device_id")
        params["device_id"] = device_id

    return "WHERE " + " AND ".join(conditions), params


def _serialize(row):
    item = dict(row)
    value = item.get("fecha_cambio")
    if value is not None and hasattr(value, "isoformat"):
        item["fecha_cambio"] = value.isoformat()
    return item


def _error(exc):
    logger.exception("Error consultando auditoría de activos")
    raise HTTPException(
        status_code=500,
        detail="No fue posible consultar el historial de activos.",
    ) from exc


@router.get("/logs")
def get_asset_logs(
    search: Optional[str] = None,
    campo: Optional[str] = None,
    serial: Optional[str] = None,
    operacion: Optional[str] = None,
    fecha_inicio: Optional[date] = None,
    fecha_fin: Optional[date] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_assets_db),
):
    """Historial completo por campo; el frontend lo utiliza para exportar TODO.

    Mantiene la estructura de la API anterior para no romper consumidores.
    """
    where_sql, params = _filters(search, campo, serial, operacion, fecha_inicio, fecha_fin)
    try:
        total = int(db.execute(text(f"SELECT COUNT(*) {FROM_SQL} {where_sql}"), params).scalar() or 0)
        rows = db.execute(text(f"""
            SELECT {LOG_FIELDS} {FROM_SQL} {where_sql}
            ORDER BY l.FECHA_CAMBIO DESC, l.LOG_ID DESC
            LIMIT :page_size OFFSET :offset
        """), {**params, "offset": (page - 1) * page_size, "page_size": page_size}).mappings().all()
        return {
            "items": [_serialize(row) for row in rows],
            "total": total, "page": page, "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
        }
    except SQLAlchemyError as exc:
        _error(exc)


@router.get("/logs/summary")
def get_asset_logs_summary(
    search: Optional[str] = None,
    campo: Optional[str] = None,
    serial: Optional[str] = None,
    operacion: Optional[str] = None,
    fecha_inicio: Optional[date] = None,
    fecha_fin: Optional[date] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_assets_db),
):
    """UNA FILA POR ACTIVO, con cantidad de campos y última modificación.

    Se agrupa por ID, no por serial: los seriales pueden faltar o repetirse.
    """
    where_sql, params = _filters(search, campo, serial, operacion, fecha_inicio, fecha_fin)
    try:
        total = int(db.execute(text(f"""
            SELECT COUNT(*) FROM (
                SELECT l.DISPOSITIVO_ID
                {FROM_SQL} {where_sql}
                GROUP BY l.DISPOSITIVO_ID
            ) AS agrupado
        """), params).scalar() or 0)

        rows = db.execute(text(f"""
            SELECT
                l.DISPOSITIVO_ID AS "dispositivo_id",
                d.DISPOSITIVO AS "dispositivo",
                d.SERIAL AS "serial",
                MAX(l.FECHA_CAMBIO) AS "fecha_cambio",
                COUNT(*) AS "total_cambios",
                -- Usuario/origen del cambio más reciente (equivale a KEEP DENSE_RANK LAST de Oracle).
                (ARRAY_AGG(l.USUARIO ORDER BY l.FECHA_CAMBIO DESC, l.LOG_ID DESC))[1] AS "usuario",
                (ARRAY_AGG(l.ORIGEN ORDER BY l.FECHA_CAMBIO DESC, l.LOG_ID DESC))[1] AS "origen"
            {FROM_SQL} {where_sql}
            GROUP BY l.DISPOSITIVO_ID, d.DISPOSITIVO, d.SERIAL
            ORDER BY MAX(l.FECHA_CAMBIO) DESC, l.DISPOSITIVO_ID DESC
            LIMIT :page_size OFFSET :offset
        """), {**params, "offset": (page - 1) * page_size, "page_size": page_size}).mappings().all()

        return {
            "items": [_serialize(row) for row in rows],
            "total": total, "page": page, "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
        }
    except SQLAlchemyError as exc:
        _error(exc)


@router.get("/logs/device/{device_id}")
def get_asset_logs_by_device(
    device_id: int,
    search: Optional[str] = None,
    campo: Optional[str] = None,
    serial: Optional[str] = None,
    operacion: Optional[str] = None,
    fecha_inicio: Optional[date] = None,
    fecha_fin: Optional[date] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=200),
    db: Session = Depends(get_assets_db),
):
    """Detalle desplegable paginado: campos con antes, después y fecha exacta."""
    where_sql, params = _filters(search, campo, serial, operacion,
                                 fecha_inicio, fecha_fin, device_id=device_id)
    try:
        total = int(db.execute(text(f"SELECT COUNT(*) {FROM_SQL} {where_sql}"), params).scalar() or 0)
        rows = db.execute(text(f"""
            SELECT {LOG_FIELDS} {FROM_SQL} {where_sql}
            ORDER BY l.FECHA_CAMBIO DESC, l.LOG_ID DESC
            LIMIT :page_size OFFSET :offset
        """), {**params, "offset": (page - 1) * page_size, "page_size": page_size}).mappings().all()
        return {
            "items": [_serialize(row) for row in rows],
            "total": total, "page": page, "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
        }
    except SQLAlchemyError as exc:
        _error(exc)
