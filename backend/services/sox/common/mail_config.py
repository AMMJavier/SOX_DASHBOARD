"""Configuración central de correos SOX: backend/config/correos.json.

Un único archivo define remitente, dominios permitidos, destinatarios, copias (CC)
y plantillas (asunto/cuerpo) de todos los controles. Para agregar dominios,
correos o cambiar textos solo se edita el JSON; no hace falta tocar código.

- Se relee automáticamente cuando el archivo cambia (no requiere reiniciar la API).
- Si el JSON no existe o le falta una clave, se usan las variables del .env
  (SOX_MAIL_SENDER, SOX_MAIL_ALLOWED_DOMAINS, SOX_REMINDER_TO_<n>) como respaldo.
- Ruta alternativa: variable SOX_MAIL_CONFIG.
- Los cuerpos admiten texto o lista de líneas (más fácil de editar en JSON).
- Variables en plantillas: {nombre}. Si una variable no existe se deja tal cual.
"""
from __future__ import annotations  # Python 3.9 en el servidor

import json
import logging
import os
import re
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_PATH = Path(__file__).resolve().parents[3] / "config" / "correos.json"
_lock = threading.Lock()
_cache = {"mtime": None, "path": None, "data": {}}


def config_path() -> Path:
    custom = os.getenv("SOX_MAIL_CONFIG", "").strip()
    return Path(custom) if custom else DEFAULT_PATH


def load() -> dict:
    """Devuelve el JSON vigente; lo relee solo si cambió en disco."""
    path = config_path()
    try:
        mtime = path.stat().st_mtime
    except FileNotFoundError:
        if _cache["path"] != str(path) or _cache["mtime"] is not None:
            logger.warning("No existe %s: se usan las variables del .env", path)
        _cache.update(mtime=None, path=str(path), data={})
        return {}
    with _lock:
        if _cache["mtime"] != mtime or _cache["path"] != str(path):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    raise ValueError("la raíz debe ser un objeto")
            except (OSError, ValueError) as exc:
                # Un JSON mal escrito no debe tumbar la API: se conserva la última versión válida.
                logger.error("correos.json inválido (%s); se mantiene la configuración anterior", exc)
                return _cache["data"]
            _cache.update(mtime=mtime, path=str(path), data=data)
            logger.info("Configuración de correos cargada desde %s", path)
    return _cache["data"]


# ---------------------------------------------------------------- utilidades

def _list(value):
    if not value:
        return []
    if isinstance(value, str):
        value = re.split(r"[,;\s]+", value)
    return [str(x).strip() for x in value if str(x).strip()]


def _dedupe(items):
    seen, result = set(), []
    for item in items:
        if item.casefold() not in seen:
            seen.add(item.casefold())
            result.append(item)
    return result


def _text(value):
    if isinstance(value, list):
        return "\n".join(str(x) for x in value)
    return str(value or "")


class _Safe(dict):
    def __missing__(self, key):
        return "{" + key + "}"


def render(template, **values) -> str:
    """Reemplaza {variables}; las desconocidas quedan como texto."""
    return _text(template).format_map(_Safe({k: ("" if v is None else v) for k, v in values.items()}))


def control(number) -> dict:
    return (load().get("controles") or {}).get(str(number)) or {}


# ---------------------------------------------------------------- valores

def sender() -> str:
    return str(load().get("remitente") or os.getenv("SOX_MAIL_SENDER", "")).strip()


def allowed_domains() -> list:
    raw = load().get("dominios_permitidos")
    items = _list(raw) if raw else _list(os.getenv("SOX_MAIL_ALLOWED_DOMAINS", ""))
    return sorted({x.lower().lstrip("@") for x in items})


def cc(number) -> list:
    """Copias fijas: las generales más las del control."""
    return _dedupe(_list(load().get("copias_generales")) + _list(control(number).get("copias")))


def notification(number) -> dict:
    """Notificación/recordatorio del control: destinatarios, asunto y cuerpo."""
    data = control(number).get("notificacion") or {}
    recipients = _list(data.get("destinatarios")) or _list(os.getenv(f"SOX_REMINDER_TO_{number}", ""))
    return {"destinatarios": _dedupe(recipients), "asunto": data.get("asunto"), "cuerpo": data.get("cuerpo")}


def notification_controls() -> set:
    return {int(k) for k, v in (load().get("controles") or {}).items()
            if str(k).isdigit() and isinstance(v, dict) and v.get("notificacion")}


def draft_template(number) -> dict | None:
    """Plantilla para prellenar el correo formal del control (p. ej. Control 5 por evento)."""
    data = control(number).get("correo_formal")
    if not data:
        return None
    return {"asunto": _text(data.get("asunto")), "cuerpo": _text(data.get("cuerpo"))}


def c7_notice() -> dict:
    """Aviso de apertura de campaña a gerentes (Control 7)."""
    data = control(7).get("aviso_gerentes") or {}
    test = data.get("modo_prueba") or {}
    return {
        "modo_prueba": bool(test.get("activo")) and bool(_list(test.get("destinatarios"))),
        "destinatarios_prueba": _dedupe(_list(test.get("destinatarios"))),
        "nota_prueba": _text(test.get("nota")),
        "asunto": data.get("asunto"),
        "cuerpo": data.get("cuerpo"),
    }
