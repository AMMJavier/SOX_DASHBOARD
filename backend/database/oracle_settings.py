"""Configuración única para SQLAlchemy y conexiones directas a Oracle.

Usa variables ORACLE_*; por compatibilidad acepta config/oracle_config.json
ya existente en el servidor. No almacenar secretos en el repositorio.
"""
import json
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")  # backend/.env

def get_oracle_config():
    config_file = Path(__file__).resolve().parents[1] / "config" / "oracle_config.json"
    legacy = {}
    if config_file.exists():
        with config_file.open(encoding="utf-8") as fh:
            legacy = json.load(fh).get("oracle", {})
    fields = {
        "user": "ORACLE_USER",
        "password": "ORACLE_PASSWORD",
        "host": "ORACLE_HOST",
        "port": "ORACLE_PORT",
        "service_name": "ORACLE_SERVICE_NAME",
    }
    config = {field: os.getenv(env) or legacy.get(field) for field, env in fields.items()}
    missing = [name for name, val in config.items() if not val]
    if missing:
        raise RuntimeError("Falta configuración de Oracle: " + ", ".join(missing) + ". Usar ORACLE_* o config/oracle_config.json privado")
    try:
        config["port"] = int(config["port"])
    except (TypeError, ValueError) as exc:
        raise RuntimeError("ORACLE_PORT debe ser numérico") from exc
    return config
