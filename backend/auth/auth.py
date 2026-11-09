from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from oracle_database import get_oracle_db
from models import Usuario
from schemas import LoginRequest, TokenResponse, ChangePasswordRequest
from auth.ldap_service import authenticate_ldap
from auth.security import verify_password, create_access_token, get_password_hash
from auth.dependencies import get_current_user, SOX_ROLES, ASSETS_ROLES
from auth.session_service import (
    create_session,
    refresh_session,
    revoke_session,
)
from auth.security import decode_access_token
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError

router = APIRouter(prefix="/auth", tags=["Autenticación"])

@router.post("/login", response_model=TokenResponse)
def login(credentials: LoginRequest, db: Session = Depends(get_oracle_db)):
    username = credentials.username.strip().lower()
    user = db.query(Usuario).filter(func.lower(Usuario.username) == username, Usuario.activo == 1).first()
    # Respuesta uniforme: evita enumerar usuarios y cuentas desactivadas.
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales incorrectas")
    authenticated = False
    if user.auth_provider == "local":
        authenticated = verify_password(credentials.password, user.password_hash)
    elif user.auth_provider == "ldap":
        authenticated = authenticate_ldap(user.username, credentials.password)
    if not authenticated:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales incorrectas")
    try:
        session_id = create_session(db, user.id)
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="No fue posible crear la sesión"
        )

    token = create_access_token({
        "sub": user.username,
        "id": user.id,
        "rol": user.rol,
        "jti": session_id
    })

    return {
        "access_token": token,
        "token_type": "bearer",
        "rol": user.rol
    }

@router.get("/me")
def me(current: Usuario = Depends(get_current_user)):
    modules = (["sox"] if current.rol in SOX_ROLES else []) + (["assets"] if current.rol in ASSETS_ROLES else [])
    return {"id": current.id, "username": current.username, "rol": current.rol,
            "auth_provider": current.auth_provider, "modulos": modules, "activo": bool(current.activo)}

@router.post("/cambiar-contrasena", status_code=204)
def cambiar_contrasena(body: ChangePasswordRequest, db: Session = Depends(get_oracle_db),
                      current: Usuario = Depends(get_current_user)):
    if current.auth_provider != "local":
        raise HTTPException(status_code=400, detail="La contraseña LDAP debe cambiarse en el directorio corporativo")
    if not verify_password(body.password_actual, current.password_hash):
        raise HTTPException(status_code=400, detail="Contraseña actual incorrecta")
    if body.password_actual == body.password_nueva:
        raise HTTPException(status_code=400, detail="La nueva contraseña debe ser diferente")
    try:
        current.password_hash = get_password_hash(body.password_nueva)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    from datetime import datetime, timezone
    current.actualizado_en = datetime.now(timezone.utc).replace(tzinfo=None)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Error al actualizar contraseña")

@router.post("/actividad")
def registrar_actividad(
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer()),
    current: Usuario = Depends(get_current_user),
    db: Session = Depends(get_oracle_db),
):
    try:
        payload = decode_access_token(credentials.credentials)
        session_id = payload.get("jti")

        if not isinstance(session_id, str) or not session_id:
            raise ValueError("Sesión inválida")

    except (JWTError, ValueError, TypeError):
        raise HTTPException(
            status_code=401,
            detail="Token inválido"
        )

    if not refresh_session(db, session_id, current.id):
        raise HTTPException(
            status_code=401,
            detail="Sesión expirada o revocada"
        )

    return {"message": "Actividad registrada"}

@router.post("/logout")
def cerrar_sesion(
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer()),
    current: Usuario = Depends(get_current_user),
    db: Session = Depends(get_oracle_db),
):
    try:
        payload = decode_access_token(credentials.credentials)
        session_id = payload.get("jti")

        if not isinstance(session_id, str) or not session_id:
            raise ValueError("Sesión inválida")

    except (JWTError, ValueError, TypeError):
        raise HTTPException(
            status_code=401,
            detail="Token inválido"
        )

    if not revoke_session(db, session_id, current.id):
        raise HTTPException(
            status_code=401,
            detail="Sesión expirada o revocada"
        )

    return {"message": "Sesión cerrada correctamente"}