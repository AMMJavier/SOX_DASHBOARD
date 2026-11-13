import sys
import os
import time
from datetime import datetime
from pathlib import Path

# Permite ejecutarlo como script suelto: agrega backend/ al path.
BASE_DIR = str(Path(__file__).resolve().parents[3])
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)


from database.oracle_connection import OracleConnection
from auth.ldap_service import get_user_email_by_cn


def limpiar_nombre(nombre):

    if not nombre:
        return None

    return (
        nombre
        .replace("\xa0", " ")
        .strip()
    )


def obtener_gerentes():

    oracle = OracleConnection()

    try:

        conn = oracle.connect()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                MIN(GERENTE) GERENTE

            FROM CHECKPOINT_TRANSFORM

            WHERE GERENTE IS NOT NULL

            GROUP BY
                UPPER(
                    NLSSORT(
                        TRIM(
                            REPLACE(GERENTE, CHR(160), ' ')
                        ),
                        'NLS_SORT=BINARY_AI'
                    )
                )

            ORDER BY GERENTE
        """)

        return [
            row[0]
            for row in cursor.fetchall()
        ]

    finally:
        oracle.close()



def guardar_contacto(datos):

    oracle = OracleConnection()

    try:

        conn = oracle.connect()
        cursor = conn.cursor()


        cursor.execute("""
            MERGE INTO AUTOM.SOX_GERENTES_CONTACTO destino

            USING (
                SELECT
                    :nombre nombre,
                    :correo correo,
                    :ldap_cn ldap_cn
                FROM dual
            ) origen

            ON (
                destino.LDAP_CN = origen.ldap_cn
            )

            WHEN MATCHED THEN

                UPDATE SET
                    destino.NOMBRE_COMPLETO = origen.nombre,
                    destino.CORREO = origen.correo,
                    destino.ACTIVO = 1,
                    destino.FECHA_ACTUALIZACION =
                        CURRENT_TIMESTAMP


            WHEN NOT MATCHED THEN

                INSERT
                (
                    NOMBRE_COMPLETO,
                    CORREO,
                    LDAP_CN,
                    ACTIVO,
                    FECHA_SYNC,
                    FECHA_ACTUALIZACION
                )

                VALUES
                (
                    origen.nombre,
                    origen.correo,
                    origen.ldap_cn,
                    1,
                    CURRENT_TIMESTAMP,
                    CURRENT_TIMESTAMP
                )
        """,
        {
            "nombre": datos["nombre"],
            "correo": datos["correo"],
            "ldap_cn": datos["username"]
        })


        conn.commit()


    finally:
        oracle.close()



def log(mensaje):
    """Traza en consola (visible en uvicorn.log con nohup gracias a flush)."""
    print(f"[SOX CONTACTOS {datetime.now():%Y-%m-%d %H:%M:%S}] {mensaje}", flush=True)


def sincronizar():

    inicio = time.monotonic()
    log("SINCRONIZACION INICIO | gerentes de CHECKPOINT_TRANSFORM -> LDAP -> SOX_GERENTES_CONTACTO")

    gerentes = obtener_gerentes()
    log(f"Gerentes distintos con VPN en CHECKPOINT_TRANSFORM: {len(gerentes)}")

    encontrados_ldap = 0
    guardados_bd = 0
    no_encontrados = []


    for indice, gerente in enumerate(gerentes, start=1):

        nombre = limpiar_nombre(gerente)
        t0 = time.monotonic()

        resultado = get_user_email_by_cn(nombre)


        if resultado and resultado["correo"]:

            encontrados_ldap += 1

            try:
                guardar_contacto(resultado)
                guardados_bd += 1
                log(f"[{indice}/{len(gerentes)}] OK      {nombre!r} -> correo={resultado['correo']} "
                    f"ldap={resultado.get('username')} ({time.monotonic() - t0:.2f}s)")
            except Exception as exc:
                log(f"[{indice}/{len(gerentes)}] ERROR BD {nombre!r} -> {resultado['correo']}: {type(exc).__name__}: {exc}")
                raise


        else:

            no_encontrados.append(nombre)
            motivo = "encontrado en LDAP pero sin atributo mail" if resultado else "no encontrado en LDAP (o más de un resultado)"
            log(f"[{indice}/{len(gerentes)}] SIN CORREO {nombre!r}: {motivo} ({time.monotonic() - t0:.2f}s)")


    log(f"SINCRONIZACION FIN | total={len(gerentes)} encontrados_ldap={encontrados_ldap} "
        f"guardados_bd={guardados_bd} sin_correo={len(no_encontrados)} | {time.monotonic() - inicio:.2f}s")
    if no_encontrados:
        log("Sin correo (quedan 'Sin contacto' en el panel): " + "; ".join(no_encontrados))

    return {
        "total_gerentes": len(gerentes),
        "encontrados_ldap": encontrados_ldap,
        "guardados_bd": guardados_bd,
        "no_encontrados": no_encontrados
    }



if __name__ == "__main__":

    resultado = sincronizar()

    print(resultado)