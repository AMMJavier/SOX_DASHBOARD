"""Control 7 - VPN internas: listado de "gerentes" (jefe directo en AD) con VPN asignadas.

SOLO LECTURA: consulta el mismo LDAP y los mismos grupos que la carga de la campaña
(LDAP_VPN_RDP_CONECEL y LDAP_VPN_APLICACIONES_CONECEL), con la misma conexión del .env.
No escribe en Active Directory ni en Oracle.

Por cada responsable muestra su cargo (title) y departamento de AD, para distinguir
si es Gerente, Jefe, Coordinador, etc., y cuántas cuentas RDP / Aplicaciones tiene a cargo.

Uso (en el servidor, desde la carpeta backend):
    .venv/bin/python scripts/c7_gerentes_vpn_internas.py
    .venv/bin/python scripts/c7_gerentes_vpn_internas.py --no-gerentes        # solo cargos sin "gerente"
    .venv/bin/python scripts/c7_gerentes_vpn_internas.py --detalle dmedinac   # cuentas de ese responsable
    .venv/bin/python scripts/c7_gerentes_vpn_internas.py --csv /tmp/gerentes_internas.csv
"""
import argparse
import csv
import os
import sys
import unicodedata

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from ldap3 import BASE  # noqa: E402

from services.sox.control_6.ldap_access import (  # noqa: E402
    LDAP_GROUPS, _direct_users, _first, _group_dn, _integer, _open_connection,
)

SIN_JEFE = "(sin jefe en AD)"


def _plain(text):
    """Minúsculas y sin tildes, para buscar "gerente" en el cargo."""
    text = unicodedata.normalize("NFKD", str(text or ""))
    return "".join(c for c in text if not unicodedata.combining(c)).lower()


def _manager_info(conn, dn):
    """Usuario, nombre, cargo, departamento y correo del jefe a partir de su DN."""
    try:
        conn.search(search_base=dn, search_scope=BASE, search_filter="(objectClass=user)",
                    attributes=["sAMAccountName", "displayName", "title", "department", "mail"], size_limit=1)
    except Exception:
        return None
    if len(conn.entries) != 1:
        return None
    a = conn.entries[0].entry_attributes_as_dict
    get = lambda k: str(_first(a.get(k)) or "").strip()  # noqa: E731
    return {"usuario": get("sAMAccountName").lower() or dn, "nombre": get("displayName"),
            "cargo": get("title"), "departamento": get("department"), "correo": get("mail")}


def collect():
    """Recorre los dos grupos y agrupa las cuentas por jefe directo."""
    page_size = _integer("LDAP6_PAGE_SIZE", 200, 20, 1000)
    max_users = _integer("LDAP6_MAX_USERS_PER_GROUP", 5000, 100, 20000)
    conn, base = _open_connection()
    managers, people = {}, {}
    try:
        for access_type, group_name in LDAP_GROUPS.items():
            group_dn = _group_dn(conn, base, group_name)
            for info in _direct_users(conn, base, group_dn, page_size, max_users, with_manager=True).values():
                dn = info.get("manager_dn")
                if dn and dn not in people:
                    people[dn] = _manager_info(conn, dn)
                boss = people.get(dn) if dn else None
                key = boss["usuario"] if boss else SIN_JEFE
                item = managers.setdefault(key, {
                    "usuario": key, "nombre": (boss or {}).get("nombre", ""), "cargo": (boss or {}).get("cargo", ""),
                    "departamento": (boss or {}).get("departamento", ""), "correo": (boss or {}).get("correo", ""),
                    "RDP": 0, "APLICACIONES": 0, "cuentas": []})
                item[access_type] += 1
                item["cuentas"].append((info["usuario"], info.get("nombre") or "", access_type,
                                        "activa" if info.get("activo") else "deshabilitada" if info.get("activo") is False else "-"))
    finally:
        try:
            conn.unbind()
        except Exception:
            pass
    for item in managers.values():
        item["total"] = item["RDP"] + item["APLICACIONES"]
        item["es_gerente"] = "gerente" in _plain(item["cargo"])
    return sorted(managers.values(), key=lambda m: (-m["total"], m["usuario"]))


def _cut(text, size):
    text = str(text or "-")
    return text if len(text) <= size else text[:size - 1] + "…"


def main():
    parser = argparse.ArgumentParser(description="Responsables (jefe directo en AD) de las VPN internas del Control 7")
    parser.add_argument("--no-gerentes", action="store_true", help="solo responsables cuyo cargo NO contiene 'gerente'")
    parser.add_argument("--detalle", metavar="USUARIO", help="lista las cuentas a cargo de ese responsable")
    parser.add_argument("--csv", metavar="RUTA", help="además guarda el listado en un CSV")
    args = parser.parse_args()

    rows = collect()
    if args.detalle:
        wanted = args.detalle.strip().lower()
        match = next((m for m in rows if m["usuario"] == wanted), None)
        if not match:
            sys.exit(f"{wanted} no figura como responsable de VPN internas")
        print(f"{match['usuario']} - {match['nombre']} | cargo: {match['cargo'] or '-'} | depto: {match['departamento'] or '-'}")
        print(f"RDP: {match['RDP']}  Aplicaciones: {match['APLICACIONES']}  Total: {match['total']}\n")
        print(f"{'CUENTA':<18} {'NOMBRE':<38} {'ACCESO':<13} ESTADO AD")
        for cuenta, nombre, tipo, estado in sorted(match["cuentas"]):
            print(f"{cuenta:<18} {_cut(nombre, 38):<38} {tipo:<13} {estado}")
        return

    shown = [m for m in rows if not (args.no_gerentes and m["es_gerente"])]
    print(f"{'#':>3} {'USUARIO':<16} {'NOMBRE':<32} {'CARGO (AD)':<40} {'GER':<3} {'RDP':>5} {'APLIC':>5} {'TOTAL':>5}")
    print("-" * 116)
    for n, m in enumerate(shown, 1):
        print(f"{n:>3} {_cut(m['usuario'], 16):<16} {_cut(m['nombre'], 32):<32} {_cut(m['cargo'], 40):<40} "
              f"{'SI' if m['es_gerente'] else 'NO':<3} {m['RDP']:>5} {m['APLICACIONES']:>5} {m['total']:>5}")
    print("-" * 116)
    gerentes = sum(1 for m in rows if m["es_gerente"])
    print(f"Responsables: {len(rows)} | con cargo 'Gerente': {gerentes} | otros cargos (jefe, coordinador...): "
          f"{len(rows) - gerentes} | accesos: {sum(m['total'] for m in rows)}")

    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8-sig") as fh:
            writer = csv.writer(fh, delimiter=";")
            writer.writerow(["usuario", "nombre", "cargo", "departamento", "correo", "es_gerente", "rdp", "aplicaciones", "total"])
            for m in shown:
                writer.writerow([m["usuario"], m["nombre"], m["cargo"], m["departamento"], m["correo"],
                                 "SI" if m["es_gerente"] else "NO", m["RDP"], m["APLICACIONES"], m["total"]])
        print(f"CSV guardado en {args.csv}")


if __name__ == "__main__":
    main()
