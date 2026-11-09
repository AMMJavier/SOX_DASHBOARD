"""Sesiones SQLAlchemy para el módulo Assets sobre PostgreSQL.

Assets ya no usa Oracle: autenticación y SOX siguen en oracle_database.py.

Configuración (en backend/.env, nunca en el repositorio):
    ASSETS_DATABASE_URL   URL completa, p. ej. postgresql+psycopg2://user:pass@host:5432/db
  o bien, por partes:
    POSTGRES_HOST, POSTGRES_PORT (5432), POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD
  opcional:
    POSTGRES_SCHEMA       esquema de las tablas de inventario (por defecto: autom)
    POSTGRES_SSLMODE      p. ej. require / verify-full

El motor se crea al primer uso: la API arranca aunque Postgres no esté
configurado y solo fallan los endpoints /assets.
"""
import os
import re
from pathlib import Path
from typing import Iterator, Optional

from dotenv import load_dotenv
from sqlalchemy import URL, create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

load_dotenv(Path(__file__).resolve().parent / ".env")

_engine: Optional[Engine] = None
_SessionLocal: Optional[sessionmaker] = None


def _schema() -> str:
    schema = os.getenv("POSTGRES_SCHEMA", "autom").strip() or "autom"
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", schema):
        raise RuntimeError("POSTGRES_SCHEMA contiene caracteres no permitidos")
    return schema


def _build_engine() -> Engine:
    # URL alternativa para pruebas automatizadas (SQLite), nunca para producción.
    test_url = os.getenv("ASSETS_TEST_DATABASE_URL")
    if test_url:
        return create_engine(test_url, pool_pre_ping=True)

    connect_args = {"options": f"-csearch_path={_schema()},public"}
    sslmode = os.getenv("POSTGRES_SSLMODE")
    if sslmode:
        connect_args["sslmode"] = sslmode

    full_url = os.getenv("ASSETS_DATABASE_URL")
    if full_url:
        return create_engine(full_url, pool_pre_ping=True, connect_args=connect_args)

    fields = {
        "host": "POSTGRES_HOST",
        "database": "POSTGRES_DB",
        "username": "POSTGRES_USER",
        "password": "POSTGRES_PASSWORD",
    }
    cfg = {key: os.getenv(env) for key, env in fields.items()}
    missing = [env for key, env in fields.items() if not cfg[key]]
    if missing:
        raise RuntimeError(
            "Falta configuración de PostgreSQL para Assets: " + ", ".join(missing)
            + ". Definir ASSETS_DATABASE_URL o POSTGRES_* en backend/.env"
        )
    try:
        port = int(os.getenv("POSTGRES_PORT", "5432"))
    except ValueError as exc:
        raise RuntimeError("POSTGRES_PORT debe ser numérico") from exc

    url = URL.create("postgresql+psycopg2", port=port, **cfg)
    return create_engine(url, pool_pre_ping=True, connect_args=connect_args)


def get_assets_engine() -> Engine:
    global _engine, _SessionLocal
    if _engine is None:
        _engine = _build_engine()
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
    return _engine


def get_assets_db() -> Iterator[Session]:
    get_assets_engine()
    db = _SessionLocal()
    try:
        yield db
    finally:
        db.close()


def set_audit_context(db: Session, usuario: Optional[str], origen: str) -> None:
    """Indica al trigger de auditoría quién y desde dónde hace el cambio.

    Los valores son locales a la transacción actual (set_config(..., true)),
    por lo que no se filtran a otras peticiones que reutilicen la conexión.
    """
    if db.get_bind().dialect.name != "postgresql":
        return
    db.execute(
        text("SELECT set_config('app.usuario', :usuario, true), set_config('app.origen', :origen, true)"),
        {"usuario": usuario or "", "origen": origen},
    )
