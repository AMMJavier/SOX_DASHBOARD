from datetime import date, datetime
from typing import Optional, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from database.assets_database import get_assets_db, set_audit_context
from auth.dependencies import get_current_user
from models import Usuario
from .upload import validate_row, ALLOWED_COLUMNS, INVALID_SERIALS, EOS_SIN_DEFINIR

router = APIRouter()
# El esquema (autom) lo fija el search_path de la conexión PostgreSQL.
TABLE = "inventario_dispositivos"
SELECT_COLUMNS = """
    id, especialidad, plataforma, tipo, dispositivo, estado, criticidad,
    infraestructura, ip, mask, gateway, mac, localidad, piso, lado, ciudad,
    so, version, firmware, fabricante, modelo, serial, licencia, eos, comentario
"""


def _serialize(row) -> dict:
    result = {str(key).lower(): value for key, value in row.items()}
    for key, value in result.items():
        if isinstance(value, (datetime, date)):
            result[key] = value.isoformat()
    return result


@router.get("/inventory/options")
def inventory_options(db: Session = Depends(get_assets_db)):
    """Valores reales de la base, sin depender de la página actual."""
    try:
        options = {}
        for field in ("tipo", "ciudad", "localidad"):
            # En PostgreSQL '' no es NULL (en Oracle sí): excluir ambos.
            rows = db.execute(text(f"""
                SELECT DISTINCT TRIM({field}) AS valor
                FROM {TABLE}
                WHERE NULLIF(TRIM({field}), '') IS NOT NULL
                ORDER BY valor
            """)).scalars().all()
            options[field] = [value for value in rows if value]
        return options
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=500, detail="No fue posible cargar las opciones de filtros.") from exc


@router.get("/inventory")
def get_inventory(
    q: Optional[str] = Query(default=None, description="Buscar dispositivo, IP, MAC, serial, fabricante, comentario o ID"),
    id: Optional[int] = Query(default=None, ge=1),
    ciudad: Optional[str] = None,
    serial: Optional[str] = Query(default=None, description="Serial exacto del equipo"),
    localidad: Optional[str] = None,
    estado: Optional[str] = None,
    plataforma: Optional[str] = None,
    tipo: Optional[str] = None,
    fabricante: Optional[str] = None,
    eos: Optional[str] = Query(default=None, pattern="^(vencido|generico|vigente)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
    db: Session = Depends(get_assets_db),
):
    conditions = []
    params = {}

    if id is not None:
        conditions.append("id = :device_id")
        params["device_id"] = id

    for column, value in (
        ("ciudad", ciudad), ("localidad", localidad), ("estado", estado),
        ("plataforma", plataforma), ("tipo", tipo), ("fabricante", fabricante),
    ):
        if value and value.strip():
            conditions.append(f"UPPER(TRIM({column})) = UPPER(TRIM(:{column}))")
            params[column] = value.strip()

    if serial and serial.strip():
        conditions.append("UPPER(TRIM(serial)) = :serial_exacto")
        params["serial_exacto"] = serial.strip().upper()

    if q and q.strip():
        conditions.append("""(
            UPPER(COALESCE(dispositivo, ' ')) LIKE :q OR
            UPPER(COALESCE(ip, ' ')) LIKE :q OR
            UPPER(COALESCE(mac, ' ')) LIKE :q OR
            UPPER(COALESCE(serial, ' ')) LIKE :q OR
            UPPER(COALESCE(fabricante, ' ')) LIKE :q OR
            UPPER(COALESCE(modelo, ' ')) LIKE :q OR
            UPPER(COALESCE(ciudad, ' ')) LIKE :q OR
            UPPER(COALESCE(localidad, ' ')) LIKE :q OR
            UPPER(COALESCE(comentario, ' ')) LIKE :q OR
            CAST(id AS TEXT) LIKE :q
        )""")
        params["q"] = f"%{q.strip().upper()}%"

    # "No anunciado" tiene prioridad sobre la fecha del EOS.
    generic = "POSITION('no anunciado' IN LOWER(COALESCE(comentario, ' '))) > 0"
    not_generic = f"NOT ({generic})"
    if eos == "generico":
        conditions.append(generic)
    elif eos == "vencido":
        conditions.append(f"({not_generic} AND eos IS NOT NULL AND eos < CURRENT_DATE)")
    elif eos == "vigente":
        # La fecha 2099-12-31 es un valor provisional, no un EOS real vigente.
        conditions.append(f"({not_generic} AND eos IS NOT NULL AND eos >= CURRENT_DATE AND eos <> DATE '2099-12-31')")

    where_sql = " WHERE " + " AND ".join(conditions) if conditions else ""
    offset = (page - 1) * page_size

    try:
        total = int(db.execute(
            text(f"SELECT COUNT(*) FROM {TABLE}{where_sql}"), params
        ).scalar() or 0)
        rows = db.execute(
            text(f"""
                SELECT {SELECT_COLUMNS}
                FROM {TABLE}
                {where_sql}
                ORDER BY id DESC
                LIMIT :page_size OFFSET :offset
            """),
            {**params, "offset": offset, "page_size": page_size},
        ).mappings()
        return {
            "items": [_serialize(row) for row in rows],
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": (total + page_size - 1) // page_size,
            },
        }
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=500, detail="No fue posible consultar el inventario de activos.") from exc


@router.patch("/inventory/{device_id}")
def update_inventory_device(
    device_id: int,
    changes: dict[str, Any] = Body(...),
    db: Session = Depends(get_assets_db),
    current: Usuario = Depends(get_current_user),
):
    """Actualiza exclusivamente los campos enviados de un activo existente.

    El enrutador /assets ya exige autenticación. Solo assets_admin puede
    realizar cambios. El historial lo registra el trigger PostgreSQL
    trg_inventario_dispositivos_audit; no se insertan logs desde aquí.
    """
    if current.rol != "assets_admin":
        raise HTTPException(status_code=403, detail="Solo Assets Admin puede editar activos.")
    if not isinstance(changes, dict) or not changes:
        raise HTTPException(status_code=422, detail="Debes enviar al menos un campo para modificar.")

    invalid = sorted(set(changes) - ALLOWED_COLUMNS)
    if invalid:
        raise HTTPException(status_code=422, detail=f"Campos no permitidos: {', '.join(invalid)}")

    try:
        normalized, _ = validate_row(changes)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    try:
        set_audit_context(db, current.username, "EDICION_WEB")
        current_row = db.execute(
            text(f"SELECT {SELECT_COLUMNS} FROM {TABLE} WHERE id = :device_id FOR UPDATE"),
            {"device_id": device_id},
        ).mappings().first()
        if current_row is None:
            db.rollback()
            raise HTTPException(status_code=404, detail="El activo no existe.")

        before = {str(k).lower(): v for k, v in current_row.items()}
        altered = {}
        for col, value in normalized.items():
            # El guion, el campo vacío o EOS 2099 provisional se interpretan como
            # "sin información nueva". Nunca borrar ni auditar por ese motivo.
            if value is None or (col == "eos" and value == EOS_SIN_DEFINIR):
                continue
            previous = before[col]
            if col == "eos" and isinstance(previous, datetime):
                previous = previous.date()
            if isinstance(previous, str) and isinstance(value, str):
                if previous.strip() == value.strip():
                    continue
            if previous != value:
                altered[col] = value

        # Impedir que al editar fabricante/serial se cree otra identidad igual.
        if altered and ("serial" in altered or "fabricante" in altered):
            maker = str(normalized.get("fabricante", before.get("fabricante")) or "").strip()
            sn = str(normalized.get("serial", before.get("serial")) or "").strip()
            invalid_ids = INVALID_SERIALS | {"", "-"}
            if maker.upper() not in invalid_ids and sn.upper() not in invalid_ids:
                duplicates = db.execute(text(f"""
                    SELECT COUNT(*) FROM {TABLE}
                    WHERE id <> :device_id
                      AND UPPER(TRIM(fabricante)) = :maker
                      AND UPPER(TRIM(serial)) = :sn
                """), {"device_id": device_id, "maker": maker.upper(), "sn": sn.upper()}).scalar()
                if duplicates:
                    db.rollback()
                    raise HTTPException(status_code=409, detail="Ya existe otro activo con ese fabricante y serial.")

        if altered:
            assignments = ", ".join(f"{col} = :val_{col}" for col in altered)
            binds = {f"val_{col}": val for col, val in altered.items()}
            db.execute(text(f"UPDATE {TABLE} SET {assignments} WHERE id = :device_id"),
                       {**binds, "device_id": device_id})
        # Al confirmar, la auditoría existente (si está habilitada) registra el UPDATE.
        db.commit()
        result = db.execute(text(f"SELECT {SELECT_COLUMNS} FROM {TABLE} WHERE id = :device_id"),
                            {"device_id": device_id}).mappings().first()
        return {"item": _serialize(result), "actualizado": bool(altered), "campos_modificados": list(altered)}
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="No se pudo actualizar el activo.") from exc
