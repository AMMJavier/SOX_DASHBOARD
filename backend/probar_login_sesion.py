
import getpass
import json
import base64
import urllib.request
import urllib.error

username = input("Usuario de prueba: ")
password = getpass.getpass("Contraseña: ")

url = "http://127.0.0.1:8000/auth/login"

data = json.dumps({
    "username": username,
    "password": password
}).encode("utf-8")

request = urllib.request.Request(
    url,
    data=data,
    headers={"Content-Type": "application/json"},
    method="POST"
)

try:
    with urllib.request.urlopen(request, timeout=30) as response:
        result = json.load(response)
        token = result.get("access_token", "")

        print("HTTP:", response.status)
        print("Login:", "CORRECTO" if token else "SIN TOKEN")
        print("Tipo de token:", result.get("token_type"))

        if token:
            payload_part = token.split(".")[1]
            payload_part += "=" * (-len(payload_part) % 4)

            payload = json.loads(
                base64.urlsafe_b64decode(payload_part)
            )

            print("JWT contiene jti:", bool(payload.get("jti")))
            print("JWT contiene exp:", bool(payload.get("exp")))

except urllib.error.HTTPError as error:
    print("HTTP:", error.code)
    print("Error de autenticación o servidor")

except Exception as error:
    print("Error de conexión:", type(error).__name__)
