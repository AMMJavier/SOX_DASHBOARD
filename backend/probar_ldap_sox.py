
import getpass
from auth.ldap_service import authenticate_ldap

username = input("Usuario LDAP: ").strip()
password = getpass.getpass("Contraseña corporativa: ")

try:
    resultado = authenticate_ldap(username, password)
    print(
        "Autenticación LDAP:",
        "CORRECTA" if resultado else "RECHAZADA"
    )
except Exception as error:
    print("Error:", type(error).__name__)
