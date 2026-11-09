
import getpass
import json
import urllib.request
import urllib.error

BASE_URL = "http://127.0.0.1:8000"

def request_api(path, method="GET", token=None, data=None):
    headers = {"Content-Type": "application/json"}

    if token:
        headers["Authorization"] = f"Bearer {token}"

    body = json.dumps(data).encode() if data is not None else None

    request = urllib.request.Request(
        BASE_URL + path,
        data=body,
        headers=headers,
        method=method
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        return error.code, None

username = input("Usuario de prueba: ")
password = getpass.getpass("Contraseña: ")

status, result = request_api(
    "/auth/login",
    "POST",
    data={"username": username, "password": password}
)

if status != 200 or not result:
    print("Login fallido:", status)
    raise SystemExit(1)

token = result["access_token"]

print("1. Login:", status)

status, _ = request_api("/auth/me", token=token)
print("2. Sesión activa (/auth/me):", status)

status, _ = request_api(
    "/auth/actividad",
    "POST",
    token=token
)
print("3. Renovación de actividad:", status)

status, _ = request_api(
    "/auth/logout",
    "POST",
    token=token
)
print("4. Cierre de sesión:", status)

status, _ = request_api("/auth/me", token=token)
print("5. Reutilización del JWT:", status)

if status == 401:
    print("RESULTADO: token anterior rechazado correctamente")
else:
    print("ATENCIÓN: el token anterior no fue rechazado")
