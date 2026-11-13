from fastapi import APIRouter, HTTPException
from database.oracle_connection import OracleConnection

router = APIRouter(
    tags=["SOX Logs"]
)


@router.get("/audit/logs")
def get_audit_logs():
    oracle = OracleConnection()
    try:
        connection = oracle.connect()
        cursor = connection.cursor()
        cursor.execute("""
            SELECT
                FECHA_EVENTO,
                USUARIO,
                GERENTE,
                REQ,
                NOMBRE_VPN,
                ACCION,
                ESTADO_ANTERIOR,
                ESTADO_NUEVO,
                OBSERVACION_ANTERIOR,
                OBSERVACION_NUEVA
            FROM AUTOM.LOG_VALIDACION_SOX
            ORDER BY FECHA_EVENTO DESC
        """)

        columns = [
            col[0].lower()
            for col in cursor.description
        ]

        rows = cursor.fetchall()
        data = []
        for row in rows:
            item = dict(
                zip(columns,row)
            )
            data.append(item)
        return data

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

    finally:
        oracle.close()