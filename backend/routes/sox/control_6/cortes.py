"""Control 6: consulta de cortes Oracle y sincronización manual desde LDAP seguro.

No realiza escrituras sobre el directorio ni procesa cesantías automáticamente.
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from auth.dependencies import get_current_user
from models import Usuario
from services.sox.control_6.cortes import cut_accounts, latest_cut, from_live_report, store_cut
from services.sox.control_6.ldap_access import LDAPAccessError, read_internal_access

router = APIRouter(prefix="/controls/6/ldap/cortes", tags=["SOX Control 6 - cortes LDAP"])


def _permission(user):
    if user.rol not in ("administrador", "desarrollador"):
        raise HTTPException(status_code=403, detail="Solo equipo técnico SOX autorizado")


@router.get("/ultimo")
def latest(user: Usuario = Depends(get_current_user)):
    _permission(user)
    return {"corte": latest_cut()}


@router.get("/{corte_id}/usuarios")
def accounts(corte_id: int, offset: int = Query(0, ge=0, le=100000),
             limite: int = Query(50, ge=1, le=200),
             buscar: str = Query("", max_length=100),
             grupo: str = Query(""), user: Usuario = Depends(get_current_user)):
    _permission(user)
    try:
        result = cut_accounts(corte_id, offset=offset, limit=limite, search=buscar, access=grupo)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    if result is None:
        raise HTTPException(404, "Corte LDAP no encontrado")
    return result


@router.post("/sincronizar", status_code=201)
def sync_now(user: Usuario = Depends(get_current_user)):
    _permission(user)
    try:
        report = read_internal_access()
        rows = from_live_report(report)
        return store_cut(rows, "LDAP_EN_VIVO", actor_id=user.id, extracted_at=datetime.now(timezone.utc))
    except (LDAPAccessError, OSError) as exc:
        raise HTTPException(503, "LDAP no disponible. Se mantiene el corte anterior.") from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
