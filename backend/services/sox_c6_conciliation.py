"""Control SOX 6: conciliación de cesantes RR. HH. contra corte LDAP persistido.

Nunca escribe en Active Directory. Genera expediente PDF privado, registro Oracle
 y auditoría documental en una transacción, con compensación del archivo si falla.
"""
from __future__ import annotations

import csv
from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO, StringIO
import os
from pathlib import Path
import re
import unicodedata
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import text, Integer, outparam

from routes.SOX.core.evidence import _storage_root

MAX_HR_BYTES = 5 * 1024 * 1024
MAX_HR_ROWS = 2000
ALLOWED_COLUMNS = {"usuario", "usuario_ad", "samaccountname", "username", "cuenta", "login", "id_usuario", "usuario_dominio"}


def now_utc():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def normalize_account(value):
    value = unicodedata.normalize("NFKC", str(value or "")).strip().casefold()
    if value.startswith("porta\\"):
        value = value[len("porta\\"):]
    if value.endswith("@porta.corp"):
        value = value[:-len("@porta.corp")]
    if not re.fullmatch(r"[a-z0-9._$-]{1,100}", value):
        return None
    return value


def _heading(text_value):
    value = unicodedata.normalize("NFKD", str(text_value or "")).casefold()
    return re.sub(r"[^a-z0-9]+", "_", "".join(c for c in value if not unicodedata.combining(c))).strip("_")


def parse_hr_file(filename, data):
    """Aceptar CSV/XLSX con columna de cuenta de dominio; jamás cruzar por nombre."""
    if not data or len(data) > MAX_HR_BYTES:
        raise ValueError("Archivo de RR. HH. vacío o superior a 5 MB")
    extension = Path(filename or "").suffix.lower()
    if extension == ".csv":
        try:
            content = data.decode("utf-8-sig")
        except UnicodeDecodeError as e:
            raise ValueError("El CSV debe estar codificado en UTF-8") from e
        try:
            dialect = csv.Sniffer().sniff(content[:4096], delimiters=",;\t|")
        except csv.Error:
            dialect = csv.excel
        reader = csv.reader(StringIO(content, newline=""), dialect)
        rows = iter(reader)
    elif extension == ".xlsx":
        try:
            from openpyxl import load_workbook
        except ImportError as e:
            raise ValueError("Falta openpyxl para procesar Excel .xlsx") from e
        try:
            workbook = load_workbook(BytesIO(data), read_only=True, data_only=True)
            worksheet = workbook.active
            rows = iter(worksheet.iter_rows(values_only=True))
        except Exception as e:
            raise ValueError("Archivo Excel inválido") from e
    else:
        raise ValueError("RR. HH.: se admite únicamente CSV UTF-8 o Excel .xlsx")
    try:
        first = next(rows, None)
        if not first:
            raise ValueError("Archivo de RR. HH. sin encabezados")
        columns = [_heading(x) for x in first]
        matches = [i for i, h in enumerate(columns) if h in ALLOWED_COLUMNS]
        if len(matches) != 1:
            raise ValueError("El archivo debe tener una columna de cuenta de dominio (usuario, usuario_ad, sAMAccountName o cuenta); no se admiten nombres personales como identificador")
        column = matches[0]
        accounts = []
        for row in rows:
            if not row or all(x is None or not str(x).strip() for x in row):
                continue
            if len(accounts) >= MAX_HR_ROWS:
                raise ValueError("RR. HH.: máximo 2000 cuentas por conciliación")
            accounts.append(str(row[column] if len(row) > column and row[column] is not None else "").strip())
        if not accounts:
            raise ValueError("No se encontraron cuentas de RR. HH. en el archivo")
        return accounts
    finally:
        if extension == ".xlsx" and "workbook" in locals():
            workbook.close()


def load_cut(db, cut_id):
    row = db.execute(text("""
        SELECT ID, FECHA_REGISTRO_UTC, FECHA_EXTRACCION_UTC, TOTAL_RDP,
               TOTAL_APLICACIONES, TOTAL_CUENTAS
        FROM AUTOM.SOX_C6_CORTES_LDAP WHERE ID=:p_id
    """), {"p_id": int(cut_id)}).first()
    if not row:
        raise ValueError("El corte LDAP seleccionado no existe")
    rows = db.execute(text("""
        SELECT USUARIO, NOMBRE, ACTIVO, TIPO_ACCESO
        FROM AUTOM.SOX_C6_ACCESOS_LDAP WHERE CORTE_ID=:p_corte
        ORDER BY USUARIO, TIPO_ACCESO
    """), {"p_corte": int(cut_id)}).all()
    if not rows:
        raise ValueError("El corte LDAP seleccionado no contiene accesos")
    memberships = [(str(r[0]), str(r[1] or ""), None if r[2] is None else int(r[2]), str(r[3])) for r in rows]
    return {
        "id": int(row[0]),
        "fecha_registro_utc": row[1].isoformat() if row[1] else None,
        "fecha_extraccion_utc": row[2].isoformat() if row[2] else None,
        "rdp": int(row[3]), "aplicaciones": int(row[4]), "cuentas_unicas": int(row[5]),
    }, memberships


def reconcile(cut, memberships, hr_accounts):
    """Cruce exacto conservando duplicados, ambigüedades y membresías múltiples."""
    if not hr_accounts or len(hr_accounts) > MAX_HR_ROWS:
        raise ValueError("Se requieren entre 1 y 2000 cuentas de RR. HH.")
    from collections import Counter, defaultdict
    index = defaultdict(list)
    for account, name, active, group in memberships:
        normalized = normalize_account(account)
        if normalized:
            index[normalized].append({"grupo": group, "activo": active, "nombre": name})
    keys = [normalize_account(raw) for raw in hr_accounts]
    duplicates = Counter(x for x in keys if x is not None)
    result = []
    for raw, key in zip(hr_accounts, keys):
        matches = index.get(key, []) if key else []
        status = "ambiguo" if not key or duplicates[key] > 1 else ("coincide" if matches else "no_coincide")
        result.append({"cuenta_rrhh": str(raw)[:120], "cuenta_normalizada": key,
                       "estado": status, "accesos": matches,
                       "motivo": "Identificador inválido" if not key else "Cuenta duplicada en RR. HH." if duplicates[key] > 1 else None})
    summary = {"rrhh": len(result), "coincidencias": sum(x["estado"] == "coincide" for x in result),
               "sin_coincidencia": sum(x["estado"] == "no_coincide" for x in result),
               "ambiguos": sum(x["estado"] == "ambiguo" for x in result),
               "membresias_encontradas": sum(len(x["accesos"]) for x in result if x["estado"] == "coincide")}
    return {"corte": cut, "resumen": summary, "items": result,
            "nota": "Coincidencia de membresías LDAP en el corte seleccionado. No acredita uso de VPN, ni valida la cesantía, ni autoriza una baja. SASE no integrado."}


def _pdf_str(v):
    # Helvetica de ReportLab soporta los acentos españoles habituales; evita controles.
    value = "".join(c if ord(c) >= 32 else " " for c in str(v or ""))
    return value[:180]


def generate_pdf(reconciliation, *, username, hr_reference, hr_filename, report_time, hr_hash):
    """PDF auto-generado como evidencia, con resultados y parámetros reproducibles."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.pdfgen.canvas import Canvas
    except ImportError as e:
        raise RuntimeError("Falta instalar reportlab en el backend") from e
    buf = BytesIO()
    page_width, page_height = landscape(A4)
    pdf = Canvas(buf, pagesize=(page_width, page_height), pageCompression=1)
    margin = 40
    y = page_height - margin
    page = 0

    def header():
        nonlocal y, page
        page += 1
        pdf.setFont("Helvetica-Bold", 13)
        pdf.drawString(margin, page_height - 33, "HITSS | SOX Control 6 - Informe de conciliación de accesos internos")
        pdf.setStrokeColor(colors.HexColor("#D7DEE8"))
        pdf.line(margin, page_height - 44, page_width - margin, page_height - 44)
        pdf.setFont("Helvetica", 8)
        pdf.drawRightString(page_width - margin, 22, f"Página {page}")
        y = page_height - 63

    def line(text_value, bold=False, size=9, indent=0):
        nonlocal y
        if y < 48:
            pdf.showPage()
            header()
        pdf.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        pdf.drawString(margin + indent, y, _pdf_str(text_value))
        y -= 15

    header()
    cut = reconciliation["corte"]
    total = reconciliation["resumen"]
    line(f"Generado UTC: {report_time.isoformat()} | Responsable: {_pdf_str(username)}")
    line(f"Corte LDAP: #{cut['id']} | Extraído UTC: {cut['fecha_extraccion_utc'] or 'No disponible'}")
    line(f"Fuente RR. HH.: {_pdf_str(hr_reference)} | Archivo: {_pdf_str(hr_filename)}")
    line(f"SHA256 archivo RR. HH.: {hr_hash}", size=8)
    line(f"RR. HH.: {total['rrhh']} | Coincidencias: {total['coincidencias']} | Sin coincidencia: {total['sin_coincidencia']} | Ambiguos: {total['ambiguos']}", bold=True)
    line("ALCANCE: solo membresías RDP y Aplicaciones del corte LDAP. SASE no integrado.", bold=True, size=8)
    line("No implica baja automática ni aprobación corporativa; requiere revisión y evidencia de gestión.", size=8)
    y -= 9
    line("CUENTA RR. HH.                     RESULTADO                MEMBRESÍAS LDAP / ESTADO", bold=True, size=9)
    pdf.line(margin, y + 10, page_width - margin, y + 10)
    for i, row in enumerate(reconciliation["items"], 1):
        groups = ", ".join(f"{x['grupo']} ({'habilitada' if x['activo'] == 1 else 'deshabilitada' if x['activo'] == 0 else 'sin dato'})" for x in row["accesos"]) or "-"
        line(f"{i:>4}. {_pdf_str(row['cuenta_rrhh'])[:27]:<29} {_pdf_str(row['estado']):<23} {_pdf_str(groups)[:70]}", size=8)
    pdf.save()
    content = buf.getvalue()
    if not content.startswith(b"%PDF-") or len(content) > 15 * 1024 * 1024:
        raise RuntimeError("El informe PDF supera el límite de evidencia")
    return content


def save_reconciliation(db, *, cut_id, hr_filename, hr_content, hr_reference, anio, semestre, user):
    """Un informe PDF y su registro de auditoría o ningún cambio persistente."""
    if not 2020 <= int(anio) <= 2100 or int(semestre) not in (1, 2):
        raise ValueError("Período inválido")
    if not hr_reference or len(hr_reference.strip()) > 240:
        raise ValueError("Indica referencia/fecha del listado oficial de RR. HH.")
    accounts = parse_hr_file(hr_filename, hr_content)
    cut, rows = load_cut(db, cut_id)
    results = reconcile(cut, rows, accounts)
    digest = sha256(hr_content).hexdigest()
    # No guardar otra vez la misma conciliación de igual fuente/período/corte.
    exists = db.execute(text("""
        SELECT ID FROM AUTOM.SOX_C6_CONCILIACIONES
        WHERE CORTE_ID=:p_corte AND ANIO=:p_anio AND SEMESTRE=:p_semestre
          AND HASH_RRHH=:p_hash AND FUENTE_RRHH=:p_fuente
        FETCH FIRST 1 ROWS ONLY
    """), {"p_corte": int(cut_id), "p_anio": int(anio), "p_semestre": int(semestre),
           "p_hash": digest, "p_fuente": hr_reference.strip()}).first()
    if exists:
        raise ValueError(f"La conciliación ya está guardada (ID {int(exists[0])}); consulta el historial")
    timestamp = now_utc()
    pdf_data = generate_pdf(results, username=user.username, hr_reference=hr_reference,
                            hr_filename=hr_filename, report_time=timestamp, hr_hash=digest)
    root = _storage_root()
    key = uuid4().hex
    path = root / key
    filename = f"Control6_Conciliacion_Corte{cut_id}_{timestamp.strftime('%Y%m%d_%H%M%S')}.pdf"
    fd = None
    try:
        fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as stream:
            fd = None
            stream.write(pdf_data)
        ev_stmt = text("""
          INSERT INTO AUTOM.SOX_CONTROL_EVIDENCIAS
           (CONTROL_NUMERO, ANIO, SEMESTRE, TIPO_EVIDENCIA, REFERENCIA, OBSERVACIONES,
            NOMBRE_ARCHIVO, ARCHIVO_KEY, TAMANIO_BYTES, SHA256, ESTADO, CREADO_POR, CREADO_EN)
          VALUES (6,:p_anio,:p_semestre,'conciliacion',:p_referencia,:p_obs,
                  :p_nombre,:p_key,:p_size,:p_sha,'CARGADA',:p_user,:p_fecha)
          RETURNING ID INTO :p_returned
        """).bindparams(outparam("p_returned", Integer))
        response = db.execute(ev_stmt, {
            "p_anio": int(anio), "p_semestre": int(semestre),
            "p_referencia": f"LDAP corte #{cut_id}; RRHH: {hr_reference.strip()}"[:250],
            "p_obs": f"Conciliación generada por backend; {results['resumen']['coincidencias']} coincidencias; {results['resumen']['ambiguos']} ambiguos. Requiere revisión.",
            "p_nombre": filename, "p_key": key, "p_size": len(pdf_data), "p_sha": sha256(pdf_data).hexdigest(),
            "p_user": user.id, "p_fecha": timestamp,
        })
        ev_val = response.out_parameters["p_returned"]
        evidence_id = int(ev_val[0] if isinstance(ev_val, (tuple, list)) else ev_val)
        db.execute(text("""
            INSERT INTO AUTOM.SOX_CONTROL_EVIDENCIA_AUD
             (EVIDENCIA_ID, ACCION, USUARIO_ID, FECHA, DETALLE)
            VALUES (:p_evid,'CARGA',:p_user,:p_fecha,'Informe automático de conciliación Control 6')
        """), {"p_evid": evidence_id, "p_user": user.id, "p_fecha": timestamp})
        meta_stmt = text("""
            INSERT INTO AUTOM.SOX_C6_CONCILIACIONES
             (CORTE_ID,EVIDENCIA_ID,ANIO,SEMESTRE,FUENTE_RRHH,ARCHIVO_RRHH,HASH_RRHH,
              TOTAL_RRHH,COINCIDENCIAS,SIN_COINCIDENCIA,AMBIGUOS,CREADO_POR,CREADO_EN)
            VALUES (:p_corte,:p_evid,:p_anio,:p_sem,:p_fuente,:p_archivo,:p_hash,
                    :p_total,:p_coincide,:p_falta,:p_ambiguo,:p_user,:p_fecha)
            RETURNING ID INTO :p_returned
        """).bindparams(outparam("p_returned", Integer))
        response = db.execute(meta_stmt, {
            "p_corte": int(cut_id), "p_evid": evidence_id, "p_anio": int(anio), "p_sem": int(semestre),
            "p_fuente": hr_reference.strip(), "p_archivo": Path(hr_filename).name[:255], "p_hash": digest,
            "p_total": results["resumen"]["rrhh"], "p_coincide": results["resumen"]["coincidencias"],
            "p_falta": results["resumen"]["sin_coincidencia"], "p_ambiguo": results["resumen"]["ambiguos"],
            "p_user": user.id, "p_fecha": timestamp,
        })
        value = response.out_parameters["p_returned"]
        reconciliation_id = int(value[0] if isinstance(value, (tuple, list)) else value)
        db.commit()
        return {"conciliacion_id": reconciliation_id, "evidencia_id": evidence_id,
                "nombre_archivo": filename, "estado": "CARGADA", "corte_id": int(cut_id),
                "resumen": results["resumen"]}
    except Exception:
        db.rollback()
        path.unlink(missing_ok=True)
        raise
    finally:
        if fd is not None:
            os.close(fd)


def list_history(db, limit=30):
    rows = db.execute(text("""
      SELECT c.ID, c.CORTE_ID, c.EVIDENCIA_ID, c.ANIO, c.SEMESTRE, c.FUENTE_RRHH,
             c.TOTAL_RRHH, c.COINCIDENCIAS, c.SIN_COINCIDENCIA, c.AMBIGUOS,
             c.CREADO_EN, e.NOMBRE_ARCHIVO, e.ESTADO, u.USERNAME
      FROM AUTOM.SOX_C6_CONCILIACIONES c
      JOIN AUTOM.SOX_CONTROL_EVIDENCIAS e ON e.ID=c.EVIDENCIA_ID
      JOIN AUTOM.USUARIOS u ON u.ID=c.CREADO_POR
      ORDER BY c.ID DESC FETCH FIRST :p_limite ROWS ONLY
    """), {"p_limite": int(limit)}).all()
    return [{"id": int(r[0]), "corte_id": int(r[1]), "evidencia_id": int(r[2]),
             "anio": int(r[3]), "semestre": int(r[4]), "fuente_rrhh": r[5],
             "total_rrhh": int(r[6]), "coincidencias": int(r[7]), "sin_coincidencia": int(r[8]),
             "ambiguos": int(r[9]), "creado_en": r[10].isoformat() if r[10] else None,
             "archivo": r[11], "estado": r[12], "usuario": r[13]} for r in rows]
