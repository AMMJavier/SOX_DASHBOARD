-- =====================================================================
-- SOX Dashboard - Correos del Control 5 asociados a un evento
--
-- Ejecutar DESPUÉS de sox_mail_outbox.sql, una sola vez, con el
-- propietario del esquema AUTOM. Agrega el vínculo entre el correo y el
-- expediente individual (alta / modificación / baja) del Control 5.
-- Para los Controles 1, 2 y 3 la columna queda vacía.
-- =====================================================================

ALTER TABLE AUTOM.SOX_MAIL_OUTBOX ADD (EVENTO_ID NUMBER);

ALTER TABLE AUTOM.SOX_MAIL_OUTBOX ADD CONSTRAINT SOX_MAIL_OUTBOX_EVT_FK
    FOREIGN KEY (EVENTO_ID) REFERENCES AUTOM.SOX_CONTROL5_EVENTOS (ID);

-- El Control 5 siempre exige evento; los demás controles nunca lo usan.
ALTER TABLE AUTOM.SOX_MAIL_OUTBOX ADD CONSTRAINT SOX_MAIL_OUTBOX_EVT_CK CHECK
    ((CONTROL_NUMERO = 5 AND EVENTO_ID IS NOT NULL) OR (CONTROL_NUMERO <> 5 AND EVENTO_ID IS NULL));

CREATE INDEX AUTOM.SOX_MAIL_OUTBOX_EVT_IX ON AUTOM.SOX_MAIL_OUTBOX (EVENTO_ID);

-- Verificación:
-- SELECT ID, CONTROL_NUMERO, EVENTO_ID, ESTADO, ASUNTO FROM AUTOM.SOX_MAIL_OUTBOX WHERE CONTROL_NUMERO = 5;
