"""LDAP/Active Directory opcional: configuración exigida sólo al autenticar.

Por seguridad, SIMPLE bind sólo usa TLS, salvo autorización explícita de legado.
"""
import logging
import os
import ssl
from urllib.parse import urlparse
from dotenv import load_dotenv
from ldap3 import Server, Connection, SIMPLE, NONE, Tls
from ldap3.utils.conv import escape_filter_chars

load_dotenv()
logger = logging.getLogger(__name__)

def _flag(name, default="false"):
    return os.getenv(name, default).strip().lower() in {"1", "yes", "true", "on"}

def _ldap_options():
    raw = os.getenv("LDAP_SERVER", "")
    base = os.getenv("LDAP_BASE_DN", "")
    bind_user = os.getenv("LDAP_SERVICE_USER", "")
    bind_password = os.getenv("LDAP_SERVICE_PASSWORD", "")
    if not all((raw, base, bind_user, bind_password)):
        logger.warning("Faltan variables LDAP_SERVER/LDAP_BASE_DN/LDAP_SERVICE_USER/LDAP_SERVICE_PASSWORD")
        return None
    parsed = urlparse(raw if '://' in raw else 'ldaps://' + raw)
    is_ssl = parsed.scheme.lower() == "ldaps"
    use_starttls = _flag("LDAP_STARTTLS")
    if not is_ssl and not use_starttls and not _flag("LDAP_ALLOW_INSECURE_BIND"):
        logger.warning("Se bloqueó LDAP SIMPLE sin TLS; habilitar LDAPS, STARTTLS o excepción explícita")
        return None
    if parsed.scheme.lower() not in ("ldap", "ldaps") or not parsed.hostname:
        logger.warning("LDAP_SERVER no tiene un formato de URL válido")
        return None
    tls = Tls(validate=ssl.CERT_REQUIRED) if is_ssl or use_starttls else None
    server = Server(parsed.hostname, port=parsed.port or (636 if is_ssl else 389),
                    use_ssl=is_ssl, tls=tls, connect_timeout=5, get_info=NONE)
    return server, base, bind_user, bind_password, use_starttls

def _bind(server, user, password, use_starttls):
    conn = Connection(server, user=user, password=password, authentication=SIMPLE, receive_timeout=5)
    try:
        if use_starttls:
            conn.open()
            if not conn.start_tls():
                conn.unbind()
                return None
        if not conn.bind():
            conn.unbind()
            return None
        return conn
    except Exception:
        try: conn.unbind()
        except Exception: pass
        raise

def authenticate_ldap(username: str, password: str) -> bool:
    if not username or not password:
        return False
    options = _ldap_options()
    if options is None:
        return False
    server, base, service_user, service_password, starttls = options
    try:
        conn = _bind(server, service_user, service_password, starttls)
        if not conn:
            return False
        try:
            filt = f"(sAMAccountName={escape_filter_chars(username)})"
            conn.search(search_base=base, search_filter=filt, attributes=["distinguishedName"], size_limit=2)
            if len(conn.entries) != 1:
                return False
            user_dn = conn.entries[0].entry_dn
        finally:
            conn.unbind()
        usuario_dominio = f"porta\\{username}" 
        user_conn = _bind(server, user_dn, password, starttls)
        if not user_conn:
            return False
        user_conn.unbind()
        return True
    except Exception:
        logger.exception("No se pudo validar la autenticación LDAP (sin credenciales en logs)")
        return False

def get_user_email_by_cn(nombre):
    if not nombre:
        return None
    options = _ldap_options()
    if options is None:
        return None
    server, base, service_user, service_password, starttls = options
    try:
        conn = _bind(server, service_user, service_password, starttls)
        if not conn:
            return None
        try:
            conn.search(search_base=base, search_filter=f"(cn={escape_filter_chars(nombre)})",
                        attributes=["cn", "mail", "sAMAccountName"], size_limit=2)
            if len(conn.entries) != 1:
                return None
            e = conn.entries[0]
            return {"nombre": str(e.cn), "correo": str(e.mail) if e.mail else None,
                    "username": str(e.sAMAccountName) if e.sAMAccountName else None}
        finally:
            conn.unbind()
    except Exception:
        logger.exception("No se pudo consultar correo en LDAP")
        return None
