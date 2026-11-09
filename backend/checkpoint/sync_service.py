from checkpoint.extract_vpn import extract_vpn_data

from database.oracle_connection import OracleConnection
from database.oracle_insert import insert_checkpoint_source



def sync_checkpoint_oracle():


    print("==============================")
    print("SYNC CHECKPOINT - ORACLE")
    print("==============================")


    try:

        # ==========================
        # 1. Extraer Check Point
        # ==========================

        registros = extract_vpn_data()


        print(
            f"Registros preparados: {len(registros)}"
        )


        if not registros:

            print(
                "No existen registros para insertar"
            )

            return {
                "status": "EMPTY",
                "insertados": 0
            }



        # ==========================
        # 2. Conectar Oracle
        # ==========================

        oracle = OracleConnection()

        connection = oracle.connect()


        try:


            # ==========================
            # 3. Insertar histórico
            # ==========================

            insert_checkpoint_source(
                connection,
                registros
            )

        finally:

            oracle.close()

        return {

            "status": "OK",

            "total_datos": len(registros),

            "mensaje": "Sincronización completa"

        }

    except Exception as e:


        print(
            "Error sincronizando Check Point:",
            e
        )

        return {

            "status": "ERROR",

            "detalle": str(e)

        }


if __name__ == "__main__":

     sync_checkpoint_oracle()