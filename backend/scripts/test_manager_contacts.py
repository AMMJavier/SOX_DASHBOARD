
import sys
import os

# Permitir importar módulos del backend
sys.path.append(
    os.path.dirname(
        os.path.dirname(__file__)
    )
)

from database.oracle_connection import OracleConnection
from auth.ldap_service import get_user_email_by_cn


def limpiar_nombre(nombre):
    """
    Limpieza básica para búsqueda LDAP
    """
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

        connection = oracle.connect()
        cursor = connection.cursor()


        cursor.execute("""
            SELECT
                MIN(GERENTE) GERENTE

            FROM AUTOM.CHECKPOINT_TRANSFORM

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



def main():

    gerentes = obtener_gerentes()


    print("=" * 50)
    print(
        f"Gerentes encontrados: {len(gerentes)}"
    )
    print("=" * 50)


    encontrados = 0
    no_encontrados = 0


    for gerente in gerentes:

        nombre = limpiar_nombre(gerente)

        print("\n--------------------------------")
        print(f"Gerente: {nombre}")


        resultado = get_user_email_by_cn(nombre)


        if resultado:

            encontrados += 1

            print(
                f"CN: {resultado['nombre']}"
            )

            print(
                f"Correo: {resultado['correo']}"
            )

            print(
                f"Usuario LDAP: {resultado['username']}"
            )

        else:

            no_encontrados += 1

            print(
                "NO ENCONTRADO EN LDAP"
            )


    print("\n==============================")
    print(
        f"Encontrados: {encontrados}"
    )

    print(
        f"No encontrados: {no_encontrados}"
    )
    print("==============================")



if __name__ == "__main__":
    main()