"""Endpoint read-only de dos grupos LDAP internos para Control 6."""
from fastapi import APIRouter, Depends, HTTPException

from auth.dependencies import get_current_user
from models import Usuario
from services.sox.control_6.ldap_access import read_internal_access, LDAPAccessError

router = APIRouter(prefix="/controls/6", tags=["SOX control 6 - LDAP"])


@router.get("/ldap/accesos")
def ldap_access(current: Usuario = Depends(get_current_user)):
    if current.rol not in ("administrador", "desarrollador"):
        raise HTTPException(403, "Sin permisos para consultar grupos de acceso interno")
    try:
        return read_internal_access()
    except LDAPAccessError as exc:
        raise HTTPException(503, str(exc)) from exc
