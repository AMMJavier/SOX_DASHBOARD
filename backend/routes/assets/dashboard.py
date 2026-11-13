from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from typing import Optional, Dict
from database.assets_database import get_assets_db

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
    db: Session = Depends(get_assets_db),
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
                SUM(CASE WHEN eos < CURRENT_DATE THEN 1 ELSE 0 END) AS eos_vencido
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
            FROM inventario_dispositivos
            WHERE NULLIF(TRIM(ciudad), '') IS NOT NULL
              AND TRIM(ciudad) <> '-'
            GROUP BY INITCAP(LOWER(TRIM(ciudad)))
            ORDER BY cantidad DESC, nombre
            """,
        )

        tipos = _rows(
            db,
            f"""
            SELECT
                COALESCE(INITCAP(NULLIF(TRIM(tipo), '')), 'Sin especificar') AS nombre,
                COUNT(*) AS cantidad
            FROM inventario_dispositivos
            WHERE 1=1 {city_filter}
            GROUP BY COALESCE(INITCAP(NULLIF(TRIM(tipo), '')), 'Sin especificar')
            ORDER BY cantidad DESC, nombre
            """,
            params,
        )

        plataformas = _rows(
            db,
            f"""
            SELECT COALESCE(NULLIF(TRIM(plataforma), ''), 'Sin especificar') AS nombre,
                   COUNT(*) AS cantidad
            FROM inventario_dispositivos
            WHERE 1=1 {city_filter}
            GROUP BY COALESCE(NULLIF(TRIM(plataforma), ''), 'Sin especificar')
            ORDER BY cantidad DESC, nombre
            """,
            params,
        )

        criticidades = _rows(
            db,
            f"""
            SELECT COALESCE(NULLIF(TRIM(criticidad), ''), 'Sin especificar') AS nombre,
                   COUNT(*) AS cantidad
            FROM inventario_dispositivos
            WHERE 1=1 {city_filter}
            GROUP BY COALESCE(NULLIF(TRIM(criticidad), ''), 'Sin especificar')
            ORDER BY cantidad DESC, nombre
            """,
            params,
        )

        estados = _rows(
            db,
            f"""
            SELECT COALESCE(NULLIF(TRIM(estado), ''), 'Sin especificar') AS nombre,
                   COUNT(*) AS cantidad
            FROM inventario_dispositivos
            WHERE 1=1 {city_filter}
            GROUP BY COALESCE(NULLIF(TRIM(estado), ''), 'Sin especificar')
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
            detail="No fue posible consultar el dashboard de activos.",
        ) from exc
