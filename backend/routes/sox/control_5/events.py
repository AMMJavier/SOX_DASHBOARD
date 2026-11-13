"""Control 5: registro individual de cambios en cuentas administradoras de firewall.

No ejecuta cambios en firewalls ni sustituye las aprobaciones emitidas por Jefatura.
"""
from datetime import date, datetime, time, timezone
from typing import Optional, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import text, Integer, outparam
from sqlalchemy.orm import Session

from auth.dependencies import get_current_user
from models import Usuario
from database.oracle_database import get_oracle_db

router = APIRouter(prefix="/controls/5", tags=["SOX control 5 - eventos administradores"])
RESPONSABLES = {"administrador", "desarrollador"}


def _guard(user: Usuario):
    if user.rol not in RESPONSABLES:
        raise HTTPException(status_code=403, detail="Control 5 restringido al personal responsable")


class EventCreate(BaseModel):
    cuenta: str = Field(min_length=2, max_length=100)
    operacion: Literal["ALTA", "MODIFICACION", "BAJA"]
    fecha_evento: date
    perfil: Optional[str] = Field(default=None, max_length=150)
    ticket: Optional[str] = Field(default=None, max_length=150)
    descripcion: Optional[str] = Field(default=None, max_length=1000)

    @field_validator("cuenta", "perfil", "ticket", "descripcion")
    @classmethod
    def limpiar(cls, value):
        if value is None:
            return None
        text_value = value.strip()
        if not text_value:
            return None
        if any(ord(char) < 32 or ord(char) == 127 for char in text_value):
            raise ValueError("El campo contiene caracteres de control")
        return text_value


def _serialize(row):
    data = dict(row)
    for key, value in data.items():
        if isinstance(value, datetime):
            data[key] = value.isoformat()
        elif isinstance(value, date):
            data[key] = value.isoformat()
    return data


@router.get("/eventos")
def listar_eventos(anio: int = Query(..., ge=2020, le=2100),
                   db: Session = Depends(get_oracle_db),
                   user: Usuario = Depends(get_current_user)):
    _guard(user)
    rows = db.execute(text("""
      SELECT ev.ID AS "id", ev.ANIO AS "anio", ev.CUENTA AS "cuenta",
             ev.OPERACION AS "operacion", ev.FECHA_EVENTO AS "fecha_evento",
             ev.PERFIL AS "perfil", ev.TICKET AS "ticket",
             ev.DESCRIPCION AS "descripcion", ev.CREADO_EN AS "creado_en",
             u.USERNAME AS "creado_por",
             (SELECT COUNT(*) FROM AUTOM.SOX_CONTROL_EVIDENCIAS e
               WHERE e.EVENTO_ID=ev.ID) AS "total_archivos",
             (SELECT COUNT(*) FROM AUTOM.SOX_CONTROL_EVIDENCIAS e
               WHERE e.EVENTO_ID=ev.ID AND e.TIPO_EVIDENCIA='aprobacion') AS "aprobaciones",
             (SELECT COUNT(*) FROM AUTOM.SOX_CONTROL_EVIDENCIAS e
               WHERE e.EVENTO_ID=ev.ID AND e.TIPO_EVIDENCIA='ejecucion') AS "ejecuciones"
      FROM AUTOM.SOX_CONTROL5_EVENTOS ev
      JOIN AUTOM.USUARIOS u ON u.ID=ev.CREADO_POR
      WHERE ev.ANIO=:anio
      ORDER BY ev.FECHA_EVENTO DESC, ev.ID DESC
    """), {"anio": anio}).mappings()
    items = [_serialize(row) for row in rows]
    return {"items": items, "total": len(items),
            "pendientes_aprobacion": sum(int(x["aprobaciones"] or 0) == 0 for x in items),
            "pendientes_ejecucion": sum(int(x["ejecuciones"] or 0) == 0 for x in items)}


@router.post("/eventos", status_code=201)
def crear_evento(data: EventCreate, db: Session = Depends(get_oracle_db),
                 user: Usuario = Depends(get_current_user)):
    _guard(user)
    if data.cuenta is None:
        raise HTTPException(422, "Cuenta requerida")
    if not 2020 <= data.fecha_evento.year <= 2100:
        raise HTTPException(422, "Fecha fuera del periodo admitido")
    try:
        stmt = text("""
          INSERT INTO AUTOM.SOX_CONTROL5_EVENTOS
            (ANIO, CUENTA, OPERACION, FECHA_EVENTO, PERFIL, TICKET,
             DESCRIPCION, CREADO_POR, CREADO_EN)
          VALUES (:anio, :cuenta, :operacion, :fecha, :perfil, :ticket,
                  :descripcion, :usuario, :creado)
          RETURNING ID INTO :returned_id
        """).bindparams(outparam("returned_id", Integer))
        result = db.execute(stmt, {
            "anio": data.fecha_evento.year,
            "cuenta": data.cuenta, "operacion": data.operacion,
            "fecha": datetime.combine(data.fecha_evento, time.min),
            "perfil": data.perfil, "ticket": data.ticket,
            "descripcion": data.descripcion, "usuario": user.id,
            "creado": datetime.now(timezone.utc).replace(tzinfo=None),
        })
        value = result.out_parameters["returned_id"]
        new_id = int(value[0] if isinstance(value, (list, tuple)) else value)
        db.commit()
        return {"id": new_id, "mensaje": "Evento registrado; adjuntar evidencia individual"}
    except Exception:
        db.rollback()
        raise
