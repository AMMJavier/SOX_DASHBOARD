"""Control 7 - VPN internas: consulta read-only de los dos grupos LDAP de VPN (RDP y Aplicaciones)."""
from fastapi import APIRouter, Depends, HTTPException

from auth.dependencies import get_current_user
from models import Usuario
from services.sox.control_7.ldap_vpn import read_internal_access, LDAPAccessError

router = APIRouter(prefix="/controls/7/internas", tags=["SOX - Control 7 VPN internas"])


@router.get("/ldap/accesos")
def ldap_vpn_access(current: Usuario = Depends(get_current_user)):
    if current.rol not in ("administrador", "desarrollador"):
        raise HTTPException(403, "Sin permisos para consultar grupos de acceso interno")
    try:
        return read_internal_access()
    except LDAPAccessError as exc:
        raise HTTPException(503, str(exc)) from exc
