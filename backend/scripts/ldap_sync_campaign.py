import sys
import os

sys.path.append(
    os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )
)


import csv
import unicodedata
from dotenv import load_dotenv
load_dotenv()

from ldap3 import Server, Connection, SUBTREE
from database.oracle_connection import OracleConnection


# =====================================
# CONFIG LDAP
# =====================================

LDAP_SERVER = os.getenv("LDAP_SERVER")

LDAP_USER = os.getenv("LDAP_SERVICE_USER")
LDAP_PASSWORD = os.getenv("LDAP_SERVICE_PASSWORD")

BASE_DN = os.getenv("LDAP_BASE_DN")


# =====================================
# NORMALIZAR NOMBRES
# =====================================

def normalizar(texto):

    if not texto:
        return ""

    texto = texto.strip()

    texto = unicodedata.normalize(
        "NFD",
        texto
    )

    texto = "".join(
        c for c in texto
        if unicodedata.category(c) != "Mn"
    )

    return texto.upper()



# =====================================
# GERENTES DESDE ORACLE
# =====================================

def obtener_gerentes():

    oracle = OracleConnection()

    conn = oracle.connect()

    cursor = conn.cursor()


    query = """

    SELECT 
        MIN(
            TRIM(
                REPLACE(GERENTE, CHR(160), ' ')
            )
        ) GERENTE

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

    """


    cursor.execute(query)


    gerentes = [
        row[0]
        for row in cursor.fetchall()
    ]


    cursor.close()
    oracle.close()


    return gerentes



# =====================================
# CONSULTAR LDAP
# =====================================

def buscar_correo(gerente):


    server = Server(
        LDAP_SERVER
    )


    conn = Connection(
        server,
        user=LDAP_USER,
        password=LDAP_PASSWORD,
        auto_bind=True
    )


    nombre = normalizar(
        gerente.replace(
            "TIC ",
            ""
        )
    )


    filtro = (
        f"(&(objectClass=user)"
        f"(cn=*{nombre.split()[0]}*))"
    )


    conn.search(
        BASE_DN,
        filtro,
        search_scope=SUBTREE,
        attributes=[
            "cn",
            "mail"
        ]
    )


    resultados = []


    for entry in conn.entries:

        cn = str(
            entry.cn
        )

        mail = None

        if hasattr(entry, "mail"):
            mail = str(
                entry.mail
            )


        resultados.append(
            {
                "cn": cn,
                "mail": mail
            }
        )


    conn.unbind()


    if len(resultados) > 1:

        print("\nMULTIPLES ENCONTRADOS:")
        
        for r in resultados:
            print(
                "CN:",
                r["cn"],
                "MAIL:",
                r["mail"]
            )

        return (
            "",
            "MULTIPLES"
        )





    else:

        return (
            "",
            "NO ENCONTRADO"
        )



# =====================================
# EJECUCION
# =====================================


def main():

    gerentes = obtener_gerentes()


    print(
        f"Gerentes encontrados: {len(gerentes)}"
    )


    archivo = (
        "gerentes_campania.csv"
    )


    with open(
        archivo,
        "w",
        newline="",
        encoding="utf-8"
    ) as f:


        writer = csv.writer(f)


        writer.writerow(
            [
                "GERENTE",
                "CORREO",
                "ESTADO"
            ]
        )


        for gerente in gerentes:


            correo, estado = buscar_correo(
                gerente
            )


            print(
                gerente,
                "=>",
                correo,
                estado
            )


            writer.writerow(
                [
                    gerente,
                    correo,
                    estado
                ]
            )



if __name__ == "__main__":

    main()