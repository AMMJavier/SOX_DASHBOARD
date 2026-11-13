from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from database.oracle_connection import OracleConnection
from typing import Optional
from checkpoint.sync_service import sync_checkpoint_oracle
from datetime import datetime


from routes.sox.control_7.campaigns import router as campaign_router
from routes.sox.control_7.validations import router as validation_router
from routes.sox.control_7.dashboard import router as dashboard_router
from routes.sox.control_7.history import router as history_router
from routes.sox.control_7.logs import router as logs_router
from routes.sox.control_7.notifications import router as campaign_notifications_router
from routes.sox.control_5.events import router as controls_events5_router
from routes.sox.control_6.reconcile import router as controls_reconcile_router
from routes.sox.control_6.conciliations import router as controls_c6_conciliations_router
from routes.sox.common.evidence import router as controls_evidence_router
from routes.sox.common.reminders import router as controls_reminders_router
from routes.sox.common.mail import router as controls_mail_router
from routes.sox.control_6.ldap_access import router as controls_ldap_access_router
from routes.sox.control_6.cortes import router as controls_c6_cortes_router
# ==========================================================
# CONFIGURACIÓN DEL ROUTER SOX
# ==========================================================

router = APIRouter(
    prefix="/sox",
    tags=["SOX"]
)


router.include_router(campaign_router)
router.include_router(validation_router)
router.include_router(dashboard_router)
router.include_router(history_router)
router.include_router(logs_router)
router.include_router(campaign_notifications_router)
router.include_router(controls_events5_router)
router.include_router(controls_reconcile_router)
router.include_router(controls_c6_conciliations_router)
router.include_router(controls_evidence_router)



router.include_router(controls_reminders_router)
router.include_router(controls_mail_router)
router.include_router(controls_ldap_access_router)
router.include_router(controls_c6_cortes_router)
