"""Copia el inventario de Assets (y su historial) de Oracle a PostgreSQL.

Uso (desde la carpeta backend, con ORACLE_* y POSTGRES_* en backend/.env):

    python scripts/migrar_assets_oracle_a_postgres.py --dry-run     # solo cuenta filas
    python scripts/migrar_assets_oracle_a_postgres.py               # copia (tablas destino vacías)
    python scripts/migrar_assets_oracle_a_postgres.py --truncate    # vacía destino y vuelve a copiar

Requisitos previos:
  * Haber ejecutado sql/postgres/assets_schema.sql en la base destino.
  * El usuario de Postgres debe ser dueño de las tablas (para desactivar el
    trigger de auditoría durante la copia y no duplicar el historial).

Conserva los ID originales de Oracle (dispositivos y log) y al final ajusta
las secuencias IDENTITY para que los nuevos registros continúen después.
"""
import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import URL, create_engine, text  # noqa: E402

from database.assets_database import get_assets_engine  # noqa: E402
from database.oracle_settings import get_oracle_config  # noqa: E402

BATCH = 1000

INVENTORY_COLUMNS = [
    "id", "especialidad", "plataforma", "tipo", "dispositivo", "estado", "criticidad",
    "infraestructura", "ip", "mask", "gateway", "mac", "localidad", "piso", "lado", "ciudad",
    "so", "version", "firmware", "fabricante", "modelo", "serial", "licencia", "eos", "comentario",
]
LOG_COLUMNS = [
    "log_id", "dispositivo_id", "fecha_cambio", "usuario", "operacion",
    "campo_modificado", "valor_anterior", "valor_nuevo", "origen",
]
TABLES = [
    # (tabla Oracle, tabla Postgres, columnas, columna clave)
    ("AUTOM.INVENTARIO_DISPOSITIVOS", "inventario_dispositivos", INVENTORY_COLUMNS, "id"),
    ("AUTOM.INVENTARIO_DISPOSITIVOS_LOG", "inventario_dispositivos_log", LOG_COLUMNS, "log_id"),
]


def oracle_engine():
    cfg = get_oracle_config()
    return create_engine(URL.create(
        "oracle+oracledb", username=cfg["user"], password=cfg["password"],
        host=cfg["host"], port=cfg["port"], query={"service_name": cfg["service_name"]},
    ))


def _clean(row: dict) -> dict:
    result = {}
    for key, value in row.items():
        key = str(key).lower()
        if hasattr(value, "read"):  # CLOB
            value = value.read()
        if key == "eos" and isinstance(value, datetime):
            value = value.date()
        result[key] = value
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="Solo muestra cuántas filas se copiarían.")
    parser.add_argument("--truncate", action="store_true", help="Vacía las tablas destino antes de copiar.")
    args = parser.parse_args()

    src = oracle_engine()
    dst = get_assets_engine()

    with src.connect() as ora:
        counts = {o: ora.execute(text(f"SELECT COUNT(*) FROM {o}")).scalar() for o, *_ in TABLES}
    for (o, p, *_), n in zip(TABLES, counts.values()):
        print(f"Oracle {o}: {n} filas  ->  Postgres {p}")
    if args.dry_run:
        print("Dry run: no se copió nada.")
        return 0

    with dst.begin() as pg:
        for _, p, *_ in TABLES:
            existing = pg.execute(text(f"SELECT COUNT(*) FROM {p}")).scalar()
            if existing and not args.truncate:
                print(f"ERROR: {p} ya tiene {existing} filas. Usa --truncate para reemplazarlas.")
                return 1
        if args.truncate:
            pg.execute(text("TRUNCATE inventario_dispositivos, inventario_dispositivos_log"))

        # Sin trigger durante la copia: el historial se trae tal cual desde Oracle.
        # Todo ocurre en una sola transacción: si algo falla, Postgres revierte
        # la copia y también el DISABLE TRIGGER (el DDL es transaccional).
        pg.execute(text("ALTER TABLE inventario_dispositivos DISABLE TRIGGER trg_inventario_dispositivos_audit"))
        with src.connect() as ora:
            for o, p, cols, key in TABLES:
                insert = text(
                    f"INSERT INTO {p} ({', '.join(cols)}) "
                    f"OVERRIDING SYSTEM VALUE VALUES ({', '.join(':' + c for c in cols)})"
                )
                result = ora.execution_options(stream_results=True).execute(
                    text(f"SELECT {', '.join(cols)} FROM {o} ORDER BY {key}")
                ).mappings()
                copied = 0
                while True:
                    chunk = result.fetchmany(BATCH)
                    if not chunk:
                        break
                    pg.execute(insert, [_clean(dict(r)) for r in chunk])
                    copied += len(chunk)
                    print(f"  {p}: {copied} filas copiadas", end="\r")
                print(f"  {p}: {copied} filas copiadas")

                pg.execute(text(
                    f"SELECT setval(pg_get_serial_sequence('{p}', '{key}'), "
                    f"COALESCE((SELECT MAX({key}) FROM {p}), 0) + 1, false)"
                ))
        pg.execute(text("ALTER TABLE inventario_dispositivos ENABLE TRIGGER trg_inventario_dispositivos_audit"))

    print("Migración completada.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
