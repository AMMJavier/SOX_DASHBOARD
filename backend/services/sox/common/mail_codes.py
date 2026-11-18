"""Códigos de correo SOX y configuración de formatos (backend/config/formatos.json).

Código: <código del control>-<serie>[.<reenvío>]  ->  001-1, 001-1.1, 001-1.2, 001-2 ...
  - Primer correo del período (año, o año + semestre)  -> serie nueva (máxima del control + 1).
  - Otro correo en el MISMO período                    -> misma serie, reenvío + 1.
El código va en el asunto como "[SOX 001-1]"; las respuestas lo conservan y así se
asocian al correo original (services/sox/common/reply_service.py).

Si formatos.json no existe se usan los valores por defecto de DEFAULTS (Control 1 activo).
Un control sin entrada en "controles" no lleva código ni lectura de respuestas.
"""
from __future__ import annotations  # Python 3.9 en el servidor

import json
import logging
import os
import re
import threading
from pathlib import Path

from sqlalchemy import text

logger = logging.getLogger(__name__)

DEFAULT_PATH = Path(__file__).resolve().parents[3] / "config" / "formatos.json"
FORMATS = {"pdf", "eml", "ambos"}
CODE_RE = re.compile(r"\[SOX\s+(\d{3}-\d+(?:\.\d+)?)\]", re.IGNORECASE)
DEFAULTS = {
    "revision_respuestas_min": 10,
    "controles": {
        "1": {
            "codigo": "001",
            "formato_archivo": "pdf",
            "tipo_evidencia_notificacion": "solicitud",
            "respuestas": {"activo": True, "palabras_aprobacion": ["ok", "aprobado", "aprobada", "apruebo"],
                           "tipo_evidencia": "aprobacion"},
        },
    },
}
_lock = threading.Lock()
_cache = {"mtime": None, "path": None, "data": None}


def config_path() -> Path:
    custom = os.getenv("SOX_FORMATS_CONFIG", "").strip()
    return Path(custom) if custom else DEFAULT_PATH


def load() -> dict:
    """formatos.json vigente (se relee si cambió); sin archivo, DEFAULTS."""
    path = config_path()
    try:
        mtime = path.stat().st_mtime
    except FileNotFoundError:
        return DEFAULTS
    with _lock:
        if _cache["mtime"] != mtime or _cache["path"] != str(path):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    raise ValueError("la raíz debe ser un objeto")
            except (OSError, ValueError) as exc:
                logger.error("formatos.json inválido (%s); se mantiene la configuración anterior", exc)
                return _cache["data"] or DEFAULTS
            _cache.update(mtime=mtime, path=str(path), data=data)
    return _cache["data"]


def settings(control) -> dict | None:
    """Configuración del control o None si no usa códigos."""
    raw = (load().get("controles") or {}).get(str(control))
    if not isinstance(raw, dict):
        return None
    code = str(raw.get("codigo") or f"{int(control):03d}").strip()
    if not re.fullmatch(r"\d{3}", code):
        logger.error("formatos.json: código inválido %r para el Control %s (usar 3 dígitos)", code, control)
        code = f"{int(control):03d}"
    fmt = str(raw.get("formato_archivo") or "pdf").strip().lower()
    if fmt not in FORMATS:
        logger.error("formatos.json: formato_archivo %r inválido en el Control %s; se usa pdf", fmt, control)
        fmt = "pdf"
    replies = raw.get("respuestas") or {}
    words = [str(w).strip().casefold() for w in (replies.get("palabras_aprobacion") or ["ok"]) if str(w).strip()]
    return {
        "codigo": code,
        "formato_archivo": fmt,
        "tipo_evidencia_notificacion": str(raw.get("tipo_evidencia_notificacion") or "solicitud"),
        "respuestas_activo": replies.get("activo", True) is not False,
        "palabras_aprobacion": words or ["ok"],
        "tipo_evidencia_respuesta": str(replies.get("tipo_evidencia") or "aprobacion"),
    }


def coded_controls() -> set:
    return {int(k) for k in (load().get("controles") or {}) if str(k).isdigit() and settings(k)}


def reply_controls() -> set:
    return {c for c in coded_controls() if settings(c)["respuestas_activo"]}


def check_minutes() -> int:
    try:
        return max(2, min(int(load().get("revision_respuestas_min", 10)), 240))
    except (TypeError, ValueError):
        return 10


def archive_format(control) -> str:
    """Formato de archivado del control; sin configuración, "ambos" (comportamiento anterior)."""
    cfg = settings(control)
    return cfg["formato_archivo"] if cfg else "ambos"


# ---------------------------------------------------------------- códigos

def _period_filter():
    return ("CONTROL_NUMERO = :p_control AND ANIO = :p_anio "
            "AND ((:p_semestre IS NULL AND SEMESTRE IS NULL) OR SEMESTRE = :p_semestre)")


def next_code(db, control, anio, semestre):
    """(codigo, serie, reenvio) que tendría el próximo correo del período, o (None, None, None)."""
    cfg = settings(control)
    if not cfg:
        return None, None, None
    params = {"p_control": control, "p_anio": anio, "p_semestre": semestre}
    serie = db.execute(text(f"""
        SELECT MAX(CODIGO_SERIE) FROM AUTOM.SOX_MAIL_OUTBOX
         WHERE {_period_filter()} AND CODIGO_SERIE IS NOT NULL
    """), params).scalar()
    if serie:
        reenvio = int(db.execute(text("""
            SELECT NVL(MAX(CODIGO_REENVIO), 0) + 1 FROM AUTOM.SOX_MAIL_OUTBOX
             WHERE CONTROL_NUMERO = :p_control AND CODIGO_SERIE = :p_serie
        """), {"p_control": control, "p_serie": int(serie)}).scalar())
        serie = int(serie)
    else:
        serie = int(db.execute(text("""
            SELECT NVL(MAX(CODIGO_SERIE), 0) + 1 FROM AUTOM.SOX_MAIL_OUTBOX WHERE CONTROL_NUMERO = :p_control
        """), {"p_control": control}).scalar())
        reenvio = 0
    return format_code(cfg["codigo"], serie, reenvio), serie, reenvio


def format_code(prefix, serie, reenvio):
    return f"{prefix}-{serie}" + (f".{reenvio}" if reenvio else "")


def subject_with_code(subject, code, max_len=200):
    tag = f" [SOX {code}]"
    return subject[:max_len - len(tag)].rstrip() + tag


def code_footer(code):
    return (f"\nCódigo SOX: {code}. Para aprobar, responda a este correo con \"OK\" "
            "sin modificar el asunto.")


def find_code(subject):
    match = CODE_RE.search(subject or "")
    return match.group(1) if match else None
