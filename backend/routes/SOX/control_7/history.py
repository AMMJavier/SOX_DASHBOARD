from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from database.oracle_connection import OracleConnection
from typing import Optional
from checkpoint.sync_service import sync_checkpoint_oracle
from datetime import datetime


router = APIRouter(
    tags=["SOX - History"]
)


@router.get(
    "/history",
    summary="Consultar histórico SOX"
)
def get_history(
    campaign_id: str = None,
    year: int = None,
    month: int = None,
    manager: str = None,
    status: str = None,
    search: str = None
):
    oracle = OracleConnection()
    try:
        connection = oracle.connect()
        cursor = connection.cursor()

        query = """
            SELECT
                H.ID_HISTORICO,
                C.NOMBRE_CAMPANA,
                C.FECHA_INICIO,
                C.FECHA_FIN,
                H.NOMBRE_VPN,
                H.REQ,
                H.GERENTE,
                H.ESTADO,
                H.OBSERVACION,
                H.FECHA_CIERRE,
                H.FECHA_MODIFICACION

            FROM AUTOM.CHECKPOINT_HISTORICO H
            INNER JOIN AUTOM.CAMPANAS_SOX C
            ON H.ID_CAMPANA = C.ID_CAMPANA
            WHERE 1=1
        """

        params = {}
        if campaign_id:
            query += " AND C.ID_CAMPANA = :campaign_id"
            params["campaign_id"] = campaign_id

        if year:
            query += " AND C.ANIO = :year"
            params["year"] = year

        if month:
            query += " AND EXTRACT(MONTH FROM C.FECHA_INICIO)=:month"
            params["month"] = month

        if manager:
            query += " AND H.GERENTE = :manager"
            params["manager"] = manager

        if status:
            query += " AND H.ESTADO = :status"
            params["status"] = status

        if search:
            query += """
            AND (
                LOWER(H.NOMBRE_VPN) LIKE LOWER(:search)
                OR LOWER(H.REQ) LIKE LOWER(:search)
                OR LOWER(H.GERENTE) LIKE LOWER(:search)
                OR LOWER(C.NOMBRE_CAMPANA) LIKE LOWER(:search)
            )
            """
            params["search"] = f"%{search}%"

        query += " ORDER BY H.ID_HISTORICO DESC"

        cursor.execute(query, params)
        rows = cursor.fetchall()
        data = []
        for row in rows:
            data.append({
                "id": row[0],
                "campaign_name": row[1],
                "campaign_period":
                    f"{row[2].strftime('%d-%b-%Y')} - {row[3].strftime('%d-%b-%Y')}",
                "vpn": row[4],
                "req": row[5],
                "manager": row[6],
                "department": "",
                "status": row[7],
                "decision": row[7],
                "observation": row[8],
                "deadline": row[3].strftime('%d-%b-%Y'),
                "closed_at":
                    row[9].strftime('%d-%b-%Y')
                    if row[9] else None,
                "modified_at":
                    row[10].strftime('%d-%b-%Y %H:%M')
                    if row[10] else None

            })

        return data
    finally:
        oracle.close()

# ENDPOINT PARA LLENAR LOS COMBOS PARA LA BUSQUEDA FILTRADA
@router.get(
    "/history/filters",
    tags=["SOX - History"]
)
def get_history_filters():
    oracle = OracleConnection()

    try:
        connection = oracle.connect()
        cursor = connection.cursor()

        cursor.execute("""
            SELECT 
                ID_CAMPANA,
                NOMBRE_CAMPANA
            FROM AUTOM.CAMPANAS_SOX
            ORDER BY ID_CAMPANA DESC
        """)

        campaigns = [
            {
                "id": row[0],
                "name": row[1]
            }
            for row in cursor.fetchall()
        ]

        cursor.execute("""
            SELECT DISTINCT ANIO
            FROM AUTOM.CAMPANAS_SOX
            ORDER BY ANIO DESC
        """)
        years = [
            row[0]
            for row in cursor.fetchall()
        ]

        cursor.execute("""
            SELECT 
                MIN(
                    TRIM(
                        REPLACE(GERENTE, CHR(160), ' ')
                    )
                ) GERENTE
            FROM AUTOM.CHECKPOINT_HISTORICO
            WHERE GERENTE IS NOT NULL
            GROUP BY
                UPPER(
                    TRANSLATE(
                        TRIM(
                            REPLACE(GERENTE, CHR(160), ' ')
                        ),
                        'ÁÉÍÓÚáéíóú',
                        'AEIOUaeiou'
                    )
                )
            ORDER BY GERENTE
        """)

        managers = [
            row[0]
            for row in cursor.fetchall()
        ]

        return {
            "campaigns": campaigns,
            "years": years,
            "managers": managers
        }

    finally:
        oracle.close()