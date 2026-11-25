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
    data = control(number)
    return _dedupe(_list(load().get("copias_generales")) + _list(data.get("copias")) + _list(data.get("cc")))


def notification(number) -> dict:
    """Notificación/recordatorio del control: destinatarios, copias propias, asunto y cuerpo."""
    data = control(number).get("notificacion") or {}
    recipients = _list(data.get("destinatarios")) or _list(os.getenv(f"SOX_REMINDER_TO_{number}", ""))
    # "copias" o "cc": ambos nombres se aceptan en notificacion.
    copies = _list(data.get("copias")) + _list(data.get("cc"))
    return {"destinatarios": _dedupe(recipients), "copias": _dedupe(copies),
            "asunto": data.get("asunto"), "cuerpo": data.get("cuerpo")}


def notification_controls() -> set:
    return {int(k) for k, v in (load().get("controles") or {}).items()
            if str(k).isdigit() and isinstance(v, dict) and v.get("notificacion")}


def draft_template(number) -> dict | None:
    """Plantilla para prellenar el correo formal del control (p. ej. Control 5 por evento)."""
    data = control(number).get("correo_formal")
    if not data:
        return None
    return {"asunto": _text(data.get("asunto")), "cuerpo": _text(data.get("cuerpo"))}


def _hour(value, name):
    """8 (hora entera) o "09:15" (hora y minutos). Inválido -> 08:00."""
    raw = str(value).strip()
    match = re.fullmatch(r"(\d{1,2})(?::(\d{2}))?", raw)
    hour, minute = (int(match.group(1)), int(match.group(2) or 0)) if match else (-1, 0)
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        logger.error("%s inválida %r en correos.json (usar HH:MM); se usa 08:00", name, raw)
        return 8, 0
    return hour, minute


def automatic() -> dict:
    """Envío automático de recordatorios y alertas (correos.json > automatico)."""
    data = load().get("automatico") or {}
    hour, minute = _hour(data.get("hora_desde", 8), "automatico.hora_desde")
    return {
        "activo": data.get("activo") is True,
        "hora_desde": f"{hour:02d}:{minute:02d}",
        "minuto_del_dia": hour * 60 + minute,
        "usuario": str(data.get("usuario") or "").strip(),
    }


def calendar(number) -> dict:
    """Calendario del control (correos.json > controles.<n>.calendario).

    fechas en formato "MM-DD":
      recordatorios      días en que se envía la notificación automática
      fecha_tope         fecha límite de evidencias; una por año (control anual) o
                         una por semestre (controles semestrales)
      alerta_dias_antes  si falta evidencia, alerta N días antes de la fecha tope
      adjuntar_ultimo    {"controles": [2], "tipos": ["plan"], "automatico": false}: con
                         automatico=true adjunta solo el último archivo subido; si no, no
                         se adjunta nada y el administrador elige los archivos al enviar
    """
    data = control(number).get("calendario") or {}

    def dates(value):
        valid = []
        for item in _list(value):
            if re.fullmatch(r"(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])", item):
                valid.append(item)
            else:
                logger.error("Fecha inválida %r en correos.json > controles.%s.calendario (usar MM-DD)", item, number)
        return sorted(set(valid))

    attach = data.get("adjuntar_ultimo") or None
    if attach:
        attach = {
            "controles": [int(x) for x in _list(attach.get("controles")) if str(x).isdigit()] or [int(number)],
            "tipos": _list(attach.get("tipos")),
            # Por defecto NO se adjunta solo: el administrador elige los archivos al enviar.
            "automatico": attach.get("automatico") is True,
        }
    try:
        days = int(data.get("alerta_dias_antes", 0) or 0)
    except (TypeError, ValueError):
        days = 0
    return {
        "recordatorios": dates(data.get("recordatorios")),
        "fecha_tope": dates(data.get("fecha_tope")),
        "alerta_dias_antes": max(days, 0),
        "adjuntar_ultimo": attach,
    }


def alert_template(number) -> dict:
    """Texto de la alerta de evidencia faltante (controles.<n>.alerta o valores por defecto)."""
    data = control(number).get("alerta") or {}
    return {"asunto": data.get("asunto"), "cuerpo": data.get("cuerpo")}


def c7_internal_notice() -> dict:
    """Aviso a gerentes de VPN internas (controles.7.aviso_gerentes_internas). El modo prueba
    es el mismo de aviso_gerentes. Sin textos, se usan los de internal_notifications.py."""
    data = control(7).get("aviso_gerentes_internas") or {}
    return {"asunto": data.get("asunto"), "cuerpo": data.get("cuerpo")}


def c7_daily_reminder() -> dict:
    """Recordatorio diario a gerentes con VPN por validar (controles.7.recordatorio_diario).

    No envía nada si falta el bloque, si "activo" no es true o si automatico.activo es false.
    El modo prueba y las copias son los de aviso_gerentes y del propio bloque ("copias").
    """
    data = control(7).get("recordatorio_diario") or {}
    general = automatic()
    hour, minute = _hour(data.get("hora_desde", general["hora_desde"]), "recordatorio_diario.hora_desde")
    test = data.get("modo_prueba") or {}
    def number(value):
        try:
            return max(int(value or 0), 0)
        except (TypeError, ValueError):
            return 0
    max_test = number(test.get("max_correos_por_ronda", test.get("max_correos_por_dia", 0)))
    interval = number(test.get("intervalo_minutos"))
    return {
        "activo": data.get("activo") is True and general["activo"],
        # Modo prueba PROPIO del recordatorio: con activo=true nunca va a los gerentes, aunque
        # aviso_gerentes esté en modo real. max_correos_por_dia: 0 = sin límite.
        "modo_prueba": bool(test.get("activo")) and bool(_list(test.get("destinatarios"))),
        "destinatarios_prueba": _dedupe(_list(test.get("destinatarios"))),
        "max_prueba": max_test,
        # Solo en modo prueba: repetir cada N minutos desde hora_desde (0 = una vez al día).
        "intervalo_prueba": interval,
        "hora_desde": f"{hour:02d}:{minute:02d}",
        "minuto_del_dia": hour * 60 + minute,
        "copias": _dedupe(_list(data.get("copias"))),
        "asunto": data.get("asunto"),
        "cuerpo": data.get("cuerpo"),
    }


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
        # false = al iniciar campaña NO se sobrescriben los correos de SOX_GERENTES_CONTACTO desde LDAP
        # (útil para pruebas con correos cambiados a mano). Por defecto true.
        "sincronizar_contactos_ldap": data.get("sincronizar_contactos_ldap", True) is not False,
    }
