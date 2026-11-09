from database.oracle_connection import OracleConnection


oracle = OracleConnection()


try:

    connection = oracle.connect()


    cursor = connection.cursor()


    cursor.execute(
        "SELECT SYSDATE FROM DUAL"
    )


    fecha = cursor.fetchone()


    print(
        "Fecha servidor Oracle:",
        fecha[0]
    )


    cursor.close()


finally:

    oracle.close()