-- =====================================================================
-- SOX Dashboard - Control 7 VPN internas: gerente asignado a mano por el administrador.
--
-- Ejecutar UNA sola vez con el propietario del esquema AUTOM, ANTES de desplegar el backend.
--
-- GERENTE_MANUAL = 1: la cuenta no tiene gerente en AD y el administrador se lo asignó en
-- Control 7 -> Internas -> Campañas. "Cargar desde LDAP", "Reemplazar carga" y el inicio de
-- una campaña nueva conservan ese gerente mientras AD siga sin tener uno.
-- =====================================================================

ALTER TABLE AUTOM.SOX_C7_VPN_INTERNAS ADD (GERENTE_MANUAL NUMBER(1) DEFAULT 0 NOT NULL);

ALTER TABLE AUTOM.SOX_C7_VPN_INTERNAS ADD CONSTRAINT SOX_C7_INT_MANUAL_CK CHECK (GERENTE_MANUAL IN (0, 1));

-- Verificación:
-- SELECT GERENTE_MANUAL, COUNT(*) FROM AUTOM.SOX_C7_VPN_INTERNAS GROUP BY GERENTE_MANUAL;
