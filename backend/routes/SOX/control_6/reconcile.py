"""Control 6: cruce exacto de identificadores internos, sin mutar LDAP ni SASE.

Se utiliza solo para muestras autorizadas suministradas explícitamente en la petición.
NO consulta VPN externas Check Point, NO realiza bajas y NO guarda personas en Oracle.
"""
from collections import Counter, defaultdict
import unicodedata
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from auth.dependencies import get_current_user
from models import Usuario

router = APIRouter(prefix="/controls/6", tags=["SOX control 6 - conciliación interna"])


def account_key(raw):
    """Normaliza solo un identificador de cuenta: no unir nombres completos similares."""
    value = unicodedata.normalize("NFKC", str(raw or "")).strip().casefold()
    if value.startswith("porta\\"):
        value = value[len("porta\\"):]
    if value.endswith("@porta.corp"):
        value = value[:-len("@porta.corp")]
    if not value or len(value) > 100 or any(c.isspace() for c in value):
        return None
    return value


class ReconInput(BaseModel):
    rrhh: List[str] = Field(max_length=2000)
    accesos: List[str] = Field(max_length=5000)
    fuente: str = Field(default="CORTE_MANUAL", max_length=40)


@router.post("/conciliar")
def conciliar(data: ReconInput, user: Usuario = Depends(get_current_user)):
    if user.rol not in ("administrador", "desarrollador"):
        raise HTTPException(403, "Sin permisos para conciliar información de personal")
    # Una cuenta puede tener varias autorizaciones RDP/aplicaciones: relación 1:N válida.
    access_index = defaultdict(list)
    invalid_accesos = 0
    for raw in data.accesos:
        key = account_key(raw)
        if key is None:
            invalid_accesos += 1
            continue
        access_index[key].append(str(raw).strip())
    hr_counts = Counter(account_key(x) for x in data.rrhh if account_key(x) is not None)
    results = []
    invalid_hr = 0
    for row, account in enumerate(data.rrhh):
        key = account_key(account)
        if key is None:
            invalid_hr += 1
            results.append({"id": row, "account": account, "matches": [], "status": "ambiguo", "motivo": "Identificador incompleto o inválido"})
            continue
        matches = access_index.get(key, [])
        status = "ambiguo" if hr_counts[key] > 1 else ("coincide" if matches else "no_coincide")
        results.append({"id": row, "account": account, "matches": matches, "status": status,
                        "motivo": "Duplicado en fuente RR. HH." if hr_counts[key] > 1 else None})
    return {
        "resumen": {
            "rrhh": len(data.rrhh), "vpn": len(data.accesos),
            "coincidences": sum(x["status"] == "coincide" for x in results),
            "ambiguous": sum(x["status"] == "ambiguo" for x in results),
            "missing": sum(x["status"] == "no_coincide" for x in results),
            "accesos_encontrados": sum(len(x["matches"]) for x in results if x["status"] == "coincide"),
            "rrhh_invalidos": invalid_hr, "accesos_invalidos": invalid_accesos,
        },
        "items": results,
        "nota": "Cruce exacto de identificadores suministrados: no valida cesantías ni autoriza una baja; SASE/LDAP aún no están integrados."
    }
