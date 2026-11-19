"""Control 7 - VPN internas (LDAP RDP / APLICACIONES).

Gerente (rol gerencial): solo GET/PATCH fuera de /sox/admin (require_sox_access), y solo sobre
sus propias cuentas (comprobado en services/sox/control_7/internal_vpn.decide).
Administrador / desarrollador: listado completo, resumen por gerente y carga desde LDAP.
"""
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from auth.dependencies import get_current_user
from database.oracle_database import get_oracle_db
from models import Usuario
from services.sox.control_7 import internal_notifications as notices
from services.sox.control_7 import internal_vpn as service

router = APIRouter(tags=["SOX - Control 7 VPN internas"])
ADMINS = {"administrador", "desarrollador"}


class InternalDecision(BaseModel):
    decision: str
    observation: Optional[str] = None


class InternalDecisionItem(InternalDecision):
    id: int


class InternalConfirmAll(BaseModel):
    validations: List[InternalDecisionItem]


def _admin(user: Usuario):
    if user.rol not in ADMINS:
        raise HTTPException(403, "Solo administradores SOX")


@router.get("/internas/mine")
def my_internal_accounts(db: Session = Depends(get_oracle_db), current: Usuario = Depends(get_current_user)):
    """Cuentas con VPN interna a cargo del usuario en sesión (gerente según la cadena de jefes de Active Directory)."""
    return service.list_for_manager(db, current.username)


@router.patch("/internas/confirm-all")
def confirm_all_internal(payload: InternalConfirmAll, db: Session = Depends(get_oracle_db),
                         current: Usuario = Depends(get_current_user)):
    return service.confirm_all(db, items=payload.validations, user=current)


@router.patch("/internas/{item_id}")
def decide_internal(item_id: int, payload: InternalDecision, db: Session = Depends(get_oracle_db),
                    current: Usuario = Depends(get_current_user)):
    return service.decide(db, item_id=item_id, decision=payload.decision, observation=payload.observation,
                          user=current)


@router.get("/campaign/internas")
def list_internal(search: str = Query("", max_length=100), gerente: str = Query("", max_length=100),
                  estado: str = Query("", max_length=20), tipo: str = Query("", max_length=20),
                  campaign_id: Optional[int] = Query(None), offset: int = Query(0, ge=0),
                  limit: int = Query(50, ge=1, le=200),
                  db: Session = Depends(get_oracle_db), current: Usuario = Depends(get_current_user)):
    _admin(current)
    return service.list_admin(db, campaign_id=campaign_id, search=search, gerente=gerente, estado=estado,
                              tipo=tipo, offset=offset, limit=limit)


@router.get("/campaign/internas/dashboard")
def internal_dashboard(gerente: str = Query("", max_length=100), db: Session = Depends(get_oracle_db),
                       current: Usuario = Depends(get_current_user)):
    _admin(current)
    return service.dashboard(db, gerente)


@router.get("/campaign/internas/todas")
def internal_campaign_rows(db: Session = Depends(get_oracle_db), current: Usuario = Depends(get_current_user)):
    _admin(current)
    return service.campaign_rows(db)


@router.get("/campaign/internas/historial/filtros")
def internal_history_filters(db: Session = Depends(get_oracle_db), current: Usuario = Depends(get_current_user)):
    _admin(current)
    return service.history_filters(db)


@router.get("/campaign/internas/historial")
def internal_history(campaign_id: Optional[int] = Query(None), year: Optional[int] = Query(None),
                     manager: str = Query("", max_length=200), status: str = Query("", max_length=20),
                     tipo: str = Query("", max_length=20), search: str = Query("", max_length=100),
                     db: Session = Depends(get_oracle_db), current: Usuario = Depends(get_current_user)):
    _admin(current)
    return service.history(db, campaign_id=campaign_id, year=year, manager=manager, status=status,
                           tipo=tipo, search=search)


@router.get("/campaign/internas/seguimiento")
def internal_audit_log(db: Session = Depends(get_oracle_db), current: Usuario = Depends(get_current_user)):
    _admin(current)
    return service.audit_log(db)


class NoticeRequest(BaseModel):
    confirmar: bool = False
    claves: Optional[List[str]] = Field(default=None, max_length=500)  # Vacío = todos los pendientes.


@router.get("/campaign/internas/notificaciones")
def internal_notifications_preview(db: Session = Depends(get_oracle_db), current: Usuario = Depends(get_current_user)):
    if current.rol != "administrador":
        raise HTTPException(403, "Solo un administrador SOX puede gestionar las notificaciones")
    return notices.preview(db)


@router.post("/campaign/internas/notificaciones/enviar", status_code=202)
def internal_notifications_send(payload: NoticeRequest, background: BackgroundTasks,
                                db: Session = Depends(get_oracle_db), current: Usuario = Depends(get_current_user)):
    campaign, keys = notices.start_batch(db, current, claves=payload.claves, confirmar=payload.confirmar)
    background.add_task(notices.run_batch, campaign["id"], keys, current.id, current.username)
    return {"en_cola": len(keys), "campana": campaign["nombre"],
            "mensaje": "Envío iniciado en segundo plano. Actualiza la vista para ver el avance."}


class ManualManager(BaseModel):
    ids: List[int] = Field(..., min_length=1, max_length=2000)
    usuario: str = Field(..., max_length=100)
    nombre: Optional[str] = Field(None, max_length=200)
    correo: Optional[str] = Field(None, max_length=254)


@router.get("/campaign/internas/gerentes")
def internal_managers(db: Session = Depends(get_oracle_db), current: Usuario = Depends(get_current_user)):
    """Gerentes que ya tienen cuentas en la campaña activa (para asignar a mano)."""
    _admin(current)
    return service.campaign_managers(db)


@router.get("/campaign/internas/gerentes/ad/{usuario}")
async def internal_manager_lookup(usuario: str, current: Usuario = Depends(get_current_user)):
    """Busca un usuario en AD para completar el nombre y el correo del gerente."""
    _admin(current)
    person = await run_in_threadpool(service.find_ad_manager, usuario)
    if not person:
        raise HTTPException(404, "El usuario no existe en AD: escribe el nombre y el correo a mano")
    return person


@router.post("/campaign/internas/asignar-gerente")
async def internal_assign_manager(payload: ManualManager, db: Session = Depends(get_oracle_db),
                                  current: Usuario = Depends(get_current_user)):
    """El administrador asigna un gerente a cuentas sin gerente en AD (casos especiales)."""
    _admin(current)
    return await run_in_threadpool(lambda: service.assign_manager(
        db, item_ids=payload.ids, usuario=payload.usuario, nombre=payload.nombre, correo=payload.correo,
        user=current))


@router.post("/campaign/internas/cargar")
async def load_internal(reemplazar: bool = Query(False), db: Session = Depends(get_oracle_db),
                        current: Usuario = Depends(get_current_user)):
    """Vuelve a tomar la foto LDAP de la campaña activa.

    reemplazar=false: actualiza y conserva las decisiones confirmadas.
    reemplazar=true: borra la carga anterior y la carga desde cero (solo sin confirmaciones).
    """
    _admin(current)
    return await run_in_threadpool(service.load_from_ldap, db, None, reemplazar)
