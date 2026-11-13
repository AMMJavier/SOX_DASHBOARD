# backend/auth/ldap_service.py

import logging
import os
from urllib.parse import urlparse
from dotenv import load_dotenv
from ldap3 import Server, Connection, SIMPLE, NONE
from ldap3.utils.conv import escape_filter_chars
 
load_dotenv()
logger = logging.getLogger(__name__)
LDAP_PREFIX = os.getenv("LDAP_PREFIX", "PORTA\\")
 
def _server():

    raw = os.getenv("LDAP_SERVER", "").strip()
    if not raw:
        return None
    parsed = urlparse(raw if "://" in raw else "ldap://" + raw)
    return Server(
        parsed.hostname,
        port=parsed.port or 389,
        use_ssl=False,
        connect_timeout=5,
        get_info=NONE,
    )
 
 
def authenticate_ldap(username: str, password: str) -> bool:

    # Un bind con clave vacía se acepta como anónimo en muchos servidores
    if not username or not password:
        return False
    server = _server()
    if server is None:
        logger.warning("Falta LDAP_SERVER en el .env")
        return False
    try:

        conn = Connection(
            server,
            user=f"{LDAP_PREFIX}{username}",
            password=password,
            authentication=SIMPLE,
            receive_timeout=5,
        )

        ok = conn.bind()
        conn.unbind()
        return ok

    except Exception:
        logger.exception("No se pudo validar la autenticación LDAP")
        return False
 
def get_user_email_by_cn(nombre):
    if not nombre:
        return None

    server = _server()
    base = os.getenv("LDAP_BASE_DN", "")
    svc_user = os.getenv("LDAP_SERVICE_USER", "")
    svc_pass = os.getenv("LDAP_SERVICE_PASSWORD", "")
    if server is None or not all((base, svc_user, svc_pass)):
        return None
 
    try:
        conn = Connection(
            server,
            user=svc_user,
            password=svc_pass,
            authentication=SIMPLE,
            receive_timeout=5,
        )

        if not conn.bind():
            return None

        try:
            conn.search(
                search_base=base,
                search_filter=f"(cn={escape_filter_chars(nombre)})",
                attributes=["cn", "mail", "sAMAccountName"],
                size_limit=2,
            )

            if len(conn.entries) != 1:
                return None
            e = conn.entries[0]
            return {
                "nombre": str(e.cn),
                "correo": str(e.mail) if e.mail else None,
                "username": str(e.sAMAccountName) if e.sAMAccountName else None,
            }

        finally:
            conn.unbind()

    except Exception:
        logger.exception("No se pudo consultar correo en LDAP")
        return None
 
