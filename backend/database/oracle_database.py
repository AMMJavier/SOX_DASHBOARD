"""Sesiones SQLAlchemy para Oracle; NO ejecuta create_all en producción."""
import os
from sqlalchemy import create_engine, URL
from sqlalchemy.orm import sessionmaker, declarative_base
from database.oracle_settings import get_oracle_config

# La URL alternativa sirve para pruebas automatizadas con SQLite, nunca para producción.
_test_url = os.getenv("SOX_TEST_DATABASE_URL")
if _test_url:
    engine = create_engine(_test_url, pool_pre_ping=True)
else:
    _cfg = get_oracle_config()
    engine = create_engine(URL.create(
        "oracle+oracledb", username=_cfg["user"], password=_cfg["password"],
        host=_cfg["host"], port=_cfg["port"], query={"service_name": _cfg["service_name"]},
    ), pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_oracle_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
