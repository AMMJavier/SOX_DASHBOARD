"""Pruebas aisladas con SQLite; requieren las dependencias de requirements.txt."""
import os
import tempfile
from pathlib import Path

TEST_DIR = Path(tempfile.mkdtemp(prefix="hitss_sox_tests_"))
os.environ["SOX_TEST_DATABASE_URL"] = "sqlite:///" + str(TEST_DIR / "test.sqlite")
os.environ["JWT_SECRET_KEY"] = "test-only-random-not-a-production-secret-ABC123456789012345"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from oracle_database import engine, SessionLocal, get_oracle_db
from models import Usuario
from main import app
from auth import auth as auth_module
from auth import dependencies as deps

@event.listens_for(engine, "connect")
def attach_autom(dbapi_conn, record):
    dbapi_conn.execute("ATTACH DATABASE ? AS AUTOM", (str(TEST_DIR / "autom.sqlite"),))

Usuario.__table__.create(engine)

def session_dep():
    with SessionLocal() as db:
        yield db

app.dependency_overrides[get_oracle_db] = session_dep

@pytest.fixture(autouse=True)
def clean_users(monkeypatch):
    monkeypatch.setattr(auth_module, "authenticate_ldap", lambda username, password: bool(password))
    with SessionLocal() as db:
        db.query(Usuario).delete()
        db.add_all([
            Usuario(id=1, username="admin_sox", auth_provider="local", rol="administrador", activo=1,
                    password_hash=auth_module.get_password_hash("PasswordPrueba123")),
            Usuario(id=2, username="admin_assets", auth_provider="local", rol="assets_admin", activo=1,
                    password_hash=auth_module.get_password_hash("PasswordPrueba123")),
            Usuario(id=3, username="viewer_assets", auth_provider="ldap", rol="assets_viewer", activo=1),
            Usuario(id=4, username="gerente_sox", auth_provider="ldap", rol="gerencial", activo=1),
        ])
        db.commit()
    monkeypatch.setattr(deps, "decode_access_token", lambda token: {
        "sub": {"sox":"admin_sox", "assets":"admin_assets", "viewer":"viewer_assets", "gerente":"gerente_sox"}.get(token,"missing"),
        "id": {"sox":1, "assets":2, "viewer":3, "gerente":4}.get(token,999), "exp": 9999999999,
    })

client = TestClient(app)

def auth_as(role):
    return {"Authorization": f"Bearer {role}"}

def test_rutas_y_no_publicidad():
    paths = {x.path for x in app.routes}
    for path in ("/auth/login", "/auth/me", "/usuarios", "/usuarios/{usuario_id}/estado",
                 "/usuarios/{usuario_id}/contrasena", "/sox/campaign/active", "/assets/inventory"):
        assert path in paths, path
    assert client.get("/assets/dashboard").status_code == 401
    assert client.get("/sox/campaign/active").status_code == 401

def test_segregacion_sox_assets():
    preview = client.post("/assets/upload/preview", headers=auth_as("sox"),
                          files={"file": ("inventario.csv", b"DESCRIPCION\nitem", "text/csv")})
    assert preview.status_code in {200, 400, 422}, preview.text
    assert client.get("/sox/campaign/active", headers=auth_as("assets")).status_code == 403
    assert client.get("/usuarios", headers=auth_as("viewer")).status_code == 403
    assert client.get("/auth/me", headers=auth_as("viewer")).json()["modulos"] == ["assets"]
    assert client.get("/auth/me", headers=auth_as("sox")).json()["modulos"] == ["sox", "assets"]

def test_creacion_local_y_ldap_admin_sox():
    local = client.post("/usuarios", headers=auth_as("sox"), json={
        "username":"nuevo_local", "rol":"desarrollador", "auth_provider":"local", "password":"PasswordPrueba123"})
    assert local.status_code == 201, local.text
    assert "password_hash" not in local.json()
    ldap = client.post("/usuarios", headers=auth_as("sox"), json={
        "username":"nuevo_ldap", "rol":"gerencial", "auth_provider":"ldap"})
    assert ldap.status_code == 201, ldap.text
    denied = client.post("/usuarios", headers=auth_as("sox"), json={
        "username":"intruso", "rol":"assets_admin", "auth_provider":"ldap"})
    assert denied.status_code == 201
    assert "assets_admin" in client.get("/usuarios/permisos", headers=auth_as("sox")).json()["roles_creables"]
    with SessionLocal() as db:
        assert db.query(Usuario).filter_by(username="nuevo_local").first().password_hash.startswith("$2")
        assert db.query(Usuario).filter_by(username="nuevo_ldap").first().password_hash is None

def test_assets_admin_no_puede_modificar_sox():
    assert client.patch("/usuarios/1/estado", headers=auth_as("assets"), json={"activo":False}).status_code == 403
    created = client.post("/usuarios", headers=auth_as("assets"), json={
        "username":"asset_nuevo", "rol":"assets_viewer", "auth_provider":"ldap"})
    assert created.status_code == 201, created.text
    assert {u["rol"] for u in client.get("/usuarios", headers=auth_as("assets")).json()} <= {"assets_admin","assets_viewer"}

def test_login_y_cambio_estado():
    ok = client.post("/auth/login", json={"username":"ADMIN_SOX", "password":"PasswordPrueba123"})
    assert ok.status_code == 200, ok.text
    assert ok.json()["rol"] == "administrador"
    assert client.post("/auth/login", json={"username":"admin_sox", "password":"incorrecta"}).status_code == 401
    assert client.patch("/usuarios/1/estado", headers=auth_as("sox"), json={"activo":False}).status_code == 400
    assert client.patch("/usuarios/3/estado", headers=auth_as("assets"), json={"activo":False}).status_code == 200
    assert client.get("/auth/me", headers=auth_as("viewer")).status_code == 401


def test_viewer_no_es_editor_ni_administrador_campanas():
    r = client.post("/assets/upload/preview", headers=auth_as("viewer"),
                    files={"file": ("inventario.csv", b"DESCRIPCION\nitem", "text/csv")})
    assert r.status_code == 403, r.text
    assert client.post("/sox/campaign/start", headers=auth_as("gerente")).status_code == 403
    assert client.get("/sox/admin/validations", headers=auth_as("gerente")).status_code == 403
    assert client.get("/usuarios", headers=auth_as("gerente")).status_code == 403


def test_admin_global_puede_gestionar_usuarios_assets():
    response = client.post("/usuarios", headers=auth_as("sox"), json={
        "username": "supervisor_crea_assets", "rol": "assets_viewer", "auth_provider": "ldap"
    })
    assert response.status_code == 201, response.text
    roles = {u["rol"] for u in client.get("/usuarios", headers=auth_as("sox")).json()}
    assert {"administrador", "assets_admin", "assets_viewer", "gerencial"} <= roles
    assert client.get("/usuarios/permisos", headers=auth_as("sox")).json()["modulo"] == "global"
    assert client.post("/assets/upload/preview", headers=auth_as("sox"),
                       files={"file": ("inventario.csv", b"DESCRIPCION\nitem", "text/csv")}).status_code != 403

def test_assets_admin_no_crea_roles_sox():
    response = client.post("/usuarios", headers=auth_as("assets"), json={
        "username": "sin_permiso", "rol": "gerencial", "auth_provider": "ldap"
    })
    assert response.status_code == 403
