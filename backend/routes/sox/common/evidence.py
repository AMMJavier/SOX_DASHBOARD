"""Repositorio de evidencias SOX 1/2/3/5/6. Oracle + directorio privado.

Las evidencias cargadas NO implican aprobación de Gerencia.
El estado VERIFICADA indica revisión interna registrada y auditada.
"""
from datetime import datetime, timezone
import hashlib
import os
import re
from pathlib import Path
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import text, Integer, outparam
from sqlalchemy.orm import Session

from auth.dependencies import get_current_user
from models import Usuario
from database.oracle_database import get_oracle_db

router = APIRouter(prefix="/controls", tags=["SOX controles 1, 2, 3, 5 y 6 - evidencias"])
MAX_BYTES = 15 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".eml", ".msg", ".doc", ".docx", ".png", ".jpg", ".jpeg", ".xlsx"}
EVIDENCE_TYPES = {
    1: {"revision", "solicitud", "aprobacion", "sis016"},
    2: {"plan", "revision", "aprobacion"},
    3: {"avance", "reunion", "aprobacion", "referencia"},
    5: {"aprobacion", "ejecucion", "solicitud", "consolidado"},
    6: {"rrhh", "accesos", "conciliacion", "baja", "informe"},
}
WRITERS = {"administrador", "desarrollador"}


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _check_control(control: int, anio: int, semestre: Optional[int]):
    if control not in EVIDENCE_TYPES:
        raise HTTPException(404, "Control no disponible en este repositorio")
    if not 2020 <= anio <= 2100:
        raise HTTPException(422, "Año inválido")
    if (control in (3, 6) and semestre not in (1, 2)) or (control in (1, 2) and semestre is not None) or (control == 5 and semestre not in (None, 1, 2)):
        raise HTTPException(422, "Semestre inválido para la periodicidad del control")


def _check_reader(user):
    if user.rol not in WRITERS:
        raise HTTPException(403, "Acceso a evidencias restringido al equipo responsable")


def _check_writer(user):
    _check_reader(user)


def _storage_root():
    raw = os.getenv("SOX_EVIDENCE_DIR", "").strip()
    if not raw:
        raise HTTPException(503, "SOX_EVIDENCE_DIR no configurado")
    root = Path(raw).resolve()
    if not root.is_dir() or not os.access(root, os.R_OK | os.W_OK | os.X_OK):
        raise HTTPException(503, "El directorio privado de evidencias no está disponible")
    return root


def _serialize(row):
    item = dict(row)
    for key, value in item.items():
        if isinstance(value, datetime):
            item[key] = value.isoformat()
    return item


@router.get("/{control}/evidencias")
def listar_evidencias(
    control: int, anio: int = Query(...), semestre: Optional[int] = Query(None),
    db: Session = Depends(get_oracle_db),
    current: Usuario = Depends(get_current_user),
):
    _check_reader(current)
    _check_control(control, anio, semestre)
    sql = text("""
        SELECT e.ID AS "id", e.CONTROL_NUMERO AS "control", e.ANIO AS "anio",
               e.SEMESTRE AS "semestre", e.TIPO_EVIDENCIA AS "tipo",
               e.REFERENCIA AS "referencia", e.OBSERVACIONES AS "observaciones",
               e.NOMBRE_ARCHIVO AS "nombre_archivo", e.TAMANIO_BYTES AS "bytes",
               e.EVENTO_ID AS "evento_id", ev.CUENTA AS "cuenta_evento",
               e.ESTADO AS "estado", e.CREADO_EN AS "creado_en",
               u.USERNAME AS "creado_por", v.USERNAME AS "verificado_por",
               e.VERIFICADO_EN AS "verificado_en"
          FROM AUTOM.SOX_CONTROL_EVIDENCIAS e
          JOIN AUTOM.USUARIOS u ON u.ID = e.CREADO_POR
          LEFT JOIN AUTOM.USUARIOS v ON v.ID = e.VERIFICADO_POR
          LEFT JOIN AUTOM.SOX_CONTROL5_EVENTOS ev ON ev.ID = e.EVENTO_ID
         WHERE e.CONTROL_NUMERO=:control AND e.ANIO=:anio
           AND (:control=5 OR ((:semestre IS NULL AND e.SEMESTRE IS NULL) OR e.SEMESTRE=:semestre))
         ORDER BY e.CREADO_EN DESC, e.ID DESC
    """)
    items = [_serialize(row) for row in db.execute(sql, {"control": control, "anio": anio, "semestre": semestre}).mappings()]
    return {"items": items, "total": len(items),
            "metrics": {"total": len(items), "confirmed": sum(x["estado"] == "VERIFICADA" for x in items),
                        "pending": sum(x["estado"] == "CARGADA" for x in items), "expired": None}}


@router.post("/{control}/evidencias", status_code=201)
async def subir_evidencia(
    control: int,
    file: UploadFile = File(...),
    anio: int = Form(...),
    semestre: Optional[int] = Form(None),
    tipo: str = Form(...),
    referencia: str = Form(""),
    observaciones: str = Form(""),
    evento_id: Optional[int] = Form(None),
    db: Session = Depends(get_oracle_db),
    current: Usuario = Depends(get_current_user),
):
    _check_writer(current)
    _check_control(control, anio, semestre)
    if tipo not in EVIDENCE_TYPES[control]:
        raise HTTPException(422, "Tipo documental no corresponde al control")
    # Los respaldos del control 5 se asocian a una intervención concreta.
    # Únicamente el consolidado es anual y complementario, sin un evento único.
    if control == 5:
        if tipo == "consolidado":
            if evento_id is not None:
                raise HTTPException(422, "El consolidado no se asocia a un evento individual")
            if semestre not in (1, 2):
                raise HTTPException(422, "El consolidado requiere semestre 1 o 2")
        else:
            if semestre is not None:
                raise HTTPException(422, "La evidencia de un evento no lleva semestre")
            if evento_id is None or evento_id < 1:
                raise HTTPException(422, "La evidencia individual requiere evento_id")
            event = db.execute(text("""
                SELECT ID FROM AUTOM.SOX_CONTROL5_EVENTOS
                WHERE ID=:id AND ANIO=:anio
            """), {"id": evento_id, "anio": anio}).first()
            if event is None:
                raise HTTPException(404, "El evento de Control 5 no existe en el año seleccionado")
    elif evento_id is not None:
        raise HTTPException(422, "evento_id solo corresponde al Control 5")
    original = Path((file.filename or "").replace("\\", "/")).name.strip()
    if not original or len(original) > 255 or any(ord(c) < 32 or ord(c) == 127 for c in original) or Path(original).suffix.lower() not in ALLOWED_EXTENSIONS:
        raise HTTPException(422, "Nombre o extensión de archivo no admitido")
    if len(referencia) > 250 or len(observaciones) > 1000:
        raise HTTPException(422, "Referencia u observaciones demasiado extensas")
    content = await file.read(MAX_BYTES + 1)
    await file.close()
    if not content or len(content) > MAX_BYTES:
        raise HTTPException(413, "Archivo vacío o superior a 15 MB")
    root = _storage_root()
    key = uuid4().hex
    destination = root / key  # Nunca utilizar el nombre suministrado por el navegador como ruta
    fd = None
    try:
        fd = os.open(str(destination), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as handle:
            fd = None
            handle.write(content)
        statement = text("""
          INSERT INTO AUTOM.SOX_CONTROL_EVIDENCIAS
            (CONTROL_NUMERO, ANIO, SEMESTRE, TIPO_EVIDENCIA, REFERENCIA, OBSERVACIONES,
             EVENTO_ID, NOMBRE_ARCHIVO, ARCHIVO_KEY, TAMANIO_BYTES, SHA256, ESTADO, CREADO_POR, CREADO_EN)
          VALUES (:control, :anio, :semestre, :tipo, :referencia, :observaciones,
                  :evento_id, :nombre_archivo, :archivo_key, :bytes, :sha256, 'CARGADA', :autor, :ahora)
          RETURNING ID INTO :returned_id
        """).bindparams(outparam("returned_id", Integer))
        result = db.execute(statement, {"control": control, "anio": anio, "semestre": semestre, "tipo": tipo,
               "referencia": referencia.strip() or None, "observaciones": observaciones.strip() or None,
               "evento_id": evento_id,
               "nombre_archivo": original, "archivo_key": key, "bytes": len(content),
               "sha256": hashlib.sha256(content).hexdigest(), "autor": current.id, "ahora": _now()})
        returned = result.out_parameters["returned_id"]
        ev_id = int(returned[0] if isinstance(returned, (tuple, list)) else returned)
        db.execute(text("""
            INSERT INTO AUTOM.SOX_CONTROL_EVIDENCIA_AUD
            (EVIDENCIA_ID, ACCION, USUARIO_ID, FECHA) VALUES (:eid, 'CARGA', :uid, :fecha)
        """), {"eid": ev_id, "uid": current.id, "fecha": _now()})
        db.commit()
        return {"id": ev_id, "evento_id": evento_id, "estado": "CARGADA", "nombre_archivo": original}
    except Exception:
        db.rollback()
        destination.unlink(missing_ok=True)
        raise
    finally:
        if fd is not None:
            os.close(fd)


@router.get("/{control}/evidencias/{evidence_id}/descargar")
def descargar_evidencia(
    control: int, evidence_id: int,
    db: Session = Depends(get_oracle_db),
    current: Usuario = Depends(get_current_user),
):
    _check_reader(current)
    if control not in EVIDENCE_TYPES:
        raise HTTPException(404, "Control inexistente")
    row = db.execute(text("""
        SELECT ARCHIVO_KEY AS "key", NOMBRE_ARCHIVO AS "filename", SHA256 AS "sha256"
        FROM AUTOM.SOX_CONTROL_EVIDENCIAS
        WHERE CONTROL_NUMERO=:control AND ID=:eid
    """), {"control": control, "eid": evidence_id}).mappings().first()
    if not row:
        raise HTTPException(404, "Evidencia inexistente")
    if not re.fullmatch(r"[0-9a-f]{32}", row["key"] or ""):
        raise HTTPException(503, "Identificador de almacenamiento inválido")
    path = _storage_root() / row["key"]
    if not path.is_file():
        raise HTTPException(503, "Archivo físico no disponible")
    # Comprobar integridad antes de entregar el documento protegido.
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != row["sha256"]:
        raise HTTPException(503, "La evidencia no supera la comprobación de integridad")
    # Registrar consulta para mantener trazabilidad (sin alterar aprobación).
    db.execute(text("""
        INSERT INTO AUTOM.SOX_CONTROL_EVIDENCIA_AUD
        (EVIDENCIA_ID,ACCION,USUARIO_ID,FECHA) VALUES (:eid,'DESCARGA',:uid,:fecha)
    """), {"eid": evidence_id, "uid": current.id, "fecha": _now()})
    db.commit()
    return FileResponse(path, media_type="application/octet-stream", filename=row["filename"],
                        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "no-store"})


@router.post("/{control}/evidencias/{evidence_id}/verificar")
def verificar_evidencia(control: int, evidence_id: int,
                        db: Session = Depends(get_oracle_db),
                        current: Usuario = Depends(get_current_user)):
    _check_reader(current)
    if control not in EVIDENCE_TYPES:
        raise HTTPException(404, "Control inexistente")
    if current.rol != "administrador":
        raise HTTPException(403, "La revisión documental requiere administrador")
    updated = db.execute(text("""
       UPDATE AUTOM.SOX_CONTROL_EVIDENCIAS
          SET ESTADO='VERIFICADA', VERIFICADO_POR=:uid, VERIFICADO_EN=:fecha
        WHERE ID=:eid AND CONTROL_NUMERO=:control AND ESTADO='CARGADA'
    """), {"uid": current.id, "fecha": _now(), "eid": evidence_id, "control": control})
    if updated.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "La evidencia no existe o ya fue verificada")
    db.execute(text("""
       INSERT INTO AUTOM.SOX_CONTROL_EVIDENCIA_AUD
       (EVIDENCIA_ID,ACCION,USUARIO_ID,FECHA,DETALLE)
       VALUES (:eid,'VERIFICACION',:uid,:fecha,'Verificación documental interna; no sustituye la aprobación corporativa')
    """), {"eid": evidence_id, "uid": current.id, "fecha": _now()})
    db.commit()
    return {"id": evidence_id, "estado": "VERIFICADA"}


@router.get("/{control}/historial")
def historial_evidencias(control: int, anio: int = Query(...),
                        semestre: Optional[int] = Query(None),
                        db: Session = Depends(get_oracle_db),
                        current: Usuario = Depends(get_current_user)):
    _check_reader(current)
    _check_control(control, anio, semestre)
    rows = db.execute(text("""
        SELECT a.ID AS "id", a.EVIDENCIA_ID AS "evidencia_id", a.ACCION AS "accion",
               a.FECHA AS "fecha", a.DETALLE AS "detalle", u.USERNAME AS "usuario",
               e.NOMBRE_ARCHIVO AS "archivo", e.EVENTO_ID AS "evento_id", ev.CUENTA AS "cuenta_evento"
          FROM AUTOM.SOX_CONTROL_EVIDENCIA_AUD a
          JOIN AUTOM.SOX_CONTROL_EVIDENCIAS e ON e.ID = a.EVIDENCIA_ID
          JOIN AUTOM.USUARIOS u ON u.ID=a.USUARIO_ID
          LEFT JOIN AUTOM.SOX_CONTROL5_EVENTOS ev ON ev.ID=e.EVENTO_ID
         WHERE e.CONTROL_NUMERO=:control AND e.ANIO=:anio
           AND (:control=5 OR ((:semestre IS NULL AND e.SEMESTRE IS NULL) OR e.SEMESTRE=:semestre))
         ORDER BY a.FECHA DESC, a.ID DESC FETCH FIRST 300 ROWS ONLY
    """), {"control": control, "anio": anio, "semestre": semestre}).mappings()
    return {"items": [_serialize(row) for row in rows]}


@router.get("/3/plan-referencia")
def plan_referencia(anio: int = Query(..., ge=2020, le=2100),
                    db: Session = Depends(get_oracle_db),
                    current: Usuario = Depends(get_current_user)):
    """Enlaza el Control 3 con la última versión verificada del plan del Control 2."""
    _check_reader(current)
    result = db.execute(text("""
        SELECT ID AS "id", NOMBRE_ARCHIVO AS "nombre_archivo", CREADO_EN AS "creado_en"
        FROM AUTOM.SOX_CONTROL_EVIDENCIAS
        WHERE CONTROL_NUMERO=2 AND ANIO=:anio AND TIPO_EVIDENCIA='plan'
          AND ESTADO='VERIFICADA'
        ORDER BY CREADO_EN DESC, ID DESC FETCH FIRST 1 ROWS ONLY
    """), {"anio": anio}).mappings().first()
    return {"plan": _serialize(result) if result else None}
