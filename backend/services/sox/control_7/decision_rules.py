"""Control 7 - reglas de las decisiones del gerente (VPN externas e internas).

- Mantener / Eliminar: la VPN queda CONFIRMADA (CONFIRMACION = 1) y ya no cambia, aunque se
  actualice la campaña o cambie el gerente en Check Point / Active Directory.
- No pertenece / Otro: la VPN queda REPORTADA. Sigue PENDIENTE (CONFIRMACION = 0) para que el
  administrador corrija el gerente; al actualizar, si el gerente cambió, vuelve limpia al nuevo.
- Una VPN confirmada o reportada ya fue respondida: el gerente no puede cambiar la decisión.
"""
from __future__ import annotations  # Python 3.9 en el servidor

import re
import unicodedata

DECISIONS = {"mantener": "Mantener", "eliminar": "Eliminar", "no pertenece": "No pertenece", "otro": "Otro"}
REPORTED = ("no pertenece", "otro")
# Fragmento SQL (columna ESTADO): la VPN fue reportada por el gerente.
REPORTED_SQL = "LOWER(TRIM(NVL(ESTADO, 'mantener'))) IN ('no pertenece', 'otro')"


def normalize(value) -> str:
    return str(value or "").strip().lower()


def is_reported(estado) -> bool:
    return normalize(estado) in REPORTED


def confirmation_for(estado) -> int:
    """1 = la decisión confirma la VPN; 0 = queda pendiente (reportada)."""
    return 0 if is_reported(estado) else 1


def is_confirmed(estado, confirmacion) -> bool:
    """Confirmada de verdad (Mantener o Eliminar): no cambia al actualizar la campaña."""
    return int(confirmacion or 0) == 1 and not is_reported(estado)


def is_answered(estado, confirmacion) -> bool:
    """El gerente ya respondió (confirmada o reportada): su decisión no se puede cambiar."""
    return int(confirmacion or 0) == 1 or is_reported(estado)


def manager_key(name) -> str:
    """Normaliza el nombre del gerente: sin NBSP, espacios dobles ni acentos, sin mayúsculas."""
    value = (name or "").replace("\xa0", " ")
    value = unicodedata.normalize("NFKD", value)
    value = "".join(c for c in value if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", value).strip().casefold()
