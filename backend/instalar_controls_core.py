#!/usr/bin/env python3
"""Instala solo los módulos controls_core desde este parche, sin cambiar rutas SOX previas."""
from pathlib import Path
from datetime import datetime
import ast
import shutil
import sys
import tempfile

source_dir = Path(__file__).resolve().parent / "backend/routes/SOX/controls_core"
backend = Path(sys.argv[1]).expanduser().resolve() if len(sys.argv) > 1 else Path.cwd().resolve()
router_path = backend / "routes/sox.py"
target_dir = backend / "routes/SOX/controls_core"
files = ("__init__.py", "evidence.py", "reconcile.py", "events5.py")

if not router_path.is_file():
    raise SystemExit("ERROR: Debes indicar la carpeta backend que contiene routes/sox.py")
for name in files:
    path = source_dir / name
    if not path.is_file():
        raise SystemExit(f"ERROR: Falta archivo fuente: {path}")
    ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

router_code = router_path.read_text(encoding="utf-8")
missing = [name for name in ("controls_evidence_router", "controls_reconcile_router", "controls_events5_router") if name not in router_code]
if missing:
    raise SystemExit("ERROR: sox.py no parece incluir los tres routers nuevos: " + ", ".join(missing))

target_dir.mkdir(parents=True, exist_ok=True)
backup_dir = backend / "backups" / ("controls_core_" + datetime.now().strftime("%Y%m%d_%H%M%S"))
for name in files:
    existing = target_dir / name
    if existing.exists():
        backup_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(existing, backup_dir / name)
    with tempfile.NamedTemporaryFile(dir=target_dir, prefix=".new_", delete=False) as temp:
        temp.write((source_dir / name).read_bytes())
        temp_path = Path(temp.name)
    temp_path.chmod(0o644)
    temp_path.replace(existing)
    print("Instalado:", existing)
print("OK: controles_core completo.")
if backup_dir.is_dir():
    print("Respaldo de archivos sustituidos:", backup_dir)
print("Siguiente comprobación: .venv/bin/python -c 'from routes.sox import router; print(len(router.routes))'")
