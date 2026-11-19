"""Control 7 - VPN internas: listado de GERENTES responsables de las VPN internas.

SOLO LECTURA: consulta el mismo LDAP y los mismos grupos que la carga de la campaña
(LDAP_VPN_RDP_CONECEL y LDAP_VPN_APLICACIONES_CONECEL), con la misma conexión del .env (LDAP7_*).
No escribe en Active Directory ni en Oracle.

Aplica la MISMA regla que la plataforma (services/sox/control_7/ldap_vpn.py): por cada
cuenta sube por la cadena de jefes de AD ("manager") hasta el primer cargo que empieza con
"Gerente". El jefe directo (jefe, coordinador...) solo se muestra en --detalle.

Uso (en el servidor, desde la carpeta backend):
    .venv/bin/python scripts/c7_gerentes_vpn_internas.py
    .venv/bin/python scripts/c7_gerentes_vpn_internas.py --detalle janton     # cuentas de ese gerente
    .venv/bin/python scripts/c7_gerentes_vpn_internas.py --csv /tmp/gerentes_internas.csv
"""
import argparse
import csv
import os
import sys

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BACKEND)

from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(BACKEND, ".env"))

from services.sox.control_7.ldap_vpn import (  # noqa: E402
    LDAP_GROUPS, _direct_users, _find_manager, _group_dn, _integer, _open_connection, _person,
)

SIN_GERENTE = "(sin gerente en AD)"


def collect():
    """Recorre los dos grupos y agrupa las cuentas por su gerente."""
    page_size = _integer("PAGE_SIZE", 200, 20, 1000)
    max_users = _integer("MAX_USERS_PER_GROUP", 5000, 100, 20000)
    conn, base = _open_connection()
    people, found, managers, users = {}, {}, {}, set()
    try:
        for access_type, group_name in LDAP_GROUPS.items():
            group_dn = _group_dn(conn, base, group_name)
            group = _direct_users(conn, base, group_dn, page_size, max_users, with_manager=True)
            print(f"Grupo {access_type}: {len(group)} cuentas", flush=True)
            for info in group.values():
                users.add(info["usuario"])
                dn = info.get("manager_dn")
                boss = _person(conn, dn, people) if dn else None
                manager = _find_manager(conn, dn, people, found) if dn else None
                key = manager["usuario"] if manager else SIN_GERENTE
                item = managers.setdefault(key, {
                    "usuario": key, "nombre": (manager or {}).get("nombre", ""), "cargo": (manager or {}).get("cargo", ""),
                    "departamento": (manager or {}).get("departamento", ""), "correo": (manager or {}).get("correo", ""),
                    "RDP": 0, "APLICACIONES": 0, "usuarios": set(), "cuentas": []})
                item[access_type] += 1
                item["usuarios"].add(info["usuario"])
                estado = "activa" if info.get("activo") else "deshabilitada" if info.get("activo") is False else "-"
                jefe = f"{boss['nombre']} ({boss['cargo'] or 'sin cargo'})" if boss else "sin jefe en AD"
                item["cuentas"].append((info["usuario"], info.get("nombre") or "", access_type, estado, jefe))
    finally:
        try:
            conn.unbind()
        except Exception:
            pass
    print(f"Usuarios VPN únicos: {len(users)}\n")
    for item in managers.values():
        item["total"] = item["RDP"] + item["APLICACIONES"]
    return sorted(managers.values(), key=lambda m: (m["usuario"] == SIN_GERENTE, m["nombre"].lower(), m["usuario"]))


def _cut(text, size):
    text = str(text or "-")
    return text if len(text) <= size else text[:size - 1] + "…"


def main():
    parser = argparse.ArgumentParser(description="Gerentes responsables de las VPN internas del Control 7")
    parser.add_argument("--detalle", metavar="USUARIO", help="lista las cuentas a cargo de ese gerente y su jefe directo")
    parser.add_argument("--csv", metavar="RUTA", help="además guarda el listado en un CSV")
    args = parser.parse_args()

    rows = collect()
    if args.detalle:
        wanted = args.detalle.strip().lower()
        match = next((m for m in rows if m["usuario"] == wanted), None)
        if not match:
            sys.exit(f"{wanted} no figura como gerente responsable de VPN internas")
        print(f"{match['usuario']} - {match['nombre']} | cargo: {match['cargo'] or '-'} | depto: {match['departamento'] or '-'}")
        print(f"Usuarios VPN: {len(match['usuarios'])}  RDP: {match['RDP']}  Aplicaciones: {match['APLICACIONES']}\n")
        print(f"{'CUENTA':<16} {'NOMBRE':<30} {'ACCESO':<13} {'ESTADO AD':<13} JEFE DIRECTO")
        for cuenta, nombre, tipo, estado, jefe in sorted(match["cuentas"]):
            print(f"{cuenta:<16} {_cut(nombre, 30):<30} {tipo:<13} {estado:<13} {_cut(jefe, 60)}")
        return

    print(f"{'#':>3} {'USUARIO':<15} {'GERENTE':<30} {'CARGO (AD)':<45} {'USR':>4} {'RDP':>4} {'APP':>4}")
    print("-" * 111)
    for n, m in enumerate(rows, 1):
        print(f"{n:>3} {_cut(m['usuario'], 15):<15} {_cut(m['nombre'], 30):<30} {_cut(m['cargo'], 45):<45} "
              f"{len(m['usuarios']):>4} {m['RDP']:>4} {m['APLICACIONES']:>4}")
    print("-" * 111)
    gerentes = sum(1 for m in rows if m["usuario"] != SIN_GERENTE)
    sin = next((m for m in rows if m["usuario"] == SIN_GERENTE), None)
    print(f"TOTAL GERENTES: {gerentes} | accesos: {sum(m['total'] for m in rows)}"
          f" | accesos sin gerente en la cadena de AD: {sin['total'] if sin else 0}")

    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8-sig") as fh:
            writer = csv.writer(fh, delimiter=";")
            writer.writerow(["usuario", "gerente", "cargo", "departamento", "correo", "usuarios_vpn", "rdp", "aplicaciones"])
            for m in rows:
                writer.writerow([m["usuario"], m["nombre"], m["cargo"], m["departamento"], m["correo"],
                                 len(m["usuarios"]), m["RDP"], m["APLICACIONES"]])
        print(f"CSV guardado en {args.csv}")


if __name__ == "__main__":
    main()
