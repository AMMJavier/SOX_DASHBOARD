"""Correo formal SOX (Controles 1, 2, 3 y 5 por evento): envío por Graph y archivado como evidencia.

Solo el equipo responsable (administrador / desarrollador) puede enviar o consultar.
Los destinatarios se restringen a los dominios corporativos configurados.
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from starlette.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from auth.dependencies import get_current_user
from models import Usuario
from database.oracle_database import get_oracle_db
from routes.sox.common.evidence import _check_writer
from services.sox.common import mail_service as mail

router = APIRouter(prefix="/controls", tags=["SOX - correo formal y evidencia"])


@router.get("/{control}/correos/config")
def mail_config(control: int, current: Usuario = Depends(get_current_user)):
    _check_writer(current)
    return mail.config_status(control)


@router.get("/{control}/correos")
def list_mails(control: int, anio: int = Query(...), semestre: Optional[int] = Query(None),
               evento_id: Optional[int] = Query(None),
               db: Session = Depends(get_oracle_db), current: Usuario = Depends(get_current_user)):
    _check_writer(current)
    return {"items": mail.list_outbox(db, control, anio, semestre, evento_id)}


@router.post("/{control}/correos", status_code=201)
async def send_mail(
    control: int,
    anio: int = Form(...),
    semestre: Optional[int] = Form(None),
    tipo: str = Form(...),
    para: str = Form(...),
    cc: str = Form(""),
    asunto: str = Form(...),
    cuerpo: str = Form(...),
    idempotency_key: str = Form(...),
    evidencias_ids: str = Form(""),
    evento_id: Optional[int] = Form(None),
    adjuntos: Optional[List[UploadFile]] = File(None),
    db: Session = Depends(get_oracle_db),
    current: Usuario = Depends(get_current_user),
):
    _check_writer(current)
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
    # El envío y el archivado llaman a Graph (bloqueante): se ejecutan fuera del event loop.
    try:
        return await run_in_threadpool(
            mail.send_mail, db, control=control, anio=anio, semestre=semestre, tipo=tipo,
            para=para, cc=cc, asunto=asunto, cuerpo=cuerpo, adjuntos=files,
            idempotency_key=idempotency_key, user=current, evidencias_ids=repository_ids,
            evento_id=evento_id,
        )
    except HTTPException as exc:
        mail.console(f"CORREO FORMAL Control {control} NO ENVIADO | HTTP {exc.status_code}: {exc.detail}")
        raise


@router.post("/{control}/correos/{outbox_id}/archivar")
async def archive_mail(control: int, outbox_id: int,
                       db: Session = Depends(get_oracle_db), current: Usuario = Depends(get_current_user)):
    """Reintenta SOLO el archivado de un correo ya aceptado; nunca lo reenvía."""
    _check_writer(current)
    return await run_in_threadpool(mail.archive_mail, db, control=control, outbox_id=outbox_id, user=current)
