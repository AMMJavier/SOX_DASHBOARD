"""Resumen general de los controles SOX (pantalla de inicio del portal SOX)."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from auth.dependencies import get_current_user
from database.oracle_database import get_oracle_db
from models import Usuario
from services.sox.common.overview import overview

router = APIRouter(tags=["SOX - resumen general"])


@router.get("/resumen")
async def sox_overview(db: Session = Depends(get_oracle_db), current: Usuario = Depends(get_current_user)):
    """Estado del período vigente de los controles 1, 2, 3, 5, 6 y 7 (solo administración SOX)."""
    if current.rol not in ("administrador", "desarrollador"):
        raise HTTPException(403, "Solo administradores SOX")
    return await run_in_threadpool(overview, db)
