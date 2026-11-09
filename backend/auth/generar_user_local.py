"""Crea un hash bcrypt para cuentas locales sin persistir contraseñas.

Uso: desde backend_integrado, python -m auth.generar_user_local
"""
import getpass
from auth.security import get_password_hash

if __name__ == "__main__":
    password = getpass.getpass("Contraseña local: ")
    confirm = getpass.getpass("Confirmar contraseña: ")
    if password != confirm:
        raise SystemExit("Las contraseñas no coinciden")
    print(get_password_hash(password))
