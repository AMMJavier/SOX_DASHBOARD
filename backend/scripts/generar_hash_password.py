"""Genera el hash bcrypt de una contraseña local, sin guardarla en ningún lado.

Uso (desde la carpeta backend):
    python scripts/generar_hash_password.py
"""
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from auth.security import get_password_hash  # noqa: E402

if __name__ == "__main__":
    password = getpass.getpass("Contraseña local: ")
    confirm = getpass.getpass("Confirmar contraseña: ")
    if password != confirm:
        raise SystemExit("Las contraseñas no coinciden")
    print(get_password_hash(password))
