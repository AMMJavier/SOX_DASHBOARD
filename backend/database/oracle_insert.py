def insert_checkpoint_source(connection, registros):

    cursor = connection.cursor()


    sql = """
        MERGE INTO AUTOM.FUENTE_CHECKPOINT destino

        USING (
            SELECT
                :checkpoint_uid AS checkpoint_uid,
                :nombre_vpn AS nombre_vpn,
                :comentario AS comentario,
                :color AS color,
                :fecha_almacenado AS fecha_almacenado
            FROM dual
        ) origen

        ON (
            destino.CHECKPOINT_UID = origen.CHECKPOINT_UID
        )


        WHEN MATCHED THEN

            UPDATE SET

                destino.NOMBRE_VPN = origen.NOMBRE_VPN,
                destino.COMENTARIO = origen.COMENTARIO,
                destino.COLOR = origen.COLOR,
                destino.FECHA_ALMACENADO = origen.FECHA_ALMACENADO


        WHEN NOT MATCHED THEN

            INSERT
            (
                CHECKPOINT_UID,
                NOMBRE_VPN,
                COMENTARIO,
                COLOR,
                FECHA_ALMACENADO
            )

            VALUES
            (
                origen.CHECKPOINT_UID,
                origen.NOMBRE_VPN,
                origen.COMENTARIO,
                origen.COLOR,
                origen.FECHA_ALMACENADO
            )
    """


    insertados = 0
    actualizados = 0


    for registro in registros:

        cursor.execute(
            sql,
            registro
        )


        if cursor.rowcount == 1:
            insertados += 1


    connection.commit()


    print("--------------------------------")
    print("Proceso Oracle completado")
    print("Registros procesados:", len(registros))
    print("--------------------------------")


    cursor.close()