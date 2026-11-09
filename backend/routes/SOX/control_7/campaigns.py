from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from database.oracle_connection import OracleConnection
from typing import Optional
from checkpoint.sync_service import sync_checkpoint_oracle
from datetime import datetime, timedelta


# ==========================================================
# CONFIGURACIÓN DEL ROUTER SOX
# ==========================================================

router = APIRouter(
    tags=["SOX - Campaigns"]
)



# NAVBAR CAMPAÑA ACTIVA Y FECHA 
@router.get(
    "/campaign/active",
    summary="Obtener campaña activa"
)
def get_active_campaign():

    oracle = OracleConnection()

    try:

        connection = oracle.connect()
        cursor = connection.cursor()


        cursor.execute("""
            SELECT
                ID_CAMPANA,
                NOMBRE_CAMPANA,
                ANIO,
                SEMESTRE,
                FECHA_INICIO,
                FECHA_FIN,
                FECHA_LIMITE,
                ESTADO
            FROM AUTOM.CAMPANAS_SOX
            WHERE ESTADO = 'ACTIVA'
        """)

        row = cursor.fetchone()

        if not row:
            return {
                "message": "No existe campaña activa"
            }


        return {
            "id_campana": row[0],
            "nombre_campana": row[1],
            "anio": row[2],
            "semestre": row[3],
            "fecha_inicio": row[4],
            "fecha_fin": row[5],
            "fecha_limite": row[6],
            "estado": row[7]
        }


    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


    finally:
        oracle.close()

@router.get(
    "/campaign/status",
    tags=["SOX - Campaign"],
    summary="Estado de vigencia de campaña"
)
def get_campaign_status():
    oracle = OracleConnection()
    try:

        connection = oracle.connect()
        cursor = connection.cursor()

        cursor.execute("""
            SELECT
                FECHA_INICIO,
                FECHA_LIMITE
            FROM AUTOM.CAMPANAS_SOX
            WHERE ESTADO='ACTIVA'
        """)

        row = cursor.fetchone()
        if not row:
            return {
                "active": False,
                "expired": True,
                "fecha_limite": None
            }
        fecha_inicio = row [0]
        fecha_limite = row[1]

        from datetime import datetime
        expired = datetime.now() > fecha_limite

        dias_restantes = (
            fecha_limite.date() -
            datetime.now().date()
        ).days

        
        dias_totales = (
            fecha_limite.date()
            -
            fecha_inicio.date()
        ).days

        porcentaje_restante = max(
            0,
            min(
                100,
                (dias_restantes / dias_totales ) *100
            )
        )
        
           
        if dias_restantes <= 0:
            semaforo = "rojo"
        elif porcentaje_restante <= 25:
            semaforo = "rojo"
        elif porcentaje_restante <= 50:
            semaforo = "amarillo"
        else:
            semaforo = "verde"


        return {
            "active": True,
            "expired": expired,
            "fecha_inicio":
                fecha_inicio.strftime("%d-%b-%Y"),
            "fecha_limite":
                fecha_limite.strftime("%d-%b-%Y"),
            "dias_restantes":
                dias_restantes,
            "dias_totales":
                dias_totales,
            "porcentaje_restante":
                round(porcentaje_restante),
            "semaforo":
                semaforo

        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

    finally:
        oracle.close()

@router.post(
    "/campaign/sync",
    tags=["SOX - Campaign"],
    summary="Actualizar datos de campaña activa"
)
def sync_active_campaign():

    oracle = OracleConnection()

    try:

        connection = oracle.connect()
        cursor = connection.cursor()


        # 1. Validar que exista campaña activa

        cursor.execute("""
            SELECT
                ID_CAMPANA,
                NOMBRE_CAMPANA
            FROM AUTOM.CAMPANAS_SOX
            WHERE ESTADO='ACTIVA'
        """)

        campana = cursor.fetchone()


        if not campana:
            raise HTTPException(
                status_code=400,
                detail="No existe una campaña activa para actualizar"
            )


        id_campana = campana[0]
        nombre_campana = campana[1]


        # 2. Ejecutar sincronización Check Point
        # 2. Ejecutar sincronización Check Point
        try:

            from checkpoint.sync_service import sync_checkpoint_oracle

            resultado = sync_checkpoint_oracle()

           


        except Exception as e:

            raise Exception(
                f"Error ejecutando sincronización: {str(e)}"
            )


        connection.commit()

        return {

            "success": True,
            "message": "Campaña actualizada correctamente",
            "campana": nombre_campana,
            "id_campana": id_campana,
            "resultado": resultado

        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

    finally:
        oracle.close()

@router.post(
    "/campaign/start",
    tags=["SOX - Campaign"],
    summary="Iniciar nueva campaña SOX"
)
def start_campaign():
    oracle = OracleConnection()

    try:
        connection = oracle.connect()
        cursor = connection.cursor()

        # 1. Validar que no exista campaña activa
        cursor.execute("""
            SELECT COUNT(*)
            FROM AUTOM.CAMPANAS_SOX
            WHERE ESTADO='ACTIVA'
        """)
        activa = cursor.fetchone()[0]

        if activa > 0:
            return {
                "success": False,
                "message": "Ya existe una campaña activa"
            }
        
        
        # 2. Ejecutar primera sincronización
        from checkpoint.sync_service import sync_checkpoint_oracle
        resultado = sync_checkpoint_oracle()
       
        # 3. Obtener última campaña creada       
        cursor.execute("""
            SELECT
                ANIO,
                SEMESTRE
            FROM AUTOM.CAMPANAS_SOX
            ORDER BY ID_CAMPANA DESC
            FETCH FIRST 1 ROW ONLY
        """)
        ultima = cursor.fetchone()

        if ultima:
            anio_actual = ultima[0]
            semestre_actual = ultima[1]

            # Última campaña fue primer semestre
            # Crear segundo semestre del mismo año
            if semestre_actual == 1:
                nuevo_anio = anio_actual
                nuevo_semestre = 2
                nombre = (
                    f"CONTROL 7 - SEGUNDO SEMESTRE {nuevo_anio}"
                )
                fecha_fin = f"31-12-{nuevo_anio}"

            # Última campaña fue segundo semestre
            # Crear primer semestre del siguiente año
            elif semestre_actual == 2:
                nuevo_anio = anio_actual + 1
                nuevo_semestre = 1
                nombre = (
                    f"CONTROL 7 - PRIMER SEMESTRE {nuevo_anio}"
                )
                fecha_fin = f"30-06-{nuevo_anio}"

        else:

            # Primera campaña del sistema
            # El semestre se determina mediante la fecha
            # de almacenamiento de las VPN

            cursor.execute("""
                SELECT MAX(FECHA_ALMACENADO)
                FROM AUTOM.CHECKPOINT_TRANSFORM
            """)
            fecha_vpn = cursor.fetchone()[0]


            if not fecha_vpn:
                raise Exception(
                    "No existen registros VPN para determinar el semestre"
                )

            nuevo_anio = fecha_vpn.year
            mes = fecha_vpn.month

            # Enero - Junio
            if mes <= 6:
                nuevo_semestre = 1
                nombre = (
                    f"CONTROL 7 - PRIMER SEMESTRE {nuevo_anio}"
                )
                fecha_fin = (
                    f"30-06-{nuevo_anio}"
                )

            # Julio - Diciembre
            else:

                nuevo_semestre = 2
                nombre = (
                    f"CONTROL 7 - SEGUNDO SEMESTRE {nuevo_anio}"
                )
                fecha_fin = (
                    f"31-12-{nuevo_anio}"
                )

        print("==============================")
        print("NUEVA CAMPAÑA")
        print("AÑO:", nuevo_anio)
        print("SEMESTRE:", nuevo_semestre)
        print("NOMBRE:", nombre)
        print("FECHA FIN:", fecha_fin)
        print("==============================")

         

        # 4. Crear nueva campaña
        cursor.execute("""
            INSERT INTO AUTOM.CAMPANAS_SOX
            (
                NOMBRE_CAMPANA,
                ANIO,
                SEMESTRE,
                FECHA_INICIO,
                FECHA_FIN,
                FECHA_LIMITE,
                ESTADO
            )
            VALUES
            (
                :nombre,
                :anio,
                :semestre,
                SYSDATE,
                TO_DATE(:fecha_fin,'DD-MM-YYYY'),
                SYSDATE + 14,
                'ACTIVA'
            )
        """,
        {
            "nombre": nombre,
            "anio": nuevo_anio,
            "semestre": nuevo_semestre,
            "fecha_fin": fecha_fin
        })
        connection.commit()

       
        


        # 5. Actualizar contactos LDAP
        from services.manager_contact_sync import sincronizar
        contactos = sincronizar()

        # 6. Preparar avisos a gerentes (sin enviar).
        # El envío real se revisa y confirma en Campañas > Notificación a gerentes,
        # con los gerentes de ESTA campaña, sus contactos y control de duplicados.
        from oracle_database import SessionLocal
        from services.sox_c7_notifications import start_summary
        db_resumen = SessionLocal()
        try:
            correo = start_summary(db_resumen)
        finally:
            db_resumen.close()

        return {

            "success": True,
            "message": "Campaña iniciada correctamente",
            "campana": nombre,
            "anio": nuevo_anio,
            "semestre": nuevo_semestre,
            "resultado": resultado,
            "contactos": contactos,
            "correo": correo

        }

    except Exception as e:
        print("==============================")
        print("ERROR CAMPAÑA SOX:")
        print(e)
        print("==============================")

        connection.rollback()

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


    finally:

        oracle.close()


@router.post(
    "/campaign/close",
    tags=["SOX - Campaign"],
    summary="Cerrar campaña y mover datos a histórico"
)
def close_campaign():
    oracle = OracleConnection()

    try:
        connection = oracle.connect()
        cursor = connection.cursor()

        # 1. Obtener campaña activa actual
        cursor.execute("""
            SELECT 
                ID_CAMPANA,
                NOMBRE_CAMPANA,
                ANIO,
                SEMESTRE,
                FECHA_FIN
            FROM AUTOM.CAMPANAS_SOX
            WHERE ESTADO='ACTIVA'
        """)

        campana = cursor.fetchone()

        if not campana:
            raise Exception("No existe una campaña activa")


        id_campana = campana[0]
        nombre_actual = campana[1]
        anio_actual = campana[2]
        semestre_actual = campana[3]


        # 2. Validar existencia de registros
        cursor.execute("""
            SELECT COUNT(*)
            FROM AUTOM.CHECKPOINT_TRANSFORM
        """)

        cantidad = cursor.fetchone()[0]

        if cantidad == 0:
            raise Exception(
                "No existen registros activos para cerrar la campaña"
            )


        # 3. Pasar información al histórico
        cursor.execute("""
            INSERT INTO AUTOM.CHECKPOINT_HISTORICO
            (
                ID_CAMPANA,
                ID_ORIGEN,
                CHECKPOINT_UID,
                REQ,
                SOLICITANTE,
                GERENTE,
                ESTADO,
                COLOR,
                FECHA_ALMACENADO,
                OBSERVACION,
                CONFIRMACION,
                NOMBRE_VPN,
                FECHA_MODIFICACION
            )
            SELECT
                :id_campana,
                ID,
                CHECKPOINT_UID,
                REQ,
                SOLICITANTE,
                GERENTE,
                ESTADO,
                COLOR,
                FECHA_ALMACENADO,
                OBSERVACION,
                CONFIRMACION,
                NOMBRE_VPN,
                FECHA_MODIFICACION
            FROM AUTOM.CHECKPOINT_TRANSFORM
        """,
        {
            "id_campana": id_campana
        })

        registros = cursor.rowcount


        # 4. Limpiar tabla operativa
        cursor.execute("""
            DELETE FROM AUTOM.CHECKPOINT_TRANSFORM
        """)


        # 5. Limpiar fuente de extracción
        cursor.execute("""
            TRUNCATE TABLE AUTOM.FUENTE_CHECKPOINT
        """)


        # 6. Cerrar campaña actual
        cursor.execute("""
            UPDATE AUTOM.CAMPANAS_SOX
            SET ESTADO='CERRADA'
            WHERE ID_CAMPANA=:id_campana
        """,
        {
            "id_campana": id_campana
        })

        connection.commit()


        return {
            "message": "Campaña cerrada correctamente",
            "registros_historico": registros,
        }


    except Exception as e:

        connection.rollback()

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


    finally:
        oracle.close()

@router.get(
    "/campaign/validation-filters",
    tags=["SOX - Campaign"],
    summary="Obtener filtros de validaciones activas"
)
def get_validation_filters():

    oracle = OracleConnection()

    try:

        connection = oracle.connect()
        cursor = connection.cursor()


        # Obtener gerentes únicos

        cursor.execute("""
            SELECT 
                MIN(
                    TRIM(
                        REPLACE(GERENTE, CHR(160), ' ')
                    )
                ) GERENTE
            FROM AUTOM.CHECKPOINT_TRANSFORM
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


        # Obtener estados únicos
        cursor.execute("""
            SELECT DISTINCT
                CASE
                    WHEN UPPER(TRIM(ESTADO)) = 'MANTENER'
                        THEN 'Mantener'

                    WHEN UPPER(TRIM(ESTADO)) = 'ELIMINAR'
                        THEN 'Eliminar'

                    WHEN UPPER(TRIM(ESTADO)) = 'OTRO'
                        THEN 'Otro'

                    WHEN UPPER(TRIM(ESTADO)) = 'NO PERTENECE'
                        THEN 'No pertenece'

                END AS ESTADO
            FROM AUTOM.CHECKPOINT_TRANSFORM
            WHERE ESTADO IS NOT NULL
            ORDER BY ESTADO
        """)

        statuses = [
            row[0]
            for row in cursor.fetchall()
        ]

        return {
            "managers": managers,
            "statuses": statuses
        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

    finally:

        oracle.close()

@router.get("/campaign/validations")
def get_campaign_validations(
    search: str = None,
    manager: str = None,
    status: str = None
):
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
                    ORDER BY FECHA_ALMACENADO DESC
                ) rn
            FROM CHECKPOINT_TRANSFORM t
        )
        WHERE rn = 1
        """
        if manager:
            query += """
            AND GERENTE = :manager
            """


        if status:
            query += """
            AND ESTADO = :status
            """

        if search:
            query += """
            AND (
                LOWER(NOMBRE_VPN) LIKE LOWER(:search)
                OR LOWER(REQ) LIKE LOWER(:search)
                OR LOWER(SOLICITANTE) LIKE LOWER(:search)
                OR LOWER(GERENTE) LIKE LOWER(:search)
            )
            """

        query += """
        ORDER BY GERENTE
        """
        params = {}

        if manager:
                params["manager"] = manager

        if status:
                params["status"] = status

        if search:
                params["search"] = f"%{search}%"

        cursor.execute(
                query,
                params
)

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
                    item["fecha_limite"],
            })
        # Total extraído desde Check Point
        cursor.execute("""
            SELECT COUNT(*)
            FROM AUTOM.FUENTE_CHECKPOINT
        """)

        total_checkpoint = cursor.fetchone()[0]

        return {
            "data":data,
            "total_checkpoint": total_checkpoint
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

    finally:
        oracle.close()
