import sys
import os
from datetime import datetime

BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

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



def sincronizar():

    gerentes = obtener_gerentes()

    encontrados_ldap = 0
    guardados_bd = 0
    no_encontrados = []


    for gerente in gerentes:

        nombre = limpiar_nombre(gerente)


        resultado = get_user_email_by_cn(nombre)


        if resultado and resultado["correo"]:

            encontrados_ldap += 1

            guardar_contacto(resultado)

            guardados_bd += 1


        else:

            no_encontrados.append(nombre)


    return {
        "total_gerentes": len(gerentes),
        "encontrados_ldap": encontrados_ldap,
        "guardados_bd": guardados_bd,
        "no_encontrados": no_encontrados
    }



if __name__ == "__main__":

    resultado = sincronizar()

    print(resultado)