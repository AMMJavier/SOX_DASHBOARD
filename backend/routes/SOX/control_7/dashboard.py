from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from database.oracle_connection import OracleConnection
from typing import Optional
from checkpoint.sync_service import sync_checkpoint_oracle
from datetime import datetime


# ==========================================================
# CONFIGURACIÓN DEL ROUTER SOX
# ==========================================================

router = APIRouter(
    tags=["SOX - Dashboard"]
)


@router.get("/admin/validations")
def get_all_validations_admin():

    oracle = OracleConnection()
    try:
        connection = oracle.connect()
        cursor = connection.cursor()

        query = """
        SELECT
            CHECKPOINT_UID,
            NOMBRE_VPN,
            REQ,
            SOLICITANTE,
            GERENTE,
            ESTADO,
            OBSERVACION,
            CONFIRMACION,
            FECHA_ALMACENADO,
            FECHA_MODIFICACION,
            FECHA_LIMITE
        FROM
        (
            SELECT t.*,
                ROW_NUMBER() OVER(
                    PARTITION BY CHECKPOINT_UID
                    ORDER BY 
                       FECHA_MODIFICACION DESC NULLS LAST,
                        FECHA_ALMACENADO DESC 
                ) rn
            FROM CHECKPOINT_TRANSFORM t
        )
        WHERE rn = 1
        ORDER BY GERENTE
        """

        cursor.execute(query)
        columns = [
            col[0].lower()
            for col in cursor.description
        ]
        data = []

        for row in cursor.fetchall():
            item = dict(
                zip(columns,row)
            )
            data.append({

                "id":
                    item["checkpoint_uid"],

                "nombre_vpn":
                    item["nombre_vpn"],

                "req":
                    item["req"],

                "solicitante":
                    item["solicitante"],

                "manager":
                    item["gerente"],

                "status":
                    item["estado"],

                "observation":
                    item["observacion"] or "",

                "confirmed":
                    item["confirmacion"],

                "date":
                    item["fecha_almacenado"],

                "fecha_modificacion":
                    item["fecha_modificacion"],

                "fecha_limite":
                    item["fehca_limite"],

            })
        return data

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

    finally:
        oracle.close()

@router.get("/admin/managers")
def get_admin_managers():

    oracle = OracleConnection()

    try:
        connection = oracle.connect()
        cursor = connection.cursor()

        query = """
        SELECT
            MIN(GERENTE) GERENTE,
            COUNT(*) TOTAL,
            SUM(
                CASE
                    WHEN CONFIRMACION = 1
                    THEN 1
                    ELSE 0
                END
            ) CONFIRMADOS

        FROM
        (
            SELECT
                CHECKPOINT_UID,

                TRIM(
                    REPLACE(GERENTE, CHR(160), ' ')
                ) GERENTE,

                UPPER(
                    NLSSORT(
                        TRIM(
                            REPLACE(GERENTE, CHR(160), ' ')
                        ),
                        'NLS_SORT=BINARY_AI'
                    )
                ) GERENTE_KEY,

                CONFIRMACION,

                ROW_NUMBER() OVER(
                    PARTITION BY CHECKPOINT_UID
                    ORDER BY
                        FECHA_MODIFICACION DESC NULLS LAST,
                        FECHA_ALMACENADO DESC
                ) RN

            FROM CHECKPOINT_TRANSFORM

            WHERE GERENTE IS NOT NULL
        )

        WHERE RN = 1

        GROUP BY GERENTE_KEY

        ORDER BY GERENTE
        """

        cursor.execute(query)

        managers = []

        for index, row in enumerate(cursor.fetchall(), start=1):
            managers.append({
                "id": index,
                "name": row[0]
            })

        return managers

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

    finally:
        oracle.close()

@router.get("/admin/dashboard/responsibles")
def get_dashboard_responsibles():

    oracle = OracleConnection()

    try:
        connection = oracle.connect()
        cursor = connection.cursor()

        query = """
        SELECT
            MIN(
                TRIM(
                    REPLACE(GERENTE, CHR(160), ' ')
                )
            ) GERENTE,
            COUNT(*) TOTAL,
            SUM(
                CASE
                    WHEN CONFIRMACION = 1
                    THEN 1
                    ELSE 0
                END
            ) CONFIRMADOS

        FROM
        (
            SELECT
                CHECKPOINT_UID,
                GERENTE,
                CONFIRMACION,

                ROW_NUMBER() OVER(
                    PARTITION BY CHECKPOINT_UID
                    ORDER BY
                        FECHA_MODIFICACION DESC NULLS LAST,
                        FECHA_ALMACENADO DESC
                ) RN
            FROM CHECKPOINT_TRANSFORM
            WHERE GERENTE IS NOT NULL
        )
        WHERE RN = 1
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
        responsibles = []

        for row in cursor.fetchall():

            gerente = row[0]
            total = row[1]
            confirmados = row[2] or 0

            porcentaje = 0

            if total > 0:
                porcentaje = round(
                    (confirmados / total) * 100
                )

            responsibles.append({

                "manager": gerente,
                "total": total,
                "confirmed": confirmados,
                "percent": porcentaje

            })

        return responsibles

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

    finally:
        oracle.close()
