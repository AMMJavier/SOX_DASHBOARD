"""Previsualizacion y envio explicito de recordatorios, solo para administrador SOX.
El usuario no puede proporcionar destinatarios ni modificar la plantilla mediante la API.
"""
from datetime import datetime, timezone
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text, Integer, outparam
from sqlalchemy.orm import Session

from auth.dependencies import get_current_user
from models import Usuario
from database.oracle_database import get_oracle_db
from services.sox.common.reminder_service import compose, send_via_graph
import os

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/controls", tags=["SOX - recordatorios"])


class RequestReminder(BaseModel):
    anio: int = Field(ge=2020, le=2100)
    semestre: Optional[int] = Field(default=None, ge=1, le=2)
    referencia: str = Field(default="", max_length=150)
    confirmar: bool = False


def _check_admin(user: Usuario):
    if user.rol != "administrador":
        raise HTTPException(403, "Solo un administrador SOX puede gestionar envíos")


@router.post("/{control}/recordatorios/previsualizar")
def preview(control: int, payload: RequestReminder,
            current: Usuario = Depends(get_current_user)):
    _check_admin(current)
    message = compose(control, payload.anio, payload.semestre, payload.referencia)
    return {"mensaje": message, "envio_habilitado": os.getenv("SOX_MAIL_ENABLED", "false").strip().lower() == "true",
            "nota": "Previsualizar no envía correo ni genera programación."}


@router.post("/{control}/recordatorios/enviar")
def send(control: int, payload: RequestReminder,
         current: Usuario = Depends(get_current_user),
         db: Session = Depends(get_oracle_db)):
    _check_admin(current)
    if payload.confirmar is not True:
        raise HTTPException(422, "Requiere confirmación explícita")
    message = compose(control, payload.anio, payload.semestre, payload.referencia)
    if os.getenv("SOX_MAIL_ENABLED", "false").strip().lower() != "true":
        raise HTTPException(503, "Envíos deshabilitados: configurar SOX_MAIL_ENABLED=true tras autorización")
    # La auditoría se registra antes de enviar. Si no hay tabla/permisos, no se envía.
    try:
        record = db.execute(text("""
            INSERT INTO AUTOM.SOX_CONTROL_CORREOS_AUD
              (CONTROL_NUMERO, ANIO, SEMESTRE, ASUNTO, DESTINATARIOS,
               SOLICITADO_POR, ESTADO, FECHA_SOLICITUD)
            VALUES (:control, :anio, :semestre, :asunto, :destinatarios,
                    :usuario, 'PENDIENTE', :ahora)
            RETURNING ID INTO :id
        """).bindparams(outparam("id", Integer)), {"control": control, "anio": payload.anio, "semestre": payload.semestre,
                "asunto": message["asunto"], "destinatarios": ";".join(message["destinatarios"]),
                "usuario": current.id, "ahora": datetime.now(timezone.utc).replace(tzinfo=None)} )
        audit_id = record.out_parameters["id"]
        audit_id = int(audit_id[0] if isinstance(audit_id, (tuple, list)) else audit_id)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("No se pudo registrar la solicitud de correo SOX")
        raise HTTPException(503, "Auditoría de correos no disponible; envío cancelado")
    status = "FALLIDO"
    try:
        result = send_via_graph(message)
        status = "ACEPTADO"
        return {"estado": status, "auditoria_id": audit_id, **result}
    finally:
        # Fallos en esta actualizacion dejan PENDIENTE, para reconciliación manual.
        try:
            db.execute(text("""
                UPDATE AUTOM.SOX_CONTROL_CORREOS_AUD
                   SET ESTADO=:estado, FECHA_RESULTADO=:ahora
                 WHERE ID=:id
            """), {"estado": status, "id": audit_id,
                   "ahora": datetime.now(timezone.utc).replace(tzinfo=None)})
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("No se pudo finalizar el registro de correo SOX id=%s", audit_id)
