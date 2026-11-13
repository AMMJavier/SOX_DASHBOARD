"""API unificada HITSS: autenticación, SOX (incluido control 7) y Assets.

Ejecutar desde el directorio backend_integrado: uvicorn main:app --host 0.0.0.0 --port 8000
"""
import os
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()
from auth.auth import router as auth_router
from auth.users import router as users_router
from auth.dependencies import require_sox_access, require_assets_access
from routes.sox import router as sox_router
from routes.assets import router as assets_router

app = FastAPI(title="HITSS / SOX Dashboard API", version="1.1.0", swagger_ui_parameters={"defaultModelsExpandDepth": -1})

# Exigir una lista precisa de orígenes para habilitar cookies/credenciales.
_origins = [x.strip() for x in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if x.strip()]
if "*" in _origins:
    raise RuntimeError("CORS_ORIGINS no puede contener '*' con credenciales habilitadas")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)

app.include_router(auth_router)
app.include_router(users_router)
# No cambiar las rutas internas: son consumidas por el frontend actual.
app.include_router(sox_router, dependencies=[Depends(require_sox_access)])
app.include_router(assets_router, dependencies=[Depends(require_assets_access)])

@app.get("/", tags=["Salud"])
def root():
    return {"message": "SOX Backend funcionando correctamente", "version": "1.1.0"}

@app.get("/health", tags=["Salud"])
def health():
    # No simula una comprobación de bases externas.
    return {"status": "up"}
