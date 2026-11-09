from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from typing import Optional, Dict
from oracle_database import get_oracle_db

router = APIRouter()


def _rows(db: Session, sql: str, params: Optional[dict] = None) -> list:
    result = db.execute(text(sql), params or {})
    return [
        {str(key).lower(): value for key, value in row.items()}
        for row in result.mappings()
    ]


def _json_value(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


@router.get("/dashboard")
def get_assets_dashboard(
    ciudad: Optional[str] = Query(default=None),
    db: Session = Depends(get_oracle_db),
):
    """
    Resumen del inventario. Los estados se devuelven según sus valores reales
    y no se convierten silenciosamente en categorías inventadas.
    """
    city_filter = " AND UPPER(TRIM(ciudad)) = UPPER(TRIM(:ciudad)) " if ciudad else ""
    params = {"ciudad": ciudad} if ciudad else {}

    try:
        kpi_rows = _rows(
            db,
            f"""
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN UPPER(TRIM(estado)) LIKE 'ACTIVO%' THEN 1 ELSE 0 END) AS activos_vigentes,
                SUM(CASE WHEN UPPER(TRIM(estado)) LIKE 'INACTIVO/NO VIGENTE%' THEN 1 ELSE 0 END) AS inactivos_no_vigentes,
                SUM(CASE WHEN UPPER(TRIM(estado)) LIKE 'INACTIVO/DAÑADO%' OR UPPER(TRIM(estado)) LIKE 'INACTIVO/DANADO%' THEN 1 ELSE 0 END) AS danados,
                SUM(CASE WHEN eos < TRUNC(SYSDATE) THEN 1 ELSE 0 END) AS eos_vencido
            FROM inventario_dispositivos
            WHERE 1=1 {city_filter}
            """,
            params,
        )
        kpis = kpi_rows[0] if kpi_rows else {
            "total": 0, "activos_vigentes": 0,
            "inactivos_no_vigentes": 0, "danados": 0, "eos_vencido": 0,
        }
        kpis = {key: int(value or 0) for key, value in kpis.items()}

        ciudades = _rows(
            db,
            """
            SELECT
                INITCAP(LOWER(TRIM(ciudad))) AS nombre,
                COUNT(*) AS cantidad
            FROM AUTOM.INVENTARIO_DISPOSITIVOS
            WHERE ciudad IS NOT NULL
              AND TRIM(ciudad) <> '-'
            GROUP BY INITCAP(LOWER(TRIM(ciudad)))
            ORDER BY cantidad DESC, nombre
            """,
        )

        tipos = _rows(
            db,
            f"""
            SELECT
                NVL(INITCAP(TRIM(tipo)), 'Sin especificar') AS nombre,
                COUNT(*) AS cantidad
            FROM AUTOM.INVENTARIO_DISPOSITIVOS
            WHERE 1=1 {city_filter}
            GROUP BY NVL(INITCAP(TRIM(tipo)), 'Sin especificar')
            ORDER BY cantidad DESC, nombre
            """,
            params,
        )

        plataformas = _rows(
            db,
            f"""
            SELECT NVL(NULLIF(TRIM(plataforma), ''), 'Sin especificar') AS nombre,
                   COUNT(*) AS cantidad
            FROM inventario_dispositivos
            WHERE 1=1 {city_filter}
            GROUP BY NVL(NULLIF(TRIM(plataforma), ''), 'Sin especificar')
            ORDER BY cantidad DESC, nombre
            """,
            params,
        )

        criticidades = _rows(
            db,
            f"""
            SELECT NVL(NULLIF(TRIM(criticidad), ''), 'Sin especificar') AS nombre,
                   COUNT(*) AS cantidad
            FROM inventario_dispositivos
            WHERE 1=1 {city_filter}
            GROUP BY NVL(NULLIF(TRIM(criticidad), ''), 'Sin especificar')
            ORDER BY cantidad DESC, nombre
            """,
            params,
        )

        estados = _rows(
            db,
            f"""
            SELECT NVL(NULLIF(TRIM(estado), ''), 'Sin especificar') AS nombre,
                   COUNT(*) AS cantidad
            FROM inventario_dispositivos
            WHERE 1=1 {city_filter}
            GROUP BY NVL(NULLIF(TRIM(estado), ''), 'Sin especificar')
            ORDER BY cantidad DESC, nombre
            """,
            params,
        )

       

        return {
            "kpis": kpis,
            "ciudad_seleccionada": ciudad,
            "ciudades": ciudades,
            "tipos": tipos,
            "plataformas": plataformas,
            "criticidades": criticidades,
            "estados": estados,
        }
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=500,
            detail="No fue posible consultar el dashboard de activos en Oracle.",
        ) from exc
