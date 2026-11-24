from services.sox.control_7.decision_rules import is_confirmed, is_reported, manager_key


def _snapshot(cursor):
    """VPN de la campaña (el trigger de FUENTE_CHECKPOINT reescribe REQ, solicitante y gerente)."""
    cursor.execute("""
        SELECT CHECKPOINT_UID, REQ, SOLICITANTE, GERENTE, ESTADO, OBSERVACION, CONFIRMACION, NOMBRE_VPN
          FROM AUTOM.CHECKPOINT_TRANSFORM
    """)
    keys = ("uid", "req", "solicitante", "gerente", "estado", "observacion", "confirmacion", "nombre")
    return {row[0]: dict(zip(keys, row)) for row in cursor.fetchall()}


def _apply_campaign_rules(cursor, before):
    """Reglas al actualizar la campaña (en la misma transacción de la sincronización):

    - Confirmada (Mantener / Eliminar): conserva su gerente, REQ y solicitante. No cambia.
    - Reportada (Otro / No pertenece): sigue pendiente. Si Check Point ya trae otro gerente,
      vuelve limpia para que la valide el nuevo y el cambio queda en el seguimiento.
    """
    kept = reassigned = 0
    for uid, new in _snapshot(cursor).items():
        old = before.get(uid)
        if not old:
            continue
        if is_confirmed(old["estado"], old["confirmacion"]):
            if any(old[k] != new[k] for k in ("req", "solicitante", "gerente")):
                cursor.execute("""
                    UPDATE AUTOM.CHECKPOINT_TRANSFORM
                       SET REQ = :p_req, SOLICITANTE = :p_sol, GERENTE = :p_ger
                     WHERE CHECKPOINT_UID = :p_uid
                """, {"p_req": old["req"], "p_sol": old["solicitante"], "p_ger": old["gerente"], "p_uid": uid})
                kept += 1
        elif manager_key(old["gerente"]) != manager_key(new["gerente"]) and not is_reported(old["estado"]):
            # Pendiente que Check Point pasó a otro gerente: la VPN cambió, se marca la fecha.
            cursor.execute("""
                UPDATE AUTOM.CHECKPOINT_TRANSFORM SET FECHA_MODIFICACION = SYSDATE WHERE CHECKPOINT_UID = :p_uid
            """, {"p_uid": uid})
        elif is_reported(old["estado"]):
            if manager_key(old["gerente"]) != manager_key(new["gerente"]):
                cursor.execute("""
                    UPDATE AUTOM.CHECKPOINT_TRANSFORM
                       SET ESTADO = 'mantener', OBSERVACION = NULL, CONFIRMACION = 0, FECHA_MODIFICACION = SYSDATE
                     WHERE CHECKPOINT_UID = :p_uid
                """, {"p_uid": uid})
                cursor.execute("""
                    INSERT INTO AUTOM.LOG_VALIDACION_SOX
                      (CHECKPOINT_UID, REQ, NOMBRE_VPN, GERENTE, ACCION, ESTADO_ANTERIOR, ESTADO_NUEVO,
                       DECISION_ANTERIOR, DECISION_NUEVA, OBSERVACION_ANTERIOR, OBSERVACION_NUEVA, USUARIO)
                    VALUES (:p_uid, :p_req, :p_vpn, :p_ger, 'CAMBIO_GERENTE', :p_ant, 'mantener',
                            :p_dant, 'mantener', :p_obs_ant, :p_obs, 'CHECKPOINT')
                """, {"p_uid": uid, "p_req": new["req"], "p_vpn": new["nombre"], "p_ger": new["gerente"],
                      "p_ant": old["estado"], "p_dant": old["estado"], "p_obs_ant": old["observacion"],
                      "p_obs": f"Gerente anterior: {old['gerente'] or 'sin gerente'}"[:200]})
                reassigned += 1
            elif int(old["confirmacion"] or 0) == 1:
                # Guardada con la regla anterior: Otro / No pertenece no cuenta como confirmada.
                cursor.execute("""
                    UPDATE AUTOM.CHECKPOINT_TRANSFORM SET CONFIRMACION = 0 WHERE CHECKPOINT_UID = :p_uid
                """, {"p_uid": uid})
    print(f"[SOX C7 EXTERNAS] Actualización: {kept} confirmada(s) conservan su gerente, "
          f"{reassigned} reportada(s) pasaron a un gerente nuevo", flush=True)


def insert_checkpoint_source(connection, registros):
    """Guarda la extracción de Check Point.

    FECHA_ALMACENADO (Fecha VPN) solo se escribe al insertar: queda la del inicio de la campaña
    o la del día en que apareció la VPN. "Actualizar campaña" no la cambia.
    """
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
        ON (destino.CHECKPOINT_UID = origen.CHECKPOINT_UID)
        WHEN MATCHED THEN UPDATE SET
            destino.NOMBRE_VPN = origen.NOMBRE_VPN,
            destino.COMENTARIO = origen.COMENTARIO,
            destino.COLOR = origen.COLOR
        WHEN NOT MATCHED THEN
            INSERT (CHECKPOINT_UID, NOMBRE_VPN, COMENTARIO, COLOR, FECHA_ALMACENADO)
            VALUES (origen.CHECKPOINT_UID, origen.NOMBRE_VPN, origen.COMENTARIO, origen.COLOR,
                    origen.FECHA_ALMACENADO)
    """
    try:
        before = _snapshot(cursor)
        for registro in registros:
            cursor.execute(sql, registro)
        _apply_campaign_rules(cursor, before)
        connection.commit()
    except Exception:
        # Sin esto una falla a mitad dejaría confirmadas con el gerente cambiado.
        connection.rollback()
        raise
    finally:
        cursor.close()

    print("--------------------------------")
    print("Proceso Oracle completado")
    print("Registros procesados:", len(registros))
    print("--------------------------------")
