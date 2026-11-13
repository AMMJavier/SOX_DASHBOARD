"""CRUD administrativo de usuarios de AUTOM.USUARIOS con segregación SOX / Assets."""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session
from database.oracle_database import get_oracle_db
from models import Usuario, SoxSesion
from schemas import CreateUserRequest, UsuarioAdminResponse, UsuarioEstadoRequest, ResetUserPasswordRequest
from auth.dependencies import require_admin
from auth.security import get_password_hash

router = APIRouter(prefix="/usuarios", tags=["Administración de usuarios"])
ROLES_GESTIONABLES = {
    "administrador": frozenset({"administrador", "gerencial", "desarrollador", "assets_admin", "assets_viewer"}),
    "assets_admin": frozenset({"assets_admin", "assets_viewer"}),
}

def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)

def verificar_rol_objetivo(admin: Usuario, rol: str):
    if rol not in ROLES_GESTIONABLES.get(admin.rol, frozenset()):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="No está autorizado para administrar usuarios de ese rol")

def to_response(user: Usuario) -> UsuarioAdminResponse:
    return UsuarioAdminResponse.model_validate(user)

@router.get("/permisos")
def permisos_admin(admin: Usuario = Depends(require_admin)):
    return {"modulo": "assets" if admin.rol == "assets_admin" else "global",
            "rol_actual": admin.rol, "roles_creables": sorted(ROLES_GESTIONABLES[admin.rol])}

@router.get("", response_model=list[UsuarioAdminResponse])
def listar_usuarios(db: Session = Depends(get_oracle_db), admin: Usuario = Depends(require_admin)):
    roles = tuple(ROLES_GESTIONABLES[admin.rol])
    users = db.query(Usuario).filter(Usuario.rol.in_(roles)).order_by(Usuario.username.asc()).all()
    return [to_response(user) for user in users]

@router.post("", response_model=UsuarioAdminResponse, status_code=status.HTTP_201_CREATED)
def crear_usuario(payload: CreateUserRequest, db: Session = Depends(get_oracle_db),
                  admin: Usuario = Depends(require_admin)):
    verificar_rol_objetivo(admin, payload.rol)
    exists = db.query(Usuario.id).filter(func.lower(Usuario.username) == payload.username).first()
    if exists:
        raise HTTPException(status_code=409, detail="El nombre de usuario ya está registrado")
    user = Usuario(username=payload.username, auth_provider=payload.auth_provider, rol=payload.rol,
                   password_hash=get_password_hash(payload.password) if payload.auth_provider == "local" else None,
                   activo=1, creado_en=_now(), actualizado_en=_now())
    try:
        db.add(user)
        db.commit()
        db.refresh(user)
        return to_response(user)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="El usuario infringe una restricción en Oracle") from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="No fue posible registrar el usuario en Oracle") from exc

@router.patch("/{usuario_id}/estado", response_model=UsuarioAdminResponse)
def actualizar_estado(usuario_id: int, payload: UsuarioEstadoRequest,
                      db: Session = Depends(get_oracle_db), admin: Usuario = Depends(require_admin)):
    user = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    verificar_rol_objetivo(admin, user.rol)
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="No puedes modificar el estado de tu propia cuenta")
    user.activo = int(payload.activo)
    user.actualizado_en = _now()
    try:
        db.commit()
        db.refresh(user)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="No fue posible actualizar el usuario en Oracle") from exc
    return to_response(user)

@router.delete("/{usuario_id}", status_code=204)
def eliminar_usuario(usuario_id: int, db: Session = Depends(get_oracle_db),
                     admin: Usuario = Depends(require_admin)):
    """Elimina definitivamente la cuenta y sus sesiones. Solo administrador SOX.

    El administrador de Assets únicamente puede activar/desactivar.
    Si otras tablas referencian al usuario (FK), Oracle rechaza el borrado y se
    sugiere desactivarlo en su lugar para conservar la trazabilidad.
    """
    if admin.rol != "administrador":
        raise HTTPException(status_code=403, detail="Solo el administrador SOX puede eliminar usuarios; desactívalo en su lugar")
    user = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    verificar_rol_objetivo(admin, user.rol)
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="No puedes eliminar tu propia cuenta")
    try:
        db.query(SoxSesion).filter(SoxSesion.usuario_id == user.id).delete(synchronize_session=False)
        db.delete(user)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="El usuario tiene registros asociados y no puede eliminarse; desactívalo en su lugar") from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="No fue posible eliminar el usuario en Oracle") from exc

@router.patch("/{usuario_id}/contrasena", status_code=204)
def resetear_contrasena(usuario_id: int, payload: ResetUserPasswordRequest,
                       db: Session = Depends(get_oracle_db), admin: Usuario = Depends(require_admin)):
    user = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    verificar_rol_objetivo(admin, user.rol)
    if user.auth_provider != "local":
        raise HTTPException(status_code=400, detail="La contraseña LDAP sólo puede gestionarse en el directorio")
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="Use /auth/cambiar-contrasena para su cuenta")
    try:
        user.password_hash = get_password_hash(payload.password_nueva)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    user.actualizado_en = _now()
    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="No fue posible restablecer la contraseña") from exc
