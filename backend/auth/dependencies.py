from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.orm import Session
from sqlalchemy import func

from oracle_database import get_oracle_db
from models import Usuario
from auth.security import decode_access_token
from auth.session_service import get_valid_session

SOX_ROLES = frozenset({"administrador", "gerencial", "desarrollador"})
ASSETS_ROLES = frozenset({"administrador","assets_admin", "assets_viewer", "desarrollador"})
ADMIN_ROLES = frozenset({"administrador", "assets_admin"})
bearer_scheme = HTTPBearer(auto_error=False)

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_oracle_db),
) -> Usuario:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Se requiere autenticación", headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = decode_access_token(credentials.credentials)
        username, user_id = payload.get("sub"), payload.get("id")
        session_id = payload.get("jti")
        if not isinstance(session_id, str) or not session_id:
            raise ValueError("Identificador de sesión inválido")
        if not isinstance(username, str) or not username or user_id is None or isinstance(user_id, bool):
            raise ValueError("Claims incompletos")
        user_id = int(user_id)
    except (JWTError, ValueError, TypeError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido o expirado", headers={"WWW-Authenticate": "Bearer"})
    user = (db.query(Usuario).filter(
        Usuario.id == user_id,
        func.lower(Usuario.username) == username.lower(),
        Usuario.activo == 1,
    ).first())

    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario no encontrado o inactivo", headers={"WWW-Authenticate": "Bearer"})
    
    # Validar que el JWT corresponda a una sesión vigente en Oracle.
    session = get_valid_session(
        db=db,
        session_id=session_id,
        user_id=user_id,
    )

    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesión expirada o revocada",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # El rol y el estado actuales proceden de Oracle.
    return user


def require_admin(user: Usuario = Depends(get_current_user)) -> Usuario:
    if user.rol not in ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="Se requiere administración de SOX o Assets")
    return user

def require_sox_access(request: Request, user: Usuario = Depends(get_current_user)) -> Usuario:
    if user.rol not in SOX_ROLES:
        raise HTTPException(status_code=403, detail="No tiene acceso al módulo SOX")
    # Gerencial conserva las validaciones PATCH; no administra campañas ni paneles administrativos.
    if user.rol == "gerencial" and (request.method in {"POST", "PUT", "DELETE"} or request.url.path.startswith("/sox/admin/")):
        raise HTTPException(status_code=403, detail="Se requiere administración SOX para esta operación")
    return user

def require_assets_access(request: Request, user: Usuario = Depends(get_current_user)) -> Usuario:
    if user.rol not in ASSETS_ROLES:
        raise HTTPException(status_code=403, detail="No tiene acceso al módulo Assets")
    if user.rol == "assets_viewer" and request.method not in {"GET", "HEAD", "OPTIONS"}:
        raise HTTPException(status_code=403, detail="Rol Assets de sólo lectura")
    return user
