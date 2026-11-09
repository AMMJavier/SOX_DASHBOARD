
"""Gestión de sesiones del Proyecto SOX mediante Oracle."""

import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session
from models import SoxSesion


SESSION_TIMEOUT_MINUTES = 15


def utc_now():
    # Oracle TIMESTAMP sin zona horaria.
    return datetime.now(timezone.utc).replace(tzinfo=None)


def create_session(db: Session, user_id: int) -> str:
    """Crea una sesión única por cada inicio de sesión."""
    now = utc_now()
    session_id = secrets.token_hex(32)

    session = SoxSesion(
        session_id=session_id,
        usuario_id=user_id,
        creado_en=now,
        ultima_actividad=now,
        expira_en=now + timedelta(minutes=SESSION_TIMEOUT_MINUTES),
        revocado=0,
    )

    db.add(session)
    db.commit()

    return session_id


def get_valid_session(db: Session, session_id: str, user_id: int):
    """Comprueba que la sesión exista y siga vigente."""
    if not session_id:
        return None

    session = (
        db.query(SoxSesion)
        .filter(
            SoxSesion.session_id == session_id,
            SoxSesion.usuario_id == user_id,
            SoxSesion.revocado == 0,
            SoxSesion.expira_en > utc_now(),
        )
        .first()
    )

    return session


def refresh_session(db: Session, session_id: str, user_id: int) -> bool:
    """Renueva la sesión únicamente si todavía está vigente."""
    now = utc_now()

    updated = (
        db.query(SoxSesion)
        .filter(
            SoxSesion.session_id == session_id,
            SoxSesion.usuario_id == user_id,
            SoxSesion.revocado == 0,
            SoxSesion.expira_en > now,
        )
        .update(
            {
                SoxSesion.ultima_actividad: now,
                SoxSesion.expira_en: now + timedelta(
                    minutes=SESSION_TIMEOUT_MINUTES
                ),
            },
            synchronize_session=False,
        )
    )

    db.commit()
    return updated == 1


def revoke_session(db: Session, session_id: str, user_id: int) -> bool:
    """Invalida una sesión para impedir reutilizar su token."""
    updated = (
        db.query(SoxSesion)
        .filter(
            SoxSesion.session_id == session_id,
            SoxSesion.usuario_id == user_id,
            SoxSesion.revocado == 0,
        )
        .update(
            {SoxSesion.revocado: 1},
            synchronize_session=False,
        )
    )

    db.commit()
    return updated == 1
