"""Busca en LDAP (vía la API de la plataforma) a personas por nombre y las crea como usuarios LDAP.

Pensado para el equipo TIC NET Seguridades: rol "assets_viewer" (viewer de Assets).
Para cada nombre usa GET /sox/campaign/internas/gerentes/buscar-ad (personas ACTIVAS de AD) y
solo crea el usuario si hay UNA coincidencia clara (si hay varias, prefiere la que empieza por "TIC").

Uso (en el servidor, desde la carpeta backend):
    .venv/bin/python scripts/crear_usuarios_assets_viewer.py            # busca y muestra, NO crea
    .venv/bin/python scripts/crear_usuarios_assets_viewer.py --crear    # busca y crea los usuarios
Variables opcionales: SOX_API (por defecto http://127.0.0.1:8000).
"""
import getpass
import json
import os
import sys
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

API = os.getenv("SOX_API", "http://127.0.0.1:8000").rstrip("/")
ROL = "assets_viewer"
PERSONAS = ["Gary Ortiz", "Angel Ochoa", "Luis Arevalo", "Nadia Carriel", "Patricio Gordillo", "Rommel Carrillo"]


def plain(value):
    return "".join(c for c in unicodedata.normalize("NFD", str(value or "")) if unicodedata.category(c) != "Mn").lower()


def call(method, path, token=None, body=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(API + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, json.loads(resp.read() or b"null")
    except urllib.error.HTTPError as exc:
        try:
            detail = json.loads(exc.read() or b"null")
        except ValueError:
            detail = None
        return exc.code, detail


def search(token, name):
    """Busca por apellido (sin tildes, LDAP no siempre las iguala) y filtra por el nombre completo."""
    first, last = name.split()[0], name.split()[-1]
    candidates = {}
    for query in (name, last):
        status, rows = call("GET", "/sox/campaign/internas/gerentes/buscar-ad?q=" + urllib.parse.quote(query), token)
        if status != 200:
            raise RuntimeError(f"búsqueda LDAP '{query}' respondió {status}: {rows}")
        for row in rows or []:
            if plain(first) in plain(row["nombre"]) and plain(last) in plain(row["nombre"]):
                candidates[row["usuario"]] = row
    found = list(candidates.values())
    if len(found) > 1:  # varias personas: quedarse con las del área TIC
        tic = [r for r in found if plain(r["nombre"]).startswith("tic ")]
        found = tic or found
    return found


def main():
    create = "--crear" in sys.argv
    admin = input("Usuario administrador: ").strip()
    password = getpass.getpass("Contraseña: ")
    status, data = call("POST", "/auth/login", body={"username": admin, "password": password})
    password = None
    if status != 200 or not (data or {}).get("access_token"):
        sys.exit(f"No se pudo iniciar sesión ({status}): {data}")
    token = data["access_token"]

    created = existing = skipped = 0
    for name in PERSONAS:
        found = search(token, name)
        if len(found) != 1:
            skipped += 1
            detail = "; ".join(f"{r['usuario']} = {r['nombre']}" for r in found) or "sin coincidencias"
            print(f"REVISAR   {name}: {len(found)} coincidencias ({detail})")
            continue
        person = found[0]
        info = f"{person['usuario']:<15} {person['nombre']} | {person.get('correo') or '-'} | {person.get('cargo') or '-'}"
        if not create:
            print(f"ENCONTRADO {info}")
            continue
        status, data = call("POST", "/usuarios", token,
                            {"username": person["usuario"], "auth_provider": "ldap", "rol": ROL})
        if status == 201:
            created += 1
            print(f"CREADO    {info}")
        elif status == 409:
            existing += 1
            print(f"YA EXISTE {info}")
        else:
            skipped += 1
            print(f"ERROR {status} {info}: {data}")
    if create:
        print(f"Creados: {created} | Ya existían: {existing} | Sin crear: {skipped} | Rol: {ROL}")
    else:
        print("Solo búsqueda. Para crearlos: añade --crear")


if __name__ == "__main__":
    main()
