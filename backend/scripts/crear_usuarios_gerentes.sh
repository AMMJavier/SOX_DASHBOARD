#!/usr/bin/env bash
# Crea en la plataforma (rol "gerencial", autenticación LDAP) a todos los gerentes del Control 7.
#
# Usuarios LDAP que se toman de Oracle:
#   - SOX_GERENTES_CONTACTO.LDAP_CN (ACTIVO = 1): gerentes de VPN externas.
#   - SOX_C7_VPN_INTERNAS.GERENTE_USUARIO de la campaña activa: gerentes de VPN internas.
#   - El aprobador de directores (LDAP7_APROBADOR_DIRECTORES, por defecto dalava).
# Los que ya existen en la plataforma (con cualquier rol) se omiten: la API responde 409.
#
# Uso (en el servidor):
#   cd /data/sisauto/Proyecto_Sox/sox-dashboard/backend
#   bash scripts/crear_usuarios_gerentes.sh            # crea los usuarios
#   bash scripts/crear_usuarios_gerentes.sh --listar   # solo muestra la lista, no crea nada
set -euo pipefail
cd "$(dirname "$0")/.."
API="${SOX_API:-http://127.0.0.1:8000}"
PY="${PYTHON:-.venv/bin/python}"

USERS=$("$PY" - <<'EOF'
import os
from dotenv import load_dotenv
load_dotenv(".env")
from sqlalchemy import text
from database.oracle_database import SessionLocal
db = SessionLocal()
try:
    names = set()
    for sql in (
        "SELECT LDAP_CN FROM AUTOM.SOX_GERENTES_CONTACTO WHERE ACTIVO = 1 AND LDAP_CN IS NOT NULL",
        """SELECT DISTINCT GERENTE_USUARIO FROM AUTOM.SOX_C7_VPN_INTERNAS
            WHERE GERENTE_USUARIO IS NOT NULL
              AND ID_CAMPANA = (SELECT MAX(ID_CAMPANA) FROM AUTOM.CAMPANAS_SOX WHERE ESTADO = 'ACTIVA')""",
    ):
        names.update(str(r[0]).strip().lower() for r in db.execute(text(sql)) if r[0] and str(r[0]).strip())
    names.add((os.getenv("LDAP7_APROBADOR_DIRECTORES") or "dalava").strip().lower())
    print("\n".join(sorted(names)))
finally:
    db.close()
EOF
)

TOTAL=$(printf '%s\n' "$USERS" | grep -c .)
echo "Gerentes encontrados: $TOTAL"
if [ "${1:-}" = "--listar" ]; then printf '%s\n' "$USERS"; exit 0; fi

# Login de un administrador SOX (la contraseña no se muestra ni queda en el historial).
read -r -p "Usuario administrador: " ADMIN_USER
read -r -s -p "Contraseña: " ADMIN_PASS; echo
TOKEN=$(ADMIN_USER="$ADMIN_USER" ADMIN_PASS="$ADMIN_PASS" "$PY" -c \
  'import json,os;print(json.dumps({"username":os.environ["ADMIN_USER"],"password":os.environ["ADMIN_PASS"]}))' \
  | curl -sS -X POST "$API/auth/login" -H "Content-Type: application/json" --data @- \
  | "$PY" -c 'import json,sys;print(json.load(sys.stdin).get("access_token",""))')
unset ADMIN_PASS
[ -n "$TOKEN" ] || { echo "No se pudo iniciar sesión"; exit 1; }

created=0; existing=0; failed=0
while read -r U; do
  [ -n "$U" ] || continue
  CODE=$(curl -sS -o /tmp/sox_user_resp.json -w '%{http_code}' -X POST "$API/usuarios" \
    -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
    --data "{\"username\":\"$U\",\"auth_provider\":\"ldap\",\"rol\":\"gerencial\"}")
  case "$CODE" in
    201) created=$((created+1)); echo "CREADO     $U" ;;
    409) existing=$((existing+1)); echo "YA EXISTE  $U" ;;
    *)   failed=$((failed+1)); echo "ERROR $CODE $U: $(cat /tmp/sox_user_resp.json)" ;;
  esac
done <<< "$USERS"
rm -f /tmp/sox_user_resp.json
echo "Creados: $created | Ya existían: $existing | Errores: $failed"
