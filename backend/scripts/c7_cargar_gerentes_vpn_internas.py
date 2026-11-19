"""Control 7 - VPN internas: revisa y carga los GERENTES en la tabla que lee la plataforma.

La pantalla de Control 7 -> Internas (tabla, "Notificación a gerentes", dashboard) lee
AUTOM.SOX_C7_VPN_INTERNAS de la campaña activa. Las columnas GERENTE / GERENTE_USUARIO /
GERENTE_CORREO se llenan SOLO al cargar desde LDAP; si la campaña se cargó con la regla
anterior, ahí siguen los jefes directos.

Uso (en el servidor, desde la carpeta backend):
    .venv/bin/python scripts/c7_cargar_gerentes_vpn_internas.py            # solo revisa (no escribe)
    .venv/bin/python scripts/c7_cargar_gerentes_vpn_internas.py --cargar   # lee LDAP y guarda los gerentes
    .venv/bin/python scripts/c7_cargar_gerentes_vpn_internas.py --reemplazar  # BORRA la carga y la hace de cero

--cargar hace exactamente lo mismo que el botón "Cargar desde LDAP": usa la regla del script
c7_gerentes_vpn_internas.py (primer cargo "Gerente" en la cadena de jefes de AD). Las cuentas
cuyo gerente cambia vuelven a pendiente para el nuevo gerente.
--reemplazar borra todas las cuentas de la campaña activa (y su seguimiento) y las carga de nuevo
con los gerentes; es lo mismo que pasa al iniciar una campaña. Si algún gerente ya confirmó
cuentas, no borra nada.
"""
import argparse
import os
import sys

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BACKEND)

from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(BACKEND, ".env"))

from sqlalchemy import text  # noqa: E402

from database.oracle_database import SessionLocal  # noqa: E402
from services.sox.control_7.internal_vpn import active_campaign, load_from_ldap  # noqa: E402


def review(db, campaign_id):
    """Lo que hoy ve la plataforma: gerentes guardados en SOX_C7_VPN_INTERNAS."""
    rows = db.execute(text("""
        SELECT GERENTE_USUARIO AS "usuario", MIN(GERENTE) AS "nombre", COUNT(*) AS "total",
               SUM(CASE WHEN TIPO_ACCESO = 'RDP' THEN 1 ELSE 0 END) AS "rdp",
               SUM(CASE WHEN TIPO_ACCESO = 'APLICACIONES' THEN 1 ELSE 0 END) AS "app"
          FROM AUTOM.SOX_C7_VPN_INTERNAS WHERE ID_CAMPANA = :p_camp
         GROUP BY GERENTE_USUARIO ORDER BY MIN(GERENTE)
    """), {"p_camp": campaign_id}).mappings().all()
    print(f"\nTabla AUTOM.SOX_C7_VPN_INTERNAS - campaña {campaign_id}")
    print(f"{'#':>3} {'USUARIO':<15} {'GERENTE GUARDADO':<40} {'TOTAL':>5} {'RDP':>4} {'APP':>4}")
    print("-" * 76)
    for n, r in enumerate(rows, 1):
        print(f"{n:>3} {str(r['usuario'] or '(sin gerente)')[:15]:<15} {str(r['nombre'] or '-')[:40]:<40} "
              f"{r['total']:>5} {r['rdp']:>4} {r['app']:>4}")
    print("-" * 76)
    total = sum(r["total"] for r in rows)
    print(f"GERENTES GUARDADOS: {sum(1 for r in rows if r['usuario'])} | registros: {total}")


def main():
    parser = argparse.ArgumentParser(description="Gerentes de VPN internas guardados en la campaña activa")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--cargar", action="store_true", help="lee LDAP y guarda los gerentes (igual que el botón)")
    group.add_argument("--reemplazar", action="store_true", help="borra la carga de la campaña y la hace de cero")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        campaign = active_campaign(db)
        if not campaign:
            sys.exit("No hay una campaña activa del Control 7")
        if args.cargar or args.reemplazar:
            print("Leyendo LDAP y guardando gerentes en la campaña activa...", flush=True)
            try:
                summary = load_from_ldap(db, replace=args.reemplazar)
            except Exception as exc:
                db.rollback()
                sys.exit(f"No se cargó: {getattr(exc, 'detail', None) or exc}")
            print(f"Carga terminada: {summary}")
        review(db, campaign["id"])
    finally:
        db.close()


if __name__ == "__main__":
    main()
