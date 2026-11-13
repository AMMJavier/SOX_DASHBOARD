from fastapi import APIRouter, HTTPException
from pydantic import BaseModel


from database.oracle_connection import OracleConnection
from typing import Optional
from checkpoint.sync_service import sync_checkpoint_oracle
from datetime import datetime

router = APIRouter(
    tags=["SOX - Validation"]
)


# ==========================================================
# MODELOS DE DATOS
# ==========================================================

class ValidationConfirmItem(BaseModel):
    """
    Modelo recibido desde el frontend cuando un gerente
    guarda una decisión sobre una VPN.

    Dashboard relacionado:
    - ManagerDashboard

    Datos enviados:
    - decision:
        Mantener
        Eliminar
        No pertenece
        Otro

    - observation:
        Texto adicional obligatorio cuando la decisión es Otro.
    """
    decision: str
    observation: Optional[str] = None

class ValidationConfirmAllItem(BaseModel):
    checkpoint_uid: str
    decision: str
    observation: Optional[str] = None

class ValidationConfirmAllRequest(BaseModel):
    validations: list[ValidationConfirmAllItem]

print("MODELO CONFIRM ALL CARGADO DESDE validations.py")
print(ValidationConfirmAllRequest.model_json_schema())



@router.get("/managers")
def get_managers():
    oracle = OracleConnection()
    try:
        connection = oracle.connect()
        cursor = connection.cursor()
        

        query = """
            SELECT 
                MIN(GERENTE) GERENTE
            FROM CHECKPOINT_TRANSFORM
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
            ORDER BY 1
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

@router.get("/validations/manager/{manager}")
def get_validations_by_manager(manager: str):
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
        AND UPPER(
            NLSSORT(TRIM(GERENTE),'NLS_SORT=BINARY_AI')
        ) =
        UPPER(
            NLSSORT(TRIM(:manager),'NLS_SORT=BINARY_AI')
        )
        """

        cursor.execute(
            query,
            manager=manager
        )

        columns = [
            col[0].lower()
            for col in cursor.description
        ]
        data = []

        for row in cursor.fetchall():
            item = dict(
                zip(columns, row)
            )

            data.append({

                # Identificador único de la VPN
                "id": item["checkpoint_uid"],

                "nombre_vpn": item["nombre_vpn"],

                # Información principal
                "req": item["req"],
                "solicitante": item["solicitante"],
                "manager": item["gerente"],

                # Estado actual de validación
                "decision": (
                    item["estado"].capitalize()
                    if item["estado"]
                    else ""
                ),

                # Comentario del gerente
                "observation":
                    item["observacion"] or "",

                # Bandera de confirmación
                #
                # 0 = pendiente
                # 1 = confirmado
                #

                "confirmed":
                    item["confirmacion"],

                # Fecha límite mostrada en pantalla
                "fecha_almacenado":
                    item["fecha_almacenado"].strftime( "%d-%b-%Y")
                    if item["fecha_almacenado"]
                    else "",

                "fecha_limite":
                    item["fecha_limite"].strftime("%d-%b-%Y")
                    if item["fecha_limite"]
                    else ""
            })
        return data

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

    finally:
        oracle.close()


@router.patch("/validations/confirm-all")
def confirm_all_validations(
    request: ValidationConfirmAllRequest
):
    print("========== CONFIRM ALL INICIO ==========")
    print(f"Total recibidos: {len(request.validations)}")
    oracle = OracleConnection()
    actualizados = 0
    no_encontrados = []


    try:
        connection = oracle.connect()
        cursor = connection.cursor()

        # =====================================
        # VALIDAR FECHA LIMITE CAMPAÑA
        # =====================================
        cursor.execute("""
            SELECT FECHA_LIMITE
            FROM AUTOM.CAMPANAS_SOX
            WHERE ESTADO='ACTIVA'
        """)
        campaign_date = cursor.fetchone()

        if campaign_date:
            from datetime import datetime
            if datetime.now() > campaign_date[0]:
                raise HTTPException(
                    status_code=400,
                    detail="La campaña ya finalizó, no se permiten validaciones"
                )

        for item in request.validations:
            print(
                f"Actualizando UID: {item.checkpoint_uid}"
            )

            # =====================================
            # DATOS ANTERIORES PARA LOG
            # =====================================
            cursor.execute("""
                SELECT
                    REQ,
                    NOMBRE_VPN,
                    GERENTE,
                    ESTADO,
                    OBSERVACION
                FROM AUTOM.CHECKPOINT_TRANSFORM
                WHERE CHECKPOINT_UID = :1
            """,
            [item.checkpoint_uid])

            old_data = cursor.fetchone()
            if not old_data:
                no_encontrados.append(
                    item.checkpoint_uid
                )
                continue

            (
                req,
                nombre_vpn,
                gerente,
                estado_anterior,
                observacion_anterior
            ) = old_data

            print("ANTES UPDATE")
            # =====================================
            # ACTUALIZAR VPN
            # =====================================
            cursor.execute(
                """
                UPDATE AUTOM.CHECKPOINT_TRANSFORM
                SET
                    ESTADO = :1,
                    OBSERVACION = :2,
                    CONFIRMACION = 1,
                    FECHA_MODIFICACION = SYSDATE
                WHERE CHECKPOINT_UID = :3
                """,
                [
                    item.decision,
                    item.observation if item.observation else None,
                    item.checkpoint_uid
                ]
            )

            filas = cursor.rowcount
            if filas == 1:
                actualizados += 1
                print("ANTES LOG")
                # =====================================
                # INSERTAR AUDITORIA
                # =====================================
                cursor.execute("""
                    INSERT INTO AUTOM.LOG_VALIDACION_SOX
                    (
                        CHECKPOINT_UID,
                        REQ,
                        NOMBRE_VPN,
                        GERENTE,
                        ACCION,
                        ESTADO_ANTERIOR,
                        ESTADO_NUEVO,
                        DECISION_ANTERIOR,
                        DECISION_NUEVA,
                        OBSERVACION_ANTERIOR,
                        OBSERVACION_NUEVA,
                        USUARIO
                    )
                    VALUES
                    (
                        :1,
                        :2,
                        :3,
                        :4,
                        :5,
                        :6,
                        :7,
                        :8,
                        :9,
                        :10,
                        :11,
                        :12
                    )
                """,
                [
                    item.checkpoint_uid,
                    req,
                    nombre_vpn,
                    gerente,
                    "GUARDAR_MASIVO",
                    estado_anterior,
                    item.decision,
                    estado_anterior,
                    item.decision,
                    observacion_anterior,
                    item.observation,
                    gerente
                ])

            else:
                no_encontrados.append(
                    item.checkpoint_uid
                )

        connection.commit()

        print("==============================")
        print("CONFIRM ALL FINALIZADO")
        print(f"Actualizados: {actualizados}")
        print(f"No encontrados: {len(no_encontrados)}")
        print("==============================")

        return {
            "ok": True,
            "mensaje":
                "Validaciones confirmadas correctamente",
            "total_recibidos":
                len(request.validations),
            "actualizados":
                actualizados,
            "no_encontrados":
                no_encontrados
        }

    except HTTPException:
        raise

    except Exception as e:
        print("==============================")
        print("ERROR CONFIRM ALL")
        print(e)
        print("==============================")

        connection.rollback()
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

    finally:
        oracle.close()

@router.patch("/validations/{checkpoint_uid}")
def update_validation(
    checkpoint_uid: str,
    data: ValidationConfirmItem
):

    oracle = OracleConnection()
    try:
        connection = oracle.connect()
        cursor = connection.cursor()

        # =====================================
        # VALIDAR FECHA LIMITE DE CAMPAÑA
        # =====================================
        cursor.execute("""
            SELECT FECHA_LIMITE
            FROM AUTOM.CAMPANAS_SOX
            WHERE ESTADO='ACTIVA'
        """)

        campaign_date = cursor.fetchone()
        if campaign_date:
            from datetime import datetime
            if datetime.now() > campaign_date[0]:
                raise HTTPException(
                    status_code=400,
                    detail="La campaña ya finalizó, no se permiten validaciones"
                )

        # =====================================
        # OBTENER DATOS ACTUALES PARA AUDITORIA
        # =====================================
        cursor.execute("""
        SELECT
            REQ,
            NOMBRE_VPN,
            GERENTE,
            ESTADO,
            CONFIRMACION,
            ESTADO,
            OBSERVACION
        FROM AUTOM.CHECKPOINT_TRANSFORM
        WHERE CHECKPOINT_UID = :checkpoint_uid
    """,
    checkpoint_uid=checkpoint_uid)

        old_data = cursor.fetchone()
        if not old_data:
            raise HTTPException(
                status_code=404,
                detail="CHECKPOINT_UID no encontrado"
            )

        (
            req,
            nombre_vpn,
            gerente,
            estado_anterior,
            confirmacion_anterior,
            decision_anterior,
            observacion_anterior
        ) = old_data

        # =====================================
        # ACTUALIZAR VALIDACION
        # =====================================
        query = """
            UPDATE AUTOM.CHECKPOINT_TRANSFORM
            SET
                ESTADO = :estado,
                OBSERVACION = :observacion,
                CONFIRMACION = 1,
                FECHA_MODIFICACION = SYSDATE
            WHERE CHECKPOINT_UID = :checkpoint_uid
        """
        cursor.execute(
            query,
            estado=data.decision,
            observacion=data.observation,
            checkpoint_uid=checkpoint_uid
        )

        # =====================================
        # INSERTAR LOG DE AUDITORIA
        # =====================================
        cursor.execute("""
            INSERT INTO AUTOM.LOG_VALIDACION_SOX
            (
                CHECKPOINT_UID,
                REQ,
                NOMBRE_VPN,
                GERENTE,
                ACCION,
                ESTADO_ANTERIOR,
                ESTADO_NUEVO,
                DECISION_ANTERIOR,
                DECISION_NUEVA,
                OBSERVACION_ANTERIOR,
                OBSERVACION_NUEVA,
                USUARIO
            )
            VALUES
            (
                :checkpoint_uid,
                :req,
                :nombre_vpn,
                :gerente,
                'MODIFICACION_VALIDACION',
                :estado_anterior,
                :estado_nuevo,
                :decision_anterior,
                :decision_nueva,
                :observacion_anterior,
                :observacion_nueva,
                :usuario
            )
        """,
        checkpoint_uid=checkpoint_uid,
        req=req,
        nombre_vpn=nombre_vpn,
        gerente=gerente,
        estado_anterior=estado_anterior,
        estado_nuevo=data.decision,
        decision_anterior=decision_anterior,
        decision_nueva=data.decision,
        observacion_anterior=observacion_anterior,
        observacion_nueva=data.observation,
        usuario=gerente
        )

        connection.commit()

        return {
            "message":
                "Validación actualizada correctamente",
            "checkpoint_uid":
                checkpoint_uid,
            "confirmacion":
                1
        }

    except HTTPException:
        raise

    except Exception as e:
        connection.rollback()
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

    finally:
        oracle.close()


