-- =====================================================================
-- RESPALDO del trigger ORIGINAL (antes de checkpoint_rechazados.sql).
-- Ejecutar SOLO para volver atrás: deja el trigger como estaba.
-- (La tabla CHECKPOINT_RECHAZADOS y la función F_CHECKPOINT_MOTIVO pueden
--  quedarse; no afectan nada si el trigger no las usa.)
-- =====================================================================

CREATE OR REPLACE TRIGGER AUTOM.TRG_FUENTE_CHECKPOINT_TRANSFORM
AFTER INSERT OR UPDATE ON AUTOM.FUENTE_CHECKPOINT
FOR EACH ROW
DECLARE
    v_pos1        PLS_INTEGER;
    v_pos2        PLS_INTEGER;
    v_pos3        PLS_INTEGER;
    v_req         VARCHAR2(50);
    v_solicitante VARCHAR2(200);
    v_gerente     VARCHAR2(200);
BEGIN
    IF :NEW.COMENTARIO IS NOT NULL THEN
        v_pos1 := INSTR(:NEW.COMENTARIO, ' - ', 1, 1);  -- 1ra ocurrencia del separador
        v_pos2 := INSTR(:NEW.COMENTARIO, ' - ', 1, 2);  -- 2da ocurrencia
        v_pos3 := INSTR(:NEW.COMENTARIO, ' - ', 1, 3);  -- 3ra ocurrencia (debe ser 0)

        -- Debe existir separador 1 y 2, pero NO un 3ro (exactamente 3 partes)
        IF v_pos1 > 0 AND v_pos2 > v_pos1 AND v_pos3 = 0 THEN
            v_req         := TRIM(SUBSTR(:NEW.COMENTARIO, 1, v_pos1 - 1));
            v_solicitante := TRIM(SUBSTR(:NEW.COMENTARIO, v_pos1 + 3, v_pos2 - (v_pos1 + 3)));
            v_gerente     := TRIM(SUBSTR(:NEW.COMENTARIO, v_pos2 + 3));

            -- Adicional: ninguna de las 3 partes puede quedar vacia tras el TRIM
            IF v_req IS NOT NULL AND v_solicitante IS NOT NULL AND v_gerente IS NOT NULL THEN
                MERGE INTO CHECKPOINT_TRANSFORM T
                USING (
                    SELECT
                        :NEW.CHECKPOINT_UID AS CHECKPOINT_UID,
                        v_req AS REQ,
                        v_solicitante AS SOLICITANTE,
                        v_gerente AS GERENTE,
                        :NEW.COLOR AS COLOR,
                        :NEW.FECHA_ALMACENADO AS FECHA_ALMACENADO,
                        :NEW.NOMBRE_VPN AS NOMBRE_VPN
                    FROM DUAL
                ) S
                ON (T.CHECKPOINT_UID = S.CHECKPOINT_UID)
                WHEN MATCHED THEN
                UPDATE SET
                    T.REQ = S.REQ,
                    T.SOLICITANTE = S.SOLICITANTE,
                    T.GERENTE = S.GERENTE,
                    T.COLOR = S.COLOR,
                    T.FECHA_ALMACENADO = S.FECHA_ALMACENADO,
                    T.NOMBRE_VPN = S.NOMBRE_VPN
                WHEN NOT MATCHED THEN
                INSERT (CHECKPOINT_UID, REQ, SOLICITANTE, GERENTE, ESTADO, COLOR,
                        FECHA_ALMACENADO, CONFIRMACION, NOMBRE_VPN)
                VALUES (S.CHECKPOINT_UID, S.REQ, S.SOLICITANTE, S.GERENTE, 'mantener', S.COLOR,
                        S.FECHA_ALMACENADO, 0, S.NOMBRE_VPN);
            END IF;
        END IF;
    END IF;
END;
/

ALTER TRIGGER AUTOM.TRG_FUENTE_CHECKPOINT_TRANSFORM ENABLE;
