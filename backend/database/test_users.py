from database.oracle_connection import OracleConnection


oracle = OracleConnection()


try:

    # Conexión Oracle
    connection = oracle.connect()


    cursor = connection.cursor()


    print("==============================")
    print("Usuarios registrados en SOX")
    print("==============================")


    cursor.execute("""
        SELECT
            ID,
            USERNAME,
            AUTH_PROVIDER,
            ROL,
            ACTIVO,
            CREADO_EN,
            ACTUALIZADO_EN
        FROM AUTOM.USUARIOS
        ORDER BY ID
    """)


    usuarios = cursor.fetchall()


    if not usuarios:
        print("No existen usuarios registrados")

    else:

        for usuario in usuarios:

            print("--------------------------------")
            print("ID:", usuario[0])
            print("USERNAME:", usuario[1])
            print("AUTH_PROVIDER:", usuario[2])
            print("ROL:", usuario[3])
            print("ACTIVO:", usuario[4])
            print("CREADO:", usuario[5])
            print("ACTUALIZADO:", usuario[6])


    cursor.close()


finally:

    oracle.close()