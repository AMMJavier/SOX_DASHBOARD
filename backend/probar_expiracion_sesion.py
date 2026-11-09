
import getpass
import json
import base64
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone

from oracle_database import get_oracle_db
from models import SoxSesion

BASE_URL = "http://127.0.0.1:8000"


def request_api(path, method="GET", token=None, data=None):
    headers = {"Content-Type": "application/json"}

    if token:
        headers["Authorization"] = f"Bearer {token}"

    body = json.dumps(data).encode("utf-8") if data is not None else None

    request = urllib.request.Request(
        BASE_URL + path,
        data=body,
        headers=headers,
        method=method,
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
    data={"username": username, "password": password},
)

if status != 200 or not result or not result.get("access_token"):
    print("Login fallido:", status)
    raise SystemExit(1)

token = result["access_token"]

# Extraer el identificador de la sesión creada en esta prueba.
payload_part = token.split(".")[1]
payload_part += "=" * (-len(payload_part) % 4)
payload = json.loads(base64.urlsafe_b64decode(payload_part))

session_id = payload.get("jti")
user_id = payload.get("id")

if not session_id or user_id is None:
    print("El JWT no contiene los identificadores necesarios.")
    raise SystemExit(1)

print("1. Login:", status)

status, _ = request_api("/auth/me", token=token)
print("2. Sesión antes del vencimiento:", status)

if status != 200:
    print("La sesión no está activa. Prueba interrumpida.")
    raise SystemExit(1)

# Modificar únicamente la sesión creada por esta prueba.
db = next(get_oracle_db())

try:
    session = (
        db.query(SoxSesion)
        .filter(
            SoxSesion.session_id == session_id,
            SoxSesion.usuario_id == int(user_id),
            SoxSesion.revocado == 0,
        )
        .first()
    )

    if session is None:
        print("No se encontró la sesión de prueba en Oracle.")
        raise SystemExit(1)

    session.expira_en = (
        datetime.now(timezone.utc).replace(tzinfo=None)
        - timedelta(minutes=1)
    )

    db.commit()
    print("3. Sesión de prueba vencida en Oracle: CORRECTO")

except Exception:
    db.rollback()
    print("Error al modificar el vencimiento de la sesión.")
    raise
finally:
    db.close()

status, _ = request_api("/auth/me", token=token)
print("4. Acceso después del vencimiento:", status)

status_actividad, _ = request_api(
    "/auth/actividad",
    "POST",
    token=token,
)
print("5. Intento de renovar sesión vencida:", status_actividad)

if status == 401 and status_actividad == 401:
    print("RESULTADO: sesión vencida rechazada correctamente")
else:
    print("ATENCIÓN: revisar validación de vencimiento")
