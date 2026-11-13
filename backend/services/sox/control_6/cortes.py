"""Cortes de acceso interno LDAP para Control 6 (Oracle).

Sin escrituras LDAP: guarda una instantánea recibida de la consulta directa al directorio.
Los dos grupos se guardan por separado para preservar membresías compartidas.
"""
from __future__ import annotations

from datetime import datetime, timezone
import re

GROUPS = ("RDP", "APLICACIONES")
MAX_MEMBERSHIPS = 15000


def canonical_account(value):
    account = str(value or "").strip().lower()
    if account.startswith("porta\\"):
        account = account[6:]
    if account.endswith("@porta.corp"):
        account = account[:-11]
    if not account or len(account) > 100 or not re.fullmatch(r"[a-z0-9._$-]+", account):
        raise ValueError("Cuenta LDAP no válida (no se guardaron registros)")
    return account


def normalize_memberships(rows):
    """Validar el corte completo antes de abrir una transacción Oracle."""
    combined = {}
    for row in rows:
        key = canonical_account(row.get("usuario"))
        group = str(row.get("tipo_acceso") or "").strip().upper()
        if group not in GROUPS:
            raise ValueError("Tipo de acceso no válido; se esperan RDP y APLICACIONES")
        name = str(row.get("nombre") or "").strip()[:200] or None
        active = row.get("activo")
        if active not in (None, 0, 1, True, False):
            raise ValueError("Estado activo incorrecto en el corte")
        item = (key, group)
        if item not in combined:
            combined[item] = {"usuario": key, "tipo_acceso": group,
                              "nombre": name, "activo": None if active is None else int(active)}
        elif not combined[item]["nombre"] and name:
            combined[item]["nombre"] = name
        if len(combined) > MAX_MEMBERSHIPS:
            raise ValueError("El corte supera el límite de membresías previsto")
    if not combined or {x[1] for x in combined} != set(GROUPS):
        raise ValueError("Se necesitan ambas fuentes RDP y APLICACIONES; no se guardó corte parcial")
    members = list(combined.values())
    counts = {group: sum(r["tipo_acceso"] == group for r in members) for group in GROUPS}
    return members, counts, len({r["usuario"] for r in members})


def store_cut(rows, source, actor_id=None, extracted_at=None):
    if source != "LDAP_EN_VIVO":
        raise ValueError("Fuente de corte inválida")
    members, counts, unique = normalize_memberships(rows)
    if extracted_at is not None:
        if not isinstance(extracted_at, datetime):
            raise ValueError("Fecha de extracción inválida")
        if extracted_at.tzinfo is not None:
            extracted_at = extracted_at.astimezone(timezone.utc).replace(tzinfo=None)
    from database.oracle_connection import OracleConnection
    oracle = OracleConnection()
    connection = None
    try:
        connection = oracle.connect()
        cursor = connection.cursor()
        import oracledb
        output_id = cursor.var(oracledb.DB_TYPE_NUMBER)
        cursor.execute("""
            INSERT INTO AUTOM.SOX_C6_CORTES_LDAP
              (FUENTE,TOTAL_RDP,TOTAL_APLICACIONES,TOTAL_CUENTAS,CAPTURADO_POR,FECHA_EXTRACCION_UTC)
            VALUES (:fuente,:rdp,:aplicaciones,:unicos,:actor,:extracted_at)
            RETURNING ID INTO :out_id
        """, {"fuente": source, "rdp": counts["RDP"], "aplicaciones": counts["APLICACIONES"],
              "unicos": unique, "actor": actor_id, "extracted_at": extracted_at, "out_id": output_id})
        cut_id = int(output_id.getvalue()[0])
        cursor.executemany("""
            INSERT INTO AUTOM.SOX_C6_ACCESOS_LDAP
              (CORTE_ID,USUARIO,NOMBRE,ACTIVO,TIPO_ACCESO)
            VALUES (:corte,:usuario,:nombre,:activo,:tipo)
        """, [dict(corte=cut_id, usuario=m["usuario"], nombre=m["nombre"],
                   activo=m["activo"], tipo=m["tipo_acceso"]) for m in members])
        connection.commit()
        return {"corte_id": cut_id, "fuente": source, "RDP": counts["RDP"],
                "APLICACIONES": counts["APLICACIONES"], "cuentas_unicas": unique}
    except Exception:
        if connection:
            connection.rollback()
        raise
    finally:
        oracle.close()


def _summary(row):
    return {"id": int(row[0]), "fecha_registro_utc": row[1].isoformat() if row[1] else None,
            "fecha_extraccion_utc": row[2].isoformat() if row[2] else None,
            "fuente": row[3], "rdp": int(row[4]), "aplicaciones": int(row[5]),
            "cuentas_unicas": int(row[6])}


def latest_cut():
    from database.oracle_connection import OracleConnection
    oracle = OracleConnection()
    try:
        c = oracle.connect().cursor()
        c.execute("""
            SELECT ID, FECHA_REGISTRO_UTC, FECHA_EXTRACCION_UTC, FUENTE, TOTAL_RDP,
                   TOTAL_APLICACIONES, TOTAL_CUENTAS
              FROM AUTOM.SOX_C6_CORTES_LDAP ORDER BY ID DESC
              FETCH FIRST 1 ROW ONLY
        """)
        row = c.fetchone()
        return _summary(row) if row else None
    finally:
        oracle.close()


def cut_accounts(cut_id, offset=0, limit=50, search="", access=""):
    if not 1 <= int(limit) <= 200 or not 0 <= int(offset) <= 100000:
        raise ValueError("Límite o desplazamiento no válido")
    if access and access not in GROUPS:
        raise ValueError("Filtro de grupo inválido")
    if len(search) > 100:
        raise ValueError("Búsqueda demasiado larga")
    from database.oracle_connection import OracleConnection
    oracle = OracleConnection()
    try:
        cur = oracle.connect().cursor()
        cur.execute("""
            SELECT ID, FECHA_REGISTRO_UTC, FECHA_EXTRACCION_UTC, FUENTE, TOTAL_RDP,
                   TOTAL_APLICACIONES, TOTAL_CUENTAS
              FROM AUTOM.SOX_C6_CORTES_LDAP WHERE ID=:id
        """, {"id": int(cut_id)})
        row = cur.fetchone()
        if row is None:
            return None
        meta = _summary(row)
        # Solo lectura. Nombres de bind que NO son palabras reservadas de Oracle.
        # Agregar filtros únicamente cuando se solicitan evita binds NULL ambiguos.
        params = {"p_corte_id": int(cut_id)}
        conditions = ["CORTE_ID = :p_corte_id"]
        if access:
            conditions.append("TIPO_ACCESO = :p_tipo_acceso")
            params["p_tipo_acceso"] = access
        term = search.strip().lower()
        if term:
            conditions.append("(LOWER(USUARIO) LIKE :p_busqueda OR LOWER(NOMBRE) LIKE :p_busqueda)")
            params["p_busqueda"] = f"%{term}%"
        where = " WHERE " + " AND ".join(conditions)
        cur.execute("SELECT COUNT(*) FROM AUTOM.SOX_C6_ACCESOS_LDAP" + where, params)
        total = int(cur.fetchone()[0])
        cur.execute("""
            SELECT USUARIO, NOMBRE, ACTIVO, TIPO_ACCESO
              FROM AUTOM.SOX_C6_ACCESOS_LDAP
        """ + where + " ORDER BY USUARIO, TIPO_ACCESO OFFSET :p_inicio ROWS FETCH NEXT :p_cantidad ROWS ONLY",
                    {**params, "p_inicio": int(offset), "p_cantidad": int(limit)})
        items = [{"usuario": r[0], "nombre": r[1],
                  "activo": None if r[2] is None else bool(r[2]),
                  "tipo_acceso": r[3]} for r in cur.fetchall()]
        return {"corte": meta, "total": total, "offset": int(offset), "limit": int(limit), "items": items}
    finally:
        oracle.close()


def from_live_report(report):
    # Exige inventario completo de ambos grupos; el fallo de LDAP nunca sustituye el último corte.
    if not set(GROUPS).issubset((report.get("fuentes") or {}).keys()):
        raise ValueError("Falta uno de los grupos LDAP")
    if (report.get("fuentes") or {}).get("RDP", 0) <= 0 or (report.get("fuentes") or {}).get("APLICACIONES", 0) <= 0:
        raise ValueError("Algún grupo LDAP devolvió cero miembros; revisar antes de guardar")
    records = []
    for user in report.get("usuarios") or []:
        for group in user.get("fuentes") or []:
            records.append({"usuario": user.get("usuario"), "nombre": user.get("nombre"),
                            "activo": user.get("activo"), "tipo_acceso": group})
    members, counts, _ = normalize_memberships(records)
    for group in GROUPS:
        if counts[group] != report["fuentes"][group]:
            raise ValueError("Conteos LDAP incompletos; corte descartado")
    return members
