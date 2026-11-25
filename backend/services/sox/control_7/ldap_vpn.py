"""SOX Control 7 - VPN internas: lectura de los grupos LDAP de VPN (RDP y Aplicaciones).

Todo lo de VPN de LDAP (LDAP_VPN_RDP_CONECEL y LDAP_VPN_APLICACIONES_CONECEL) vive aquí,
en el Control 7. NO escribe en Active Directory ni necesita CSV.

Variables del .env: LDAP7_SERVER, LDAP7_MODE, LDAP7_ALLOW_UNVERIFIED_TLS, LDAP7_CA_CERT,
LDAP7_PAGE_SIZE, LDAP7_MAX_USERS_PER_GROUP, LDAP7_CONNECT_TIMEOUT y LDAP7_READ_TIMEOUT.
Mientras el .env del servidor tenga los nombres antiguos LDAP6_*, se leen como respaldo.

Modo predeterminado: STARTTLS y validación de certificado. STARTTLS no verificado es una
excepción TEMPORAL y EXPLÍCITA; no modifica el LDAP de autenticación del portal.
"""

from datetime import datetime, timezone
import logging
import os
import ssl
from pathlib import Path
from urllib.parse import urlparse

from ldap3 import BASE, Connection, NONE, SIMPLE, SUBTREE, Server, Tls
from ldap3.utils.conv import escape_filter_chars

logger = logging.getLogger(__name__)

LDAP_GROUPS = {
    "RDP": "LDAP_VPN_RDP_CONECEL",
    "APLICACIONES": "LDAP_VPN_APLICACIONES_CONECEL",
}


class LDAPAccessError(Exception):
    """Error controlado sin revelar cuentas ni credenciales LDAP."""


CONTEXT = "Control 7 (VPN internas)"


def _env(name, default=None):
    """LDAP7_<name>; si no existe, el nombre antiguo LDAP6_<name> (compatibilidad del .env)."""
    value = os.getenv("LDAP7_" + name)
    if value is None or not value.strip():
        value = os.getenv("LDAP6_" + name)
    return default if value is None or not value.strip() else value


def _enabled(value):
    return str(value or "").strip().lower() in ("true", "yes", "1", "on")


def _integer(name, default, minimum, maximum):
    """Entero LDAP7_<name> (o LDAP6_<name>) dentro de sus límites."""
    try:
        result = int(_env(name, str(default)))
    except ValueError as exc:
        raise LDAPAccessError("Parámetro LDAP7_" + name + " inválido") from exc
    if not minimum <= result <= maximum:
        raise LDAPAccessError("Parámetro LDAP7_" + name + " fuera del límite permitido")
    return result


def _open_connection(context=CONTEXT):
    """Conexión LDAP de servicio para leer los grupos de VPN."""
    server_url = (_env("SERVER") or os.getenv("LDAP_SERVER") or "").strip()
    base = (os.getenv("LDAP_BASE_DN") or "").strip()
    service_user = (os.getenv("LDAP_SERVICE_USER") or "").strip()
    service_password = os.getenv("LDAP_SERVICE_PASSWORD") or ""
    if not all((server_url, base, service_user, service_password)):
        raise LDAPAccessError("Faltan variables LDAP de servicio en el backend")

    parsed = urlparse(server_url if "://" in server_url else "ldap://" + server_url)
    if parsed.scheme not in ("ldap", "ldaps") or not parsed.hostname:
        raise LDAPAccessError("LDAP7_SERVER no contiene una dirección LDAP válida")

    mode = _env("MODE", "starttls_verified").strip().lower()
    if mode not in ("starttls_verified", "starttls_unverified", "ldaps_verified"):
        raise LDAPAccessError("LDAP7_MODE debe ser starttls_verified, starttls_unverified o ldaps_verified")

    if mode == "ldaps_verified" and parsed.scheme != "ldaps":
        raise LDAPAccessError("ldaps_verified requiere LDAP7_SERVER=ldaps://...")
    if mode != "ldaps_verified" and parsed.scheme != "ldap":
        raise LDAPAccessError("STARTTLS requiere LDAP7_SERVER=ldap://...")

    ca_path = (_env("CA_CERT") or os.getenv("LDAP_CA_CERT") or "").strip()
    if mode == "starttls_unverified":
        # Conserva el cifrado, pero desactiva autenticación del servidor:
        # una excepción limitada y temporal, nunca el modo por defecto.
        if not _enabled(_env("ALLOW_UNVERIFIED_TLS")):
            raise LDAPAccessError("STARTTLS sin CA requiere habilitación explícita de seguridad")
        tls = Tls(validate=ssl.CERT_NONE)
        logger.warning("%s usa STARTTLS SIN verificar la identidad del servidor LDAP", context)
    else:
        if ca_path and not Path(ca_path).is_file():
            raise LDAPAccessError("No se encuentra el archivo CA corporativo LDAP (LDAP7_CA_CERT)")
        tls = Tls(validate=ssl.CERT_REQUIRED, ca_certs_file=ca_path or None)

    server = Server(
        parsed.hostname,
        port=parsed.port or (636 if parsed.scheme == "ldaps" else 389),
        use_ssl=(mode == "ldaps_verified"),
        tls=tls,
        get_info=NONE,
        connect_timeout=_integer("CONNECT_TIMEOUT", 8, 2, 60),
    )
    conn = Connection(
        server,
        user=service_user,
        password=service_password,
        authentication=SIMPLE,
        receive_timeout=_integer("READ_TIMEOUT", 30, 5, 120),
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


def _direct_users(conn, base, group_dn, page_size, max_users, with_manager=False):
    """Busca usuarios directamente miembros del grupo mediante páginas AD.

    No equivale a grupos anidados ni a sesiones VPN conectadas.
    with_manager=True agrega el DN del jefe ("manager" de AD) en "manager_dn" y el cargo ("title") en "cargo".
    """
    search_filter = (
        "(&(objectCategory=person)(objectClass=user)(memberOf="
        + escape_filter_chars(group_dn) + "))"
    )
    accounts = {}
    attributes = ["sAMAccountName", "displayName", "userAccountControl"] + (["manager", "title"] if with_manager else [])
    rows = conn.extend.standard.paged_search(
        search_base=base,
        search_filter=search_filter,
        search_scope=SUBTREE,
        attributes=attributes,
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
        if with_manager:
            accounts[username]["manager_dn"] = str(_first(attrs.get("manager")) or "").strip() or None
            accounts[username]["cargo"] = str(_first(attrs.get("title")) or "").strip()[:200]
        if len(accounts) > max_users:
            raise LDAPAccessError("El grupo LDAP supera el máximo configurado")
    return accounts


# El responsable de una VPN interna es el primer GERENTE de la cadena de jefes
# de AD (atributo "manager"), no el jefe directo (que puede ser jefe o coordinador).
MANAGER_TITLE_PREFIX = "gerente"
MAX_MANAGER_LEVELS = 10

# Excepción: las VPN de las cuentas con cargo "Director..." no las valida un gerente (sería un
# subordinado) sino el aprobador de directores (David Álava, usuario de red "dalava"), también la
# suya propia. Se cambia con LDAP7_APROBADOR_DIRECTORES en el .env. Aplica a directores nuevos y
# existentes en cada carga desde LDAP.
DIRECTOR_TITLE_PREFIX = "director"
DEFAULT_DIRECTOR_APPROVER = "dalava"


def director_approver():
    """Usuario de red (sAMAccountName) que valida las VPN de los directores."""
    return (_env("APROBADOR_DIRECTORES") or DEFAULT_DIRECTOR_APPROVER).strip().lower()


def director_demo_users():
    """Usuarios SOX que ven la página del aprobador de directores en SOLO LECTURA (demostración
    para los administradores). .env: LDAP7_DEMO_DIRECTORES=amiranda (varios separados por coma)."""
    return {u.strip().lower() for u in (_env("DEMO_DIRECTORES") or "").split(",") if u.strip()}


def is_director(title):
    return _plain_title(title).startswith(DIRECTOR_TITLE_PREFIX)


def _plain_title(value):
    import unicodedata
    value = unicodedata.normalize("NFKD", str(value or "")).strip().lower()
    return "".join(c for c in value if not unicodedata.combining(c))


def _person(conn, dn, people):
    """Datos de AD de un DN (con caché): usuario, nombre, correo, cargo y DN de su jefe."""
    if dn in people:
        return people[dn]
    person = None
    try:
        conn.search(search_base=dn, search_scope=BASE, search_filter="(objectClass=user)",
                    attributes=["sAMAccountName", "displayName", "mail", "title", "department", "manager"], size_limit=1)
        if len(conn.entries) == 1:
            attrs = conn.entries[0].entry_attributes_as_dict
            username = str(_first(attrs.get("sAMAccountName")) or "").strip().lower()
            if username:
                person = {"usuario": username[:100],
                          "nombre": (str(_first(attrs.get("displayName")) or "").strip() or username)[:200],
                          "correo": (str(_first(attrs.get("mail")) or "").strip() or None),
                          "cargo": str(_first(attrs.get("title")) or "").strip(),
                          "departamento": str(_first(attrs.get("department")) or "").strip(),
                          "manager_dn": str(_first(attrs.get("manager")) or "").strip() or None}
    except Exception:
        person = None
    people[dn] = person
    return person


def _find_manager(conn, dn, people, found):
    """Sube por la cadena de jefes desde dn hasta el primer cargo que empieza con "Gerente".

    Devuelve {usuario, nombre, correo, cargo, departamento} o None si no hay gerente en la cadena.
    """
    if dn in found:
        return found[dn]
    path, current, result = [], dn, None
    while current and len(path) < MAX_MANAGER_LEVELS and current not in path:
        if current in found:
            result = found[current]
            break
        path.append(current)
        person = _person(conn, current, people)
        if not person:
            break
        if _plain_title(person["cargo"]).startswith(MANAGER_TITLE_PREFIX):
            result = {k: person[k] for k in ("usuario", "nombre", "correo", "cargo", "departamento")}
            break
        current = person["manager_dn"]
    for step in path:
        found[step] = result
    return result


def read_internal_access_with_managers():
    """VPN internas: membresías RDP/APLICACIONES con el GERENTE de cada cuenta.

    Devuelve una fila por (cuenta, grupo): usuario, nombre, activo, tipo_acceso y
    gerente {usuario, nombre, correo, cargo}: el primer jefe de la cadena de AD cuyo cargo
    empieza con "Gerente"; None si la cuenta no tiene jefe o no hay gerente en la cadena.
    Si el cargo de la cuenta empieza con "Director", el gerente es el aprobador de directores
    (director_approver) y la fila lleva director=True.
    """
    page_size = _integer("PAGE_SIZE", 200, 20, 1000)
    max_users = _integer("MAX_USERS_PER_GROUP", 5000, 100, 20000)
    conn = None
    try:
        conn, base = _open_connection()
        rows, people, found = [], {}, {}
        approver = _approver(conn, base)
        for access_type, group_name in LDAP_GROUPS.items():
            dn = _group_dn(conn, base, group_name)
            group_users = _direct_users(conn, base, dn, page_size, max_users, with_manager=True)
            if not group_users:
                raise LDAPAccessError("El grupo LDAP " + access_type + " no devolvió cuentas")
            for info in group_users.values():
                manager_dn = info.pop("manager_dn", None)
                director = bool(approver) and is_director(info.get("cargo"))
                if director:
                    manager = approver
                else:
                    manager = _find_manager(conn, manager_dn, people, found) if manager_dn else None
                rows.append({**info, "tipo_acceso": access_type, "gerente": manager, "director": director})
        managers = {m["usuario"] for m in found.values() if m}
        if any(r["director"] for r in rows):
            managers.add(approver["usuario"])
        return {"filas": rows, "gerentes": len(managers),
                "consulta_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    except LDAPAccessError:
        raise
    except Exception as exc:
        logger.warning("Control 7 internas: lectura LDAP fallida (%s)", type(exc).__name__)
        raise LDAPAccessError("No se completó la consulta LDAP de VPN internas") from exc
    finally:
        if conn is not None:
            try:
                conn.unbind()
            except Exception:
                pass


def _approver(conn, base):
    """Datos de AD del aprobador de directores; None (y aviso en el log) si no está en AD."""
    username = director_approver()
    conn.search(search_base=base, search_scope=SUBTREE,
                search_filter="(&(objectCategory=person)(objectClass=user)(sAMAccountName="
                              + escape_filter_chars(username) + "))",
                attributes=["sAMAccountName", "displayName", "mail", "title", "department"], size_limit=2)
    if len(conn.entries) != 1:
        logger.warning("Control 7 internas: el aprobador de directores %s no está en AD; "
                       "las VPN de directores siguen la cadena de jefes", username)
        return None
    attrs = conn.entries[0].entry_attributes_as_dict
    return {"usuario": str(_first(attrs.get("sAMAccountName")) or username).strip().lower()[:100],
            "nombre": (str(_first(attrs.get("displayName")) or "").strip() or username)[:200],
            "correo": str(_first(attrs.get("mail")) or "").strip() or None,
            "cargo": str(_first(attrs.get("title")) or "").strip(),
            "departamento": str(_first(attrs.get("department")) or "").strip()}


def read_internal_access():
    """Cuentas únicas de los dos grupos de VPN con sus fuentes (sin gerente).

    Hoy también la usan los cortes LDAP del Control 6, que está pendiente de reestructurar.
    """
    page_size = _integer("PAGE_SIZE", 200, 20, 1000)
    max_users = _integer("MAX_USERS_PER_GROUP", 5000, 100, 20000)
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
        logger.warning("Control 7 internas: lectura LDAP de membresías fallida (%s)", type(exc).__name__)
        raise LDAPAccessError("No se completó la consulta LDAP de VPN internas") from exc
    finally:
        if conn is not None:
            try:
                conn.unbind()
            except Exception:
                pass


def find_person(username):
    """Datos de AD de un usuario de red (para asignar un gerente a mano): None si no existe."""
    conn = None
    try:
        conn, base = _open_connection()
        conn.search(search_base=base, search_scope=SUBTREE,
                    search_filter="(&(objectCategory=person)(objectClass=user)(sAMAccountName="
                                  + escape_filter_chars(username) + "))",
                    attributes=["sAMAccountName", "displayName", "mail", "title", "department"], size_limit=2)
        if len(conn.entries) != 1:
            return None
        attrs = conn.entries[0].entry_attributes_as_dict
        return {"usuario": str(_first(attrs.get("sAMAccountName")) or username).strip().lower()[:100],
                "nombre": (str(_first(attrs.get("displayName")) or "").strip() or username)[:200],
                "correo": str(_first(attrs.get("mail")) or "").strip() or None,
                "cargo": str(_first(attrs.get("title")) or "").strip(),
                "departamento": str(_first(attrs.get("department")) or "").strip()}
    except LDAPAccessError:
        raise
    except Exception as exc:
        logger.warning("Control 7 internas: búsqueda LDAP de gerente fallida (%s)", type(exc).__name__)
        raise LDAPAccessError("No se pudo consultar el usuario en LDAP") from exc
    finally:
        if conn is not None:
            try:
                conn.unbind()
            except Exception:
                pass


SEARCH_LIMIT = 20


def search_people(query, limit=SEARCH_LIMIT):
    """Busca personas ACTIVAS en AD por cuenta (sAMAccountName) o por nombre (displayName).

    "Angel Napa" encuentra "COM Angel Napa": cada palabra debe estar en el nombre.
    Devuelve hasta `limit` personas {usuario, nombre, correo, cargo, departamento}.
    """
    words = [w for w in str(query or "").strip().split() if w][:5]
    if not words or len(" ".join(words)) < 3:
        return []
    by_name = "".join("(displayName=*" + escape_filter_chars(w) + "*)" for w in words)
    by_account = "(sAMAccountName=" + escape_filter_chars(words[0]) + "*)" if len(words) == 1 else ""
    search_filter = ("(&(objectCategory=person)(objectClass=user)"
                     "(!(userAccountControl:1.2.840.113556.1.4.803:=2))"
                     "(|" + by_account + "(&" + by_name + ")))")
    conn = None
    found = []
    try:
        conn, base = _open_connection()
        rows = conn.extend.standard.paged_search(
            search_base=base, search_filter=search_filter, search_scope=SUBTREE,
            attributes=["sAMAccountName", "displayName", "mail", "title", "department"],
            paged_size=limit + 5, generator=True)
        for item in rows:
            if item.get("type") != "searchResEntry":
                continue
            attrs = item.get("attributes") or {}
            username = str(_first(attrs.get("sAMAccountName")) or "").strip().lower()
            if not username:
                continue
            found.append({"usuario": username[:100],
                          "nombre": (str(_first(attrs.get("displayName")) or "").strip() or username)[:200],
                          "correo": str(_first(attrs.get("mail")) or "").strip() or None,
                          "cargo": str(_first(attrs.get("title")) or "").strip(),
                          "departamento": str(_first(attrs.get("department")) or "").strip()})
            if len(found) >= limit:
                break
    except LDAPAccessError:
        raise
    except Exception as exc:
        logger.warning("Control 7 internas: búsqueda LDAP de personas fallida (%s)", type(exc).__name__)
        raise LDAPAccessError("No se pudo buscar en LDAP") from exc
    finally:
        if conn is not None:
            try:
                conn.unbind()
            except Exception:
                pass
    plain = " ".join(words).lower()
    # Primero la cuenta exacta, luego los que empiezan igual, luego por nombre.
    return sorted(found, key=lambda p: (p["usuario"] != plain, not p["usuario"].startswith(plain), p["nombre"].lower()))
