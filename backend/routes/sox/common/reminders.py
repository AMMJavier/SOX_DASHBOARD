"""Previsualización y envío explícito de notificaciones/recordatorios, solo administrador SOX.

El usuario no puede proporcionar destinatarios ni modificar la plantilla mediante la API:
ambos vienen de backend/config/correos.json. Cada envío queda auditado en
AUTOM.SOX_MAIL_OUTBOX con ORIGEN='RECORDATORIO' antes de llamar a Microsoft Graph.
"""
import logging
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import Integer, outparam, text
from sqlalchemy.orm import Session

from auth.dependencies import get_current_user
from database.oracle_database import get_oracle_db
from models import Usuario
from services.sox.common import mail_service as mail
from services.sox.common.reminder_service import compose, send_via_graph

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
def preview(control: int, payload: RequestReminder, current: Usuario = Depends(get_current_user)):
    _check_admin(current)
    message = compose(control, payload.anio, payload.semestre, payload.referencia)
    return {"mensaje": message, "envio_habilitado": mail._env_bool("SOX_MAIL_ENABLED"),
            "nota": "Previsualizar no envía correo ni genera programación."}


@router.post("/{control}/recordatorios/enviar")
def send(control: int, payload: RequestReminder,
         current: Usuario = Depends(get_current_user),
         db: Session = Depends(get_oracle_db)):
    _check_admin(current)
    if payload.confirmar is not True:
        raise HTTPException(422, "Requiere confirmación explícita")
    message = compose(control, payload.anio, payload.semestre, payload.referencia)
    if not mail._env_bool("SOX_MAIL_ENABLED"):
        raise HTTPException(503, "Envíos deshabilitados: configurar SOX_MAIL_ENABLED=true tras autorización")
    mail._graph_paths()  # Falla aquí, antes de registrar, si la integración no está instalada.

    correlation = uuid4().hex
    semestre = payload.semestre if control in (3, 6) else None
    # La auditoría se registra antes de enviar. Si no se puede registrar, no se envía.
    try:
        result = db.execute(text("""
            INSERT INTO AUTOM.SOX_MAIL_OUTBOX
              (CONTROL_NUMERO, ANIO, SEMESTRE, TIPO_EVIDENCIA, ORIGEN, IDEMPOTENCY_KEY, CORRELACION,
               EMISOR, DESTINATARIOS, CC, ASUNTO, CUERPO, ESTADO, SOLICITADO_POR, FECHA_SOLICITUD)
            VALUES (:p_control, :p_anio, :p_sem, 'notificacion', 'RECORDATORIO', :p_idem, :p_corr,
                    :p_emisor, :p_para, :p_cc, :p_asunto, :p_cuerpo, 'PENDIENTE', :p_user, :p_fecha)
            RETURNING ID INTO :p_returned
        """).bindparams(outparam("p_returned", Integer)), {
            "p_control": control, "p_anio": payload.anio, "p_sem": semestre,
            "p_idem": f"N{control}-{correlation}", "p_corr": correlation,
            "p_emisor": message["emisor"], "p_para": "; ".join(message["destinatarios"]),
            "p_cc": "; ".join(message["cc"]) or None, "p_asunto": message["asunto"],
            "p_cuerpo": message["cuerpo"], "p_user": current.id, "p_fecha": mail._now()})
        value = result.out_parameters["p_returned"]
        outbox_id = int(value[0] if isinstance(value, (tuple, list)) else value)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("No se pudo registrar la notificación SOX")
        raise HTTPException(503, "Auditoría de correos no disponible; envío cancelado")

    footer = f"\n\n--\nEnviado desde SOX Dashboard por {current.username}. Referencia SOX: N{control}-{outbox_id}."
    try:
        ok, detail, message_id = send_via_graph({**message, "cuerpo": message["cuerpo"] + footer}, correlation)
    except HTTPException as exc:
        mail._set_state(db, outbox_id, "FALLIDO", f"No se envió: {exc.detail}")
        raise
    if ok is None:
        mail._set_state(db, outbox_id, "PENDIENTE", detail)
        raise HTTPException(504, "Graph no confirmó el envío a tiempo. Revisa el buzón antes de reintentar.")
    if not ok:
        mail._set_state(db, outbox_id, "FALLIDO", detail)
        raise HTTPException(502, "Microsoft Graph no aceptó el envío. Revisar registros del servidor.")
    # Notificación operativa: ACEPTADO es su estado final (no se archiva como evidencia).
    mail._set_state(db, outbox_id, "ACEPTADO", None, FECHA_ENVIO=mail._now(), INTERNET_MESSAGE_ID=message_id)
    return {"estado": "ACEPTADO", "auditoria_id": outbox_id, "aceptado_graph": True}
