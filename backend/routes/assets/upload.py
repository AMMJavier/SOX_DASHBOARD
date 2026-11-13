from datetime import date, datetime
import re
from typing import Any, Dict, List
import csv, io

from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Form
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from database.assets_database import get_assets_db, set_audit_context
from auth.dependencies import get_current_user
from models import Usuario


router = APIRouter()

# Columnas admitidas y longitud máxima (VARCHAR en sql/postgres/assets_schema.sql)
TEXT_COLUMNS = {
    "especialidad": 50,
    "plataforma": 50,
    "tipo": 50,
    "dispositivo": 100,
    "estado": 30,
    "criticidad": 20,
    "infraestructura": 30,
    "ip": 255,
    "mask": 15,
    "gateway": 15,
    "mac": 17,
    "localidad": 100,
    "piso": 20,
    "lado": 20,
    "ciudad": 100,
    "so": 255,
    "version": 30,
    "firmware": 50,
    "fabricante": 100,
    "modelo": 50,
    "serial": 50,
    "licencia": 500,
    "comentario": 500,
}

REQUIRED_COLUMNS = set()  # Sin campos obligatorios temporalmente

ALLOWED_COLUMNS = set(TEXT_COLUMNS) | {"eos"}

# Identificadores genéricos que no representan un equipo físico.
INVALID_SERIALS = {
    "N/A", "NA", "S/N", "SIN SERIAL",
    "UNKNOWN", "0", "NULL"
}

# Meses aceptados en español e inglés.
MONTHS = {
    "ene": 1, "jan": 1,
    "feb": 2,
    "mar": 3,
    "abr": 4, "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "ago": 8, "aug": 8,
    "sep": 9, "set": 9,
    "oct": 10,
    "nov": 11,
    "dic": 12, "dec": 12,
}


def normalize_eos(value):
    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    value = str(value).strip().lower()

    # Fechas con meses escritos: 21-jul-25, 07-abr-2029
    match = re.fullmatch(
        r"(\d{1,2})[-/](\w{3})[-/](\d{2}|\d{4})",
        value
    )

    if match:
        day, month_text, year = match.groups()

        if month_text not in MONTHS:
            raise ValueError(f"Mes EOS no reconocido: {month_text}")

        year = int(year)

        if year < 100:
            year += 2000

        try:
            return date(year, MONTHS[month_text], int(day))
        except ValueError:
            raise ValueError(f"Fecha EOS inválida: {value}")

    # Fechas numéricas.
    formats = (
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%d-%m-%y",
        "%d/%m/%y",
        "%Y-%m-%dT%H:%M:%S",
    )

    for fmt in formats:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue

    raise ValueError(f"Formato EOS no reconocido: {value}")


def save_inventory_items(db: Session, rows: List[Dict[str, Any]]):
    """
    Inserta equipos nuevos o actualiza únicamente los campos
    modificados de equipos existentes.

    La coincidencia se realiza mediante fabricante + serial.
    Las operaciones se confirman juntas desde el endpoint.
    """

    counters = {
        "insertados": 0,
        "actualizados": 0,
        "sin_cambios": 0,
    }

    for row in rows:
        # No fusionar equipos sin una identidad confiable.
        # En esos casos cada fila se inserta como un activo independiente.
        fabricante = str(row.get("fabricante") or "-").strip()
        serial = str(row.get("serial") or "-").strip()
        # Valores provisionales no identifican un activo de forma única.
        invalid_identity_values = INVALID_SERIALS | {"", "-"}
        identity_valid = (
            fabricante.upper() not in invalid_identity_values
            and serial.upper() not in invalid_identity_values
        )
        existing = None
        if identity_valid:
            existing = db.execute(
                text("""
                    SELECT * FROM inventario_dispositivos
                    WHERE UPPER(TRIM(FABRICANTE)) = :fabricante
                      AND UPPER(TRIM(SERIAL)) = :serial
                    FOR UPDATE
                """),
                {"fabricante": fabricante.upper(), "serial": serial.upper()},
            ).mappings().first()

        # Normalizar los nombres de columnas devueltos por SQLAlchemy.
        if existing is not None:
            existing = {
                str(key).lower(): value
                for key, value in existing.items()
            }

        if existing is None:
            # Los campos de texto vacíos se guardan como NULL (validate_row).
            # EOS mantiene la fecha provisional porque la columna es DATE NOT NULL.
            row = {**{column: None for column in TEXT_COLUMNS}, "eos": EOS_SIN_DEFINIR, **row}
            columns = list(row.keys())

            statement = text(f"""
                INSERT INTO inventario_dispositivos
                ({", ".join(columns)})
                VALUES ({", ".join(":" + c for c in columns)})
            """)

            db.execute(statement, row)
            counters["insertados"] += 1
            continue

        # Compara únicamente las columnas presentes en el archivo.
        changes = {}

        for column, new_value in row.items():
            # No sobrescribir datos existentes ni generar auditoría por guiones,
            # vacíos o EOS provisional provenientes del CSV/formulario.
            if new_value is None or (column == "eos" and new_value == EOS_SIN_DEFINIR):
                continue
            old_value = existing[column]

            # Por compatibilidad, normalizar si la fecha llega como datetime.
            if column == "eos" and isinstance(old_value, datetime):
                old_value = old_value.date()

            # Espacios externos no constituyen una modificación real.
            if isinstance(old_value, str) and isinstance(new_value, str):
                if old_value.strip() == new_value.strip():
                    continue
            if old_value != new_value:
                changes[column] = new_value

        if not changes:
            counters["sin_cambios"] += 1
            continue

        assignments = ", ".join(
            f"{column} = :upd_{column}"
            for column in changes
        )

        parameters = {
            f"upd_{column}": value
            for column, value in changes.items()
        }
        parameters["device_id"] = existing["id"]

        db.execute(
            text(f"""
                UPDATE inventario_dispositivos
                SET {assignments}
                WHERE ID = :device_id
            """),
            parameters,
        )

        counters["actualizados"] += 1

    return counters

class UploadRequest(BaseModel):
    items: List[Dict[str, Any]]


# Fecha de referencia para EOS no informado; la columna EOS es DATE NOT NULL.
EOS_SIN_DEFINIR = date(2099, 12, 31)


def validate_row(raw_row):
    cleaned = {}
    ignored = []

    for original_key, value in raw_row.items():
        key = str(original_key).strip().lower()
        if key not in ALLOWED_COLUMNS:
            ignored.append(str(original_key))
            continue

        # Un guion es un marcador de campo vacío, nunca un valor de inventario.
        # Aplica tanto para archivos CSV como para edición manual/PATCH.
        raw_text = "" if value is None else str(value).strip()
        if not raw_text or raw_text in {"-", "–", "—"}:
            cleaned[key] = EOS_SIN_DEFINIR if key == "eos" else None
            continue

        if key == "eos":
            cleaned[key] = normalize_eos(value)
            continue

        if not isinstance(value, str):
            value = str(value)
        value = value.strip()

        if key == "serial":
            value = value.upper()
        elif key == "fabricante":
            value = value.title()
        elif key == "estado":
            estados = {
                "activo/vigente": "Activo/Vigente",
                "inactivo/no vigente": "Inactivo/No Vigente",
                "averiado": "Averiado",
            }
            value = estados.get(value.casefold(), value.title())
        elif key in (
            "especialidad", "plataforma", "tipo", "criticidad",
            "infraestructura", "ciudad", "localidad",
        ):
            # Quitar espacios no significativos para uniformizar ciudades/localidades.
            value = re.sub(r"\s+", " ", value).title()

        if key == "mask":
            value = value.replace("$", ".")
        if key == "dispositivo":
            value = " ".join(value.splitlines()).strip()

        # "CAC" es una sigla corporativa: no convertirla a "Cac" al
        # normalizar ciudades, localidades o campos importados desde Excel.
        value = re.sub(r"\bCAC\b", "CAC", value, flags=re.IGNORECASE)

        if len(value) > TEXT_COLUMNS[key]:
            raise ValueError(
                f"'{key}' supera los {TEXT_COLUMNS[key]} caracteres"
            )
        cleaned[key] = value

    return cleaned, ignored


@router.post("/upload/manual")
def upload_manual(
    payload: UploadRequest,
    db: Session = Depends(get_assets_db),
    current: Usuario = Depends(get_current_user),
):
    if not payload.items:
        raise HTTPException(
            status_code=400,
            detail="Debe enviar al menos un dispositivo.",
        )

    if len(payload.items) > 500:
        raise HTTPException(
            status_code=400,
            detail="Máximo 500 registros por solicitud.",
        )

    validated = []
    errors = []
    ignored_columns = set()

    # Validar todo antes de insertar
    for index, row in enumerate(payload.items, start=1):
        try:
            cleaned, ignored = validate_row(row)
            validated.append(cleaned)
            ignored_columns.update(ignored)
        except ValueError as exc:
            errors.append({
                "fila": index,
                "error": str(exc),
            })

    if errors:
        raise HTTPException(
            status_code=422,
            detail={
                "mensaje": "Existen registros inválidos.",
                "errores": errors,
                "insertados": 0,
            },
        )

    try:
        set_audit_context(db, current.username, "CARGA_MANUAL")
        counters = save_inventory_items(db, validated)
        db.commit()

        return {
            "mensaje": "Carga completada correctamente.",
            **counters,
            "columnas_ignoradas": sorted(ignored_columns),
            "total_procesados": len(validated),
        }
    
    except SQLAlchemyError as exc:
            db.rollback()
    
            raise HTTPException(
                status_code=500,
                detail="No fue posible completar la importación.",
            ) from exc

# ============================================================
# PREVISUALIZACIÓN DE ARCHIVOS CSV
# POST /assets/upload/preview
# ============================================================

MAX_CSV_SIZE = 5 * 1024 * 1024
MAX_CSV_ROWS = 500


@router.post("/upload/preview")
async def preview_csv(
    file: UploadFile = File(...),
    delimiter: str = Form("auto"),
):
    filename = file.filename or ""

    if not filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=400,
            detail="Solo se permiten archivos CSV.",
        )

    try:
        content = await file.read(MAX_CSV_SIZE + 1)

        if len(content) > MAX_CSV_SIZE:
            raise HTTPException(
                status_code=413,
                detail="El archivo supera el límite de 5 MB.",
            )

        try:
            decoded = content.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise HTTPException(
                status_code=400,
                detail="El archivo debe estar codificado en UTF-8.",
            )

        allowed_delimiters = {"$", ",", ";", "\t", "|"}
        if delimiter == "tab":
            delimiter = "\t"
        if delimiter != "auto" and delimiter not in allowed_delimiters:
            raise HTTPException(status_code=400, detail="Delimitador CSV no permitido.")

        if delimiter == "auto":
            sample = decoded[:16384]
            try:
                detected = csv.Sniffer().sniff(sample, delimiters="$;,|\t")
                delimiter = detected.delimiter
            except csv.Error:
                # Fallback: encabezados conocidos, sin dividir campos entrecomillados.
                header = next(csv.reader(io.StringIO(decoded)), [])
                candidates = []
                for candidate in ("$", ",", ";", "\t", "|"):
                    cells = next(csv.reader(io.StringIO(decoded), delimiter=candidate), [])
                    matches = sum(cell.strip().lower() in ALLOWED_COLUMNS for cell in cells)
                    candidates.append((matches, candidate))
                best = max(candidates, key=lambda x: x[0])
                if best[0] < 2:
                    raise HTTPException(status_code=400, detail="No se pudo detectar el delimitador. Selecciónalo manualmente.")
                delimiter = best[1]

        # Excel suele exportar columnas sin nombre y totalmente vacías al final.
        # Solo se descartan si NINGUNA fila contiene datos en esas posiciones.
        parsed_rows = list(csv.reader(
            io.StringIO(decoded), delimiter=delimiter, quotechar='"', strict=True
        ))
        if not parsed_rows:
            raise HTTPException(status_code=400, detail="El CSV no contiene encabezados.")
        headers = parsed_rows[0]
        keep_columns = len(headers)
        while keep_columns > 0 and not str(headers[keep_columns - 1]).strip():
            index = keep_columns - 1
            if any(len(row) > index and str(row[index]).strip() for row in parsed_rows[1:]):
                break
            keep_columns -= 1
        empty_columns_removed = len(headers) - keep_columns
        if empty_columns_removed:
            if any(any(str(v).strip() for v in row[keep_columns:]) for row in parsed_rows[1:]):
                raise HTTPException(status_code=400, detail="Existen columnas sin encabezado que contienen datos.")
            rebuilt = io.StringIO()
            writer = csv.writer(rebuilt, delimiter=delimiter, quotechar='"', lineterminator="\n")
            for row in parsed_rows:
                writer.writerow(row[:keep_columns])
            decoded_for_reader = rebuilt.getvalue()
        else:
            decoded_for_reader = decoded

        reader = csv.DictReader(
            io.StringIO(decoded_for_reader), delimiter=delimiter, quotechar='"', strict=True
        )

        if not reader.fieldnames:
            raise HTTPException(
                status_code=400,
                detail="El CSV no contiene encabezados.",
            )

        original_columns = [
            str(column).strip()
            for column in reader.fieldnames
            if column is not None
        ]

        normalized_columns = [
            column.lower()
            for column in original_columns
        ]

        if len(normalized_columns) != len(set(normalized_columns)):
            duplicates = sorted({name for name in normalized_columns if normalized_columns.count(name) > 1})
            raise HTTPException(
                status_code=400,
                detail="El CSV contiene columnas duplicadas: " + ", ".join(name or "(vacía)" for name in duplicates),
            )

        valid_columns = [
            column
            for column in original_columns
            if column.lower() in ALLOWED_COLUMNS
        ]

        ignored_columns = [
            column
            for column in original_columns
            if column.lower() not in ALLOWED_COLUMNS
        ]

        records = []
        errors = []

        for index, raw_row in enumerate(reader, start=2):

            if index > MAX_CSV_ROWS + 1:
                raise HTTPException(
                    status_code=400,
                    detail="El CSV supera el máximo de 500 filas.",
                )

            if None in raw_row:
                errors.append({
                    "fila": index,
                    "error": "La fila contiene más valores que encabezados.",
                })
                continue

            if any(value is None for value in raw_row.values()):
                errors.append({
                    "fila": index,
                    "error": (
                        "La fila tiene menos columnas que el encabezado. "
                        "Verifica el delimitador y las comillas del CSV."
                    ),
                })
                continue

            if all(
                value is None or not str(value).strip()
                for value in raw_row.values()
            ):
                continue

            try:
                cleaned, _ = validate_row(raw_row)

                # Convertir fechas para que el JSON sea serializable.
                serialized = {
                    key: (
                        value.isoformat()
                        if isinstance(value, (date, datetime))
                        else value
                    )
                    for key, value in cleaned.items()
                }

                records.append({
                    "fila": index,
                    "datos": serialized,
                })

            except ValueError as exc:
                errors.append({
                    "fila": index,
                    "error": str(exc),
                })

        identities = {}
        repeated_identities = []
        missing_serial = 0
        bad_identity = INVALID_SERIALS | {"", "-"}
        for record in records:
            data = record["datos"]
            serial = str(data.get("serial") or "").strip().upper()
            fabricante = str(data.get("fabricante") or "").strip().upper()
            if serial in bad_identity:
                missing_serial += 1
            if serial not in bad_identity and fabricante not in bad_identity:
                identity = (fabricante, serial)
                if identity in identities:
                    repeated_identities.append({
                        "fila_primera": identities[identity],
                        "fila_repetida": record["fila"],
                        "fabricante": fabricante,
                        "serial": serial,
                    })
                else:
                    identities[identity] = record["fila"]

        return {
            "archivo": filename,
            "columnas_vacias_omitidas": empty_columns_removed,
            "sin_serial_valido": missing_serial,
            "identidades_repetidas": repeated_identities,
            "delimitador_detectado": "TAB" if delimiter == "\t" else delimiter,
            "columnas_validas": valid_columns,
            "columnas_ignoradas": ignored_columns,
            "total_validos": len(records),
            "total_errores": len(errors),
            "registros_validos": records,
            "errores": errors,
        }

    except csv.Error as exc:
        raise HTTPException(
            status_code=400,
            detail="El archivo CSV contiene un formato inválido.",
        ) from exc

    finally:
        await file.close()

# ============================================================
# CONFIRMAR IMPORTACIÓN CSV
# POST /assets/upload/confirm
# ============================================================

@router.post("/upload/confirm")
def confirm_csv(
    payload: UploadRequest,
    db: Session = Depends(get_assets_db),
    current: Usuario = Depends(get_current_user),
):
    if not payload.items:
        raise HTTPException(
            status_code=400,
            detail="No existen registros para importar.",
        )

    if len(payload.items) > MAX_CSV_ROWS:
        raise HTTPException(
            status_code=400,
            detail="Máximo 500 registros por importación.",
        )

    validated = []
    errors = []
    ignored_columns = set()

    for index, row in enumerate(payload.items, start=1):
        try:
            cleaned, ignored = validate_row(row)
            validated.append(cleaned)
            ignored_columns.update(ignored)

        except ValueError as exc:
            errors.append({
                "fila": index,
                "error": str(exc),
            })

    if errors:
        raise HTTPException(
            status_code=422,
            detail={
                "mensaje": "La importación contiene registros inválidos.",
                "insertados": 0,
                "errores": errors,
            },
        )

    try:
        set_audit_context(db, current.username, "CARGA_CSV")
        counters = save_inventory_items(db, validated)

        db.commit()

        return{
            "mensaje": "Importación completada correctamente.",
            **counters,
            "columnas_ignoradas": sorted(ignored_columns),
            "total_procesados": len(validated),
        }

    except Exception as exc:
            db.rollback()
    
            import traceback
    
            print("\n========== ERROR CONFIRM CSV ==========", flush=True)
            traceback.print_exc()
            print("=======================================\n", flush=True)
    
            raise HTTPException(
                status_code=500,
                detail="No fue posible completar la importación.",
            ) from exc
