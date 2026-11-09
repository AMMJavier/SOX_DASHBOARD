-- =====================================================================
-- SOX Dashboard - Notificaciones de apertura de campaña (Control 7)
--
-- Ejecutar DESPUÉS de sox_mail_outbox.sql y sox_mail_outbox_c5.sql, una
-- sola vez, con el propietario del esquema AUTOM.
--
-- Las notificaciones se registran en la misma bandeja (ORIGEN='CAMPANA').
-- No se duplican contactos: el correo se toma de AUTOM.SOX_GERENTES_CONTACTO
-- y aquí solo queda el intento, su resultado y a quién se dirigió.
-- La clave de idempotencia (C7-<campaña>-<gerente>-<intento>) impide que un
-- gerente reciba dos avisos por reintentos o dobles clics.
-- =====================================================================

ALTER TABLE AUTOM.SOX_MAIL_OUTBOX ADD (
    ID_CAMPANA   NUMBER,
    GERENTE      VARCHAR2(200),
    GERENTE_KEY  VARCHAR2(200)
);

-- Una notificación de campaña siempre identifica campaña y gerente.
ALTER TABLE AUTOM.SOX_MAIL_OUTBOX ADD CONSTRAINT SOX_MAIL_OUTBOX_CAMP_CK CHECK
    (ORIGEN <> 'CAMPANA' OR (ID_CAMPANA IS NOT NULL AND GERENTE_KEY IS NOT NULL));

CREATE INDEX AUTOM.SOX_MAIL_OUTBOX_CAMP_IX ON AUTOM.SOX_MAIL_OUTBOX (ID_CAMPANA, GERENTE_KEY);

-- Verificación:
-- SELECT ID_CAMPANA, GERENTE, DESTINATARIOS, ESTADO, FECHA_ENVIO, DETALLE
--   FROM AUTOM.SOX_MAIL_OUTBOX WHERE ORIGEN = 'CAMPANA' ORDER BY ID DESC;
