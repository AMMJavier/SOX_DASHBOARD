"""Control 7: vista previa y envío de avisos de apertura de campaña a los gerentes.

Solo administración SOX. El envío se ejecuta en segundo plano (puede tardar varios
minutos con muchos gerentes) y su avance se consulta con la vista previa.
"""
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from auth.dependencies import get_current_user
from models import Usuario
from oracle_database import get_oracle_db
from services import sox_c7_notifications as notifications

router = APIRouter(tags=["SOX - Campaign notifications"])


class SendRequest(BaseModel):
    confirmar: bool = False
    # Vacío = todos los gerentes pendientes con contacto válido.
    claves: Optional[List[str]] = Field(default=None, max_length=500)


@router.get("/campaign/notifications", summary="Vista previa de avisos a gerentes de la campaña activa")
def notifications_preview(db: Session = Depends(get_oracle_db), current: Usuario = Depends(get_current_user)):
    if current.rol != "administrador":
        raise HTTPException(403, "Solo un administrador SOX puede gestionar las notificaciones")
    return notifications.preview(db)


@router.post("/campaign/notifications/send", status_code=202, summary="Enviar avisos pendientes a gerentes")
def notifications_send(payload: SendRequest, background: BackgroundTasks,
                       db: Session = Depends(get_oracle_db), current: Usuario = Depends(get_current_user)):
    campaign, keys = notifications.start_batch(db, current, claves=payload.claves, confirmar=payload.confirmar)
    background.add_task(notifications.run_batch, campaign["id"], keys, current.id, current.username)
    return {"en_cola": len(keys), "campana": campaign["nombre"],
            "mensaje": "Envío iniciado en segundo plano. Actualiza la vista para ver el avance."}
