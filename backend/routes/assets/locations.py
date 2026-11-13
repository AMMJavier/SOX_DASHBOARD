from collections import defaultdict
import re
import unicodedata
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from database.assets_database import get_assets_db

router = APIRouter()


def normalize_city(value: str) -> str:
    value = re.sub(r"[\u200b-\u200d\ufeff]", "", str(value or ""))
    value = unicodedata.normalize("NFKC", value)
    value = re.sub(r"\s+", " ", value.strip())
    return "".join(
        character for character in unicodedata.normalize("NFD", value)
        if unicodedata.category(character) != "Mn"
    ).casefold()


@router.get("/locations")
def get_locations(
    ciudad: Optional[str] = Query(default=None),
    db: Session = Depends(get_assets_db),
):
    try:
        result = db.execute(text("""
            SELECT TRIM(ciudad) AS ciudad, COUNT(*) AS cantidad
            FROM inventario_dispositivos
            WHERE NULLIF(TRIM(ciudad), '') IS NOT NULL
              AND TRIM(ciudad) <> '-'
            GROUP BY TRIM(ciudad)
        """))

        grouped = defaultdict(int)
        for row in result.mappings():
            key = normalize_city(row["ciudad"])
            if not key:
                continue
            grouped[key] += int(row["cantidad"] or 0)

        requested = normalize_city(ciudad) if ciudad else None
        items = [
            {"ciudad": key.title(), "cantidad": quantity, "total_dispositivos": quantity}
            for key, quantity in grouped.items()
            if requested is None or key == requested
        ]
        items.sort(key=lambda item: (-item["cantidad"], item["ciudad"]))

        sin_ciudad = int(db.execute(text("""
            SELECT COUNT(*) FROM inventario_dispositivos
            WHERE NULLIF(TRIM(ciudad), '') IS NULL OR TRIM(ciudad) = '-'
        """)).scalar() or 0)
        return {
            "items": items,
            "total_ubicaciones": len(items),
            "total_dispositivos": sum(item["cantidad"] for item in items),
            "sin_ciudad": sin_ciudad,
        }
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=500,
            detail="No fue posible consultar las ubicaciones de activos.",
        ) from exc
