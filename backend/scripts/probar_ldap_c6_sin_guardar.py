"""Prueba segura de lectura de grupos LDAP SIN modificar Oracle ni AD.

Ejecutar desde backend usando .venv/bin/python scripts/probar_ldap_c6_sin_guardar.py.
No imprime nombres de cuentas ni contraseñas.
"""
import sys
from pathlib import Path
from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))
load_dotenv(BACKEND_DIR / ".env")

from services.sox_ldap_access import LDAPAccessError, read_internal_access

try:
    report = read_internal_access()
except LDAPAccessError as exc:
    print("LDAP Control 6: NO DISPONIBLE")
    print("Detalle:", str(exc))
    raise SystemExit(1)

print("LDAP Control 6: CONSULTA CORRECTA, SIN GUARDAR")
print("RDP:", report["fuentes"]["RDP"])
print("Aplicaciones:", report["fuentes"]["APLICACIONES"])
print("Cuentas únicas:", report["total_cuentas_unicas"])
print("Fecha UTC:", report["consulta_utc"])
