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
 
def _name_variants(nombre):
    """Nombre completo y, si empieza con un prefijo de área (palabras cortas en MAYÚSCULAS
    como TIC, COM, FIN, SAC, "T H"), el nombre sin ese prefijo."""
    nombre = " ".join(str(nombre).replace("\xa0", " ").split())
    variantes = [nombre]
    partes = nombre.split(" ")
    i = 0
    while i < len(partes) - 2 and partes[i].isupper() and len(partes[i]) <= 4 and partes[i].isalpha():
        i += 1
    if 0 < i:
        variantes.append(" ".join(partes[i:]))
    return variantes


def get_user_email_by_cn(nombre):
    if not nombre:
        return None

    server = _server()
    base = os.getenv("LDAP_BASE_DN", "")
    svc_user = os.getenv("LDAP_SERVICE_USER", "")
    svc_pass = os.getenv("LDAP_SERVICE_PASSWORD", "")
    if server is None or not all((base, svc_user, svc_pass)):
        faltan = [n for n, v in (("LDAP_SERVER", server), ("LDAP_BASE_DN", base),
                                 ("LDAP_SERVICE_USER", svc_user), ("LDAP_SERVICE_PASSWORD", svc_pass)) if not v]
        print(f"[SOX LDAP] Búsqueda de {nombre!r} omitida: faltan en .env {faltan}", flush=True)
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
            # No se imprime la contraseña: solo el usuario de servicio y el resultado del bind.
            print(f"[SOX LDAP] Bind FALLIDO con la cuenta de servicio {svc_user!r}: {conn.result.get('description')}", flush=True)
            return None

        try:
            # 1ro el nombre tal cual; si no aparece, sin el prefijo del área de Check Point
            # ("TIC Paola Galecio" -> "Paola Galecio", "T H Oscar Salas" -> "Oscar Salas").
            for variante in _name_variants(nombre):
                conn.search(
                    search_base=base,
                    search_filter=f"(|(cn={escape_filter_chars(variante)})(displayName={escape_filter_chars(variante)}))",
                    attributes=["cn", "mail", "sAMAccountName"],
                    size_limit=2,
                )
                if len(conn.entries) == 1:
                    e = conn.entries[0]
                    if variante != nombre:
                        print(f"[SOX LDAP] {nombre!r} encontrado como {variante!r} (sin prefijo de área)", flush=True)
                    return {
                        "nombre": str(e.cn),
                        "correo": str(e.mail) if e.mail else None,
                        "username": str(e.sAMAccountName) if e.sAMAccountName else None,
                    }
                print(f"[SOX LDAP] cn/displayName={variante!r}: {len(conn.entries)} resultado(s) en {base!r} "
                      f"({'no existe con ese nombre' if not conn.entries else 'nombre ambiguo, más de una cuenta'})", flush=True)
                if len(conn.entries) > 1:
                    return None  # Ambiguo: no se adivina la cuenta.
            return None

        finally:
            conn.unbind()

    except Exception as exc:
        print(f"[SOX LDAP] Error consultando cn={nombre!r}: {type(exc).__name__}: {exc}", flush=True)
        logger.exception("No se pudo consultar correo en LDAP")
        return None
 
