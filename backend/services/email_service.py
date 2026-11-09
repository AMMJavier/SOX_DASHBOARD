import sys
import os


BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

sys.path.append(BASE_DIR)


from database.oracle_connection import OracleConnection

TEST_MODE = True

TEST_EMAIL = os.getenv("SOX_TEST_EMAIL", "")


def obtener_destinatarios():

    oracle = OracleConnection()

    conn = None

    try:

        conn = oracle.connect()

        cursor = conn.cursor()


        cursor.execute("""
            SELECT
                NOMBRE_COMPLETO,
                CORREO
            FROM AUTOM.SOX_GERENTES_CONTACTO
            WHERE ACTIVO = 1
              AND CORREO IS NOT NULL
            ORDER BY NOMBRE_COMPLETO
        """)


        destinatarios = []


        for row in cursor.fetchall():

            destinatarios.append(
                {
                    "nombre": row[0],
                    "correo": row[1]
                }
            )


        return destinatarios


    finally:

        if conn:
            conn.close()



def enviar_correo(destinatario):

    """
    Aquí irá la integración real:
    SMTP o API corporativa de notificaciones
    """

    print(
        f"Enviando correo a: {destinatario['correo']}"
    )


    # MOCK TEMPORAL
    # Aquí después reemplazaremos
    # con el consumo real del servicio


    return {
        "correo": destinatario["correo"],
        "estado": "ENVIADO"
    }



def send_campaign_notification():

    if TEST_MODE:
        destinatarios = [
            {
            "nombre": "Prueba SOX",
            "correo": TEST_EMAIL
            }
        ]
    else:

    
        destinatarios = obtener_destinatarios()

    print("==============================")
    print("MODO PRUEBA:", TEST_MODE)
    print("DESTINATARIOS:")
    print(destinatarios)
    print("==============================")
    
    enviados = []
    errores = []


    print(
        f"Destinatarios encontrados: {len(destinatarios)}"
    )


    for destinatario in destinatarios:


        try:

            resultado = enviar_correo(
                destinatario
            )


            enviados.append(resultado)


        except Exception as e:


            errores.append(
                {
                    "correo": destinatario["correo"],
                    "error": str(e)
                }
            )


    return {

        "total_destinatarios":
            len(destinatarios),

        "enviados":
            len(enviados),

        "errores":
            errores,

        "modo_prueba":
            TEST_MODE,

        "detalle":
            enviados
    }