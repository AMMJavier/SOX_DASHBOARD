from datetime import datetime
from checkpoint.checkpoint_client import CheckPointClient
import json

# ==================================
# Configuración Check Point
# ==================================

def _checkpoint_client():
    import os
    import json
    from pathlib import Path
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    cfg_path = Path(__file__).resolve().parents[1] / "config" / "config.json"
    legacy = {}
    if cfg_path.exists():
        with cfg_path.open(encoding="utf8") as fh:
            legacy = json.load(fh).get("checkpoint", {})
    url = os.getenv("CHECKPOINT_URL") or legacy.get("url")
    user = os.getenv("CHECKPOINT_USERNAME") or legacy.get("username")
    password = os.getenv("CHECKPOINT_PASSWORD") or legacy.get("password")
    if not all([url, user, password]):
        raise RuntimeError("Configurar CHECKPOINT_URL, CHECKPOINT_USERNAME y CHECKPOINT_PASSWORD")
    return CheckPointClient(url=url, username=user, password=password)



# ==================================
# Función paginación Check Point
# ==================================

def extract_all_vpn_objects(client):

    all_objects = []

    limit = 50
    offset = 0

    while True:

        print(
            f"Consultando registros {offset} - {offset + limit}"
        )

        response = client.call_api(
            "show-users",
            {
                "details-level": "full",
                "limit": limit,
                "offset": offset
            }
        )

        objects = response.get(
            "objects",
            []
        )

        all_objects.extend(objects)

        total = response.get(
            "total",
            0
        )

        print(
            f"Recibidos: {len(objects)} | "
            f"Acumulados: {len(all_objects)} de {total}"
        )

        if len(all_objects) >= total:
            break

        offset += limit


    return all_objects



# ==================================
# Función utilizada por sync_service
# ==================================

def extract_vpn_data():

    print("Iniciando extracción Check Point")

    client = _checkpoint_client()
    client.login()

    try:

        # Aquí entra la paginación
        usuarios = extract_all_vpn_objects(client)


        fecha_extraccion = datetime.now()

        registros = []


        for usuario in usuarios:

            registro = {

                "checkpoint_uid": usuario.get(
                    "uid",
                    ""
                ),

                "nombre_vpn": usuario.get(
                    "name",
                    """"""
                ),

                "comentario": usuario.get(
                    "comments",
                    ""
                ),

                "color": usuario.get(
                    "color",
                    ""
                ),

                "fecha_almacenado": fecha_extraccion
            }


            registros.append(registro)


        print(
            f"Registros preparados: {len(registros)}"
        )

        with open(
            "checkpoint/output/vpn_export.json",
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                registros,
                file,
                indent=4,
                default=str
            )

        return registros


    finally:

        client.logout()



# ==================================
# Prueba manual del extractor
# ==================================

if __name__ == "__main__":

    datos = extract_vpn_data()

    print(datos[:10])