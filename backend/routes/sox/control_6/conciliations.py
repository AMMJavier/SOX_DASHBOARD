"""Control 6: previsualizar y registrar conciliación RR. HH. vs corte LDAP Oracle."""
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session
from auth.dependencies import get_current_user
from models import Usuario
from database.oracle_database import get_oracle_db
from services.sox.control_6.conciliation import (
    MAX_HR_BYTES, parse_hr_file, load_cut, reconcile, save_reconciliation, list_history,
)

router = APIRouter(prefix="/controls/6/conciliaciones", tags=["SOX Control 6 - conciliaciones"])


def _allow(user):
    if user.rol not in ("administrador", "desarrollador"):
        raise HTTPException(403, "Se requiere permiso técnico SOX para datos de RR. HH.")


async def _read_hr(file):
    if not file.filename or not file.filename.lower().endswith((".xlsx", ".csv")):
        raise HTTPException(422, "Cargar archivo oficial de RR. HH. CSV o XLSX")
    content = await file.read(MAX_HR_BYTES + 1)
    await file.close()
    if not content or len(content) > MAX_HR_BYTES:
        raise HTTPException(413, "Archivo RR. HH. vacío o superior a 5 MB")
    return content


@router.post("/previsualizar")
async def preview(
    corte_id: int = Form(...),
    archivo_rrhh: UploadFile = File(...),
    current: Usuario = Depends(get_current_user),
    db: Session = Depends(get_oracle_db),
):
    _allow(current)
    content = await _read_hr(archivo_rrhh)
    try:
        accounts = parse_hr_file(archivo_rrhh.filename, content)
        cut, memberships = load_cut(db, corte_id)
        return reconcile(cut, memberships, accounts)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/guardar", status_code=201)
async def save(
    corte_id: int = Form(...),
    anio: int = Form(...),
    semestre: int = Form(...),
    referencia_rrhh: str = Form(...),
    archivo_rrhh: UploadFile = File(...),
    current: Usuario = Depends(get_current_user),
    db: Session = Depends(get_oracle_db),
):
    _allow(current)
    content = await _read_hr(archivo_rrhh)
    try:
        return save_reconciliation(db, cut_id=corte_id, hr_filename=archivo_rrhh.filename,
                                   hr_content=content, hr_reference=referencia_rrhh,
                                   anio=anio, semestre=semestre, user=current)
    except ValueError as exc:
        raise HTTPException(409 if "ya está guardada" in str(exc) else 422, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(503, "No se pudo generar el informe PDF. Verificar dependencia reportlab") from exc


@router.get("/historial")
def history(current: Usuario = Depends(get_current_user), db: Session = Depends(get_oracle_db)):
    _allow(current)
    return {"items": list_history(db)}
