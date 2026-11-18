"""Notificaciones/recordatorios por control y calendario (fecha tope), solo administrador SOX.

El usuario no puede proporcionar destinatarios ni modificar la plantilla mediante la API:
ambos vienen de backend/config/correos.json. Cada envío queda auditado en
AUTOM.SOX_MAIL_OUTBOX con ORIGEN='RECORDATORIO' antes de llamar a Microsoft Graph
(services/sox/common/reminder_service.deliver, la misma función del envío automático).
"""
import logging
import time
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from auth.dependencies import get_current_user
from database.oracle_database import get_oracle_db
from models import Usuario
from services.sox.common import mail_service as mail
from services.sox.common import reminder_scheduler
from services.sox.common.reminder_service import compose, deliver, public

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/controls", tags=["SOX - notificaciones"])


class RequestReminder(BaseModel):
    anio: int = Field(ge=2020, le=2100)
    semestre: Optional[int] = Field(default=None, ge=1, le=2)
    referencia: str = Field(default="", max_length=150)
    confirmar: bool = False


def _check_admin(user: Usuario):
    if user.rol != "administrador":
        raise HTTPException(403, "Solo un administrador SOX puede gestionar envíos")


@router.post("/{control}/recordatorios/previsualizar")
def preview(control: int, payload: RequestReminder, current: Usuario = Depends(get_current_user),
            db: Session = Depends(get_oracle_db)):
    _check_admin(current)
    message = compose(control, payload.anio, payload.semestre, payload.referencia, db=db)
    return {"mensaje": public(message), "envio_habilitado": mail._env_bool("SOX_MAIL_ENABLED"),
            "nota": "Previsualizar no envía correo ni genera programación."}


@router.post("/{control}/recordatorios/enviar")
async def send(control: int,
               anio: int = Form(..., ge=2020, le=2100),
               semestre: Optional[int] = Form(None, ge=1, le=2),
               referencia: str = Form("", max_length=150),
               confirmar: bool = Form(False),
               evidencias_ids: str = Form(""),
               adjuntos: Optional[List[UploadFile]] = File(None),
               current: Usuario = Depends(get_current_user),
               db: Session = Depends(get_oracle_db)):
    """Envía la notificación del control; admite adjuntos del equipo y del repositorio."""
    start = time.monotonic()
    mail.console(f"NOTIFICACION Control {control} INICIO | usuario={current.username} anio={anio} "
                 f"semestre={semestre}")
    try:
        _check_admin(current)
        if confirmar is not True:
            raise HTTPException(422, "Requiere confirmación explícita")
        repository_ids = mail.parse_evidence_ids(evidencias_ids)
        files = []
        limit = mail.max_attachment_bytes()
        for upload in adjuntos or []:
            if not upload.filename:
                continue
            content = await upload.read(limit + 1)
            await upload.close()
            if len(content) > limit:
                raise HTTPException(413, "Los adjuntos superan el tamaño permitido")
            files.append((upload.filename, content))
        # Graph es bloqueante: el envío y el archivado se ejecutan fuera del event loop.
        result = await run_in_threadpool(
            deliver, db, control=control, anio=anio, semestre=semestre, referencia=referencia,
            user_id=current.id, username=current.username, adjuntos=files, evidencias_ids=repository_ids)
    except HTTPException as exc:
        mail.console(f"NOTIFICACION Control {control} NO ENVIADA tras {mail.elapsed(start)} | "
                     f"HTTP {exc.status_code}: {exc.detail}")
        raise
    mail.console(f"NOTIFICACION Control {control} ENVIADA (N{control}-{result['auditoria_id']}"
                 f"{', código ' + result['codigo'] if result.get('codigo') else ''}) en {mail.elapsed(start)}")
    return {**result, "aceptado_graph": result["estado"] in ("ACEPTADO", "ARCHIVADO")}


@router.get("/{control}/calendario")
def calendar(control: int, anio: int = Query(ge=2020, le=2100), semestre: Optional[int] = Query(default=None),
             current: Usuario = Depends(get_current_user), db: Session = Depends(get_oracle_db)):
    """Fecha tope del período, días restantes y si venció (para el indicador "Vencidos")."""
    return reminder_scheduler.period_status(db, control, anio, semestre)
