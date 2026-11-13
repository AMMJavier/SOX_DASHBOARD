"""SOX Control 6: lectura de membresías directas LDAP RDP/Aplicaciones.

NO escribe en Active Directory, ni necesita CSV. La persistencia Oracle
se realiza de manera independiente tras obtener los DOS grupos completos.

Modo predeterminado: STARTTLS y validación de certificado. Una excepción
TEMPORAL y EXPLÍCITA para STARTTLS no verificado se limita al Control 6;
no modifica el servicio LDAP de autenticación del portal.
"""

from datetime import datetime, timezone
import logging
import os
import ssl
from pathlib import Path
from urllib.parse import urlparse

from ldap3 import Connection, NONE, SIMPLE, SUBTREE, Server, Tls
from ldap3.utils.conv import escape_filter_chars

logger = logging.getLogger(__name__)

LDAP_GROUPS = {
    "RDP": "LDAP_VPN_RDP_CONECEL",
    "APLICACIONES": "LDAP_VPN_APLICACIONES_CONECEL",
}


class LDAPAccessError(Exception):
    """Error controlado sin revelar cuentas ni credenciales LDAP."""


def _enabled(value):
    return str(value or "").strip().lower() in ("true", "yes", "1", "on")


def _integer(name, default, minimum, maximum):
    try:
        result = int(os.getenv(name, str(default)))
    except ValueError as exc:
        raise LDAPAccessError("Parámetro LDAP6 inválido") from exc
    if not minimum <= result <= maximum:
        raise LDAPAccessError("Parámetro LDAP6 fuera del límite permitido")
    return result


def _open_connection():
    server_url = (os.getenv("LDAP6_SERVER") or os.getenv("LDAP_SERVER") or "").strip()
    base = (os.getenv("LDAP_BASE_DN") or "").strip()
    service_user = (os.getenv("LDAP_SERVICE_USER") or "").strip()
    service_password = os.getenv("LDAP_SERVICE_PASSWORD") or ""
    if not all((server_url, base, service_user, service_password)):
        raise LDAPAccessError("Faltan variables LDAP de servicio en el backend")

    parsed = urlparse(server_url if "://" in server_url else "ldap://" + server_url)
    if parsed.scheme not in ("ldap", "ldaps") or not parsed.hostname:
        raise LDAPAccessError("LDAP6_SERVER no contiene una dirección LDAP válida")

    mode = os.getenv("LDAP6_MODE", "starttls_verified").strip().lower()
    if mode not in ("starttls_verified", "starttls_unverified", "ldaps_verified"):
        raise LDAPAccessError("LDAP6_MODE debe ser starttls_verified, starttls_unverified o ldaps_verified")

    if mode == "ldaps_verified" and parsed.scheme != "ldaps":
        raise LDAPAccessError("ldaps_verified requiere LDAP6_SERVER=ldaps://...")
    if mode != "ldaps_verified" and parsed.scheme != "ldap":
        raise LDAPAccessError("STARTTLS requiere LDAP6_SERVER=ldap://...")

    ca_path = (os.getenv("LDAP6_CA_CERT") or os.getenv("LDAP_CA_CERT") or "").strip()
    if mode == "starttls_unverified":
        # Conserva el cifrado, pero desactiva autenticación del servidor:
        # una excepción limitada y temporal, nunca el modo por defecto.
        if not _enabled(os.getenv("LDAP6_ALLOW_UNVERIFIED_TLS")):
            raise LDAPAccessError("STARTTLS sin CA requiere habilitación explícita de seguridad")
        tls = Tls(validate=ssl.CERT_NONE)
        logger.warning("Control 6 usa STARTTLS SIN verificar la identidad del servidor LDAP")
    else:
        if ca_path and not Path(ca_path).is_file():
            raise LDAPAccessError("No se encuentra el archivo CA corporativo LDAP6")
        tls = Tls(validate=ssl.CERT_REQUIRED, ca_certs_file=ca_path or None)

    server = Server(
        parsed.hostname,
        port=parsed.port or (636 if parsed.scheme == "ldaps" else 389),
        use_ssl=(mode == "ldaps_verified"),
        tls=tls,
        get_info=NONE,
        connect_timeout=_integer("LDAP6_CONNECT_TIMEOUT", 8, 2, 60),
    )
    conn = Connection(
        server,
        user=service_user,
        password=service_password,
        authentication=SIMPLE,
        receive_timeout=_integer("LDAP6_READ_TIMEOUT", 30, 5, 120),
        auto_referrals=False,
        raise_exceptions=True,
    )
    try:
        conn.open()
        if mode != "ldaps_verified" and not conn.start_tls():
            raise LDAPAccessError("No fue posible negociar STARTTLS con LDAP")
        if not conn.bind():
            raise LDAPAccessError("Bind de servicio LDAP rechazado")
        return conn, base
    except Exception:
        try:
            conn.unbind()
        except Exception:
            pass
        raise


def _group_dn(conn, base, group_name):
    conn.search(
        search_base=base,
        search_scope=SUBTREE,
        search_filter="(&(objectCategory=group)(cn=" + escape_filter_chars(group_name) + "))",
        attributes=["cn"],
        size_limit=2,
    )
    if len(conn.entries) != 1:
        raise LDAPAccessError("Grupo LDAP no encontrado o duplicado: " + group_name)
    return str(conn.entries[0].entry_dn)


def _first(value):
    if isinstance(value, (list, tuple)):
        return value[0] if value else None
    return value


def _direct_users(conn, base, group_dn, page_size, max_users):
    """Busca usuarios directamente miembros del grupo mediante páginas AD.

    No equivale a grupos anidados ni a sesiones VPN conectadas.
    """
    search_filter = (
        "(&(objectCategory=person)(objectClass=user)(memberOf="
        + escape_filter_chars(group_dn) + "))"
    )
    accounts = {}
    rows = conn.extend.standard.paged_search(
        search_base=base,
        search_filter=search_filter,
        search_scope=SUBTREE,
        attributes=["sAMAccountName", "displayName", "userAccountControl"],
        paged_size=page_size,
        generator=True,
    )
    for item in rows:
        if item.get("type") == "searchResDone":
            result = (item.get("result") or {}).get("result", 0)
            if result != 0:
                raise LDAPAccessError("El controlador no completó la búsqueda paginada")
            continue
        if item.get("type") != "searchResEntry":
            continue
        attrs = item.get("attributes") or {}
        username = str(_first(attrs.get("sAMAccountName")) or "").strip().lower()
        if not username or len(username) > 100 or any(c.isspace() for c in username):
            raise LDAPAccessError("LDAP devolvió una cuenta sin identificador confiable")
        display = str(_first(attrs.get("displayName")) or "").strip()[:200] or None
        flags = _first(attrs.get("userAccountControl"))
        try:
            enabled = None if flags is None else not bool(int(flags) & 2)
        except (ValueError, TypeError):
            enabled = None
        accounts[username] = {"usuario": username, "nombre": display, "activo": enabled}
        if len(accounts) > max_users:
            raise LDAPAccessError("El grupo LDAP supera el máximo configurado")
    return accounts


def read_internal_access():
    """Consulta ambos grupos antes de permitir guardar un corte Oracle."""
    page_size = _integer("LDAP6_PAGE_SIZE", 200, 20, 1000)
    max_users = _integer("LDAP6_MAX_USERS_PER_GROUP", 5000, 100, 20000)
    conn = None
    try:
        conn, base = _open_connection()
        merged = {}
        counts = {}
        for access_type, group_name in LDAP_GROUPS.items():
            dn = _group_dn(conn, base, group_name)
            group_users = _direct_users(conn, base, dn, page_size, max_users)
            if not group_users:
                raise LDAPAccessError("El grupo LDAP " + access_type + " no devolvió cuentas")
            counts[access_type] = len(group_users)
            for username, info in group_users.items():
                if username not in merged:
                    merged[username] = dict(info, fuentes=[])
                merged[username]["fuentes"].append(access_type)
                if not merged[username]["nombre"] and info["nombre"]:
                    merged[username]["nombre"] = info["nombre"]
        return {
            "fuentes": counts,
            "total_membresias": sum(counts.values()),
            "total_cuentas_unicas": len(merged),
            "consulta_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "usuarios": [{**merged[u], "fuentes": sorted(merged[u]["fuentes"])}
                         for u in sorted(merged)],
            "nota": "Membresías LDAP directas; no son sesiones VPN activas ni orden de baja.",
        }
    except LDAPAccessError:
        raise
    except Exception as exc:
        logger.warning("Control 6: lectura LDAP fallida (%s), sin datos personales", type(exc).__name__)
        raise LDAPAccessError("No se completó la consulta LDAP; no se guardó ningún corte") from exc
    finally:
        if conn is not None:
            try:
                conn.unbind()
            except Exception:
                pass
