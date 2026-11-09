# Ajuste jerárquico de permisos — HITSS/SOX Dashboard

## Jerarquía

| Rol | SOX | Assets consulta | Assets escritura/carga | Administración de usuarios | Portal de módulos |
|---|---|---|---|---|---|
| `administrador` (supervisor SOX) | Completo | Sí | Sí | Todos los roles de SOX y Assets | Sí; SOX, Assets, Network, Maintenance |
| `assets_admin` | No | Sí | Sí | Solo `assets_admin` y `assets_viewer` | No (ingresa directo a Assets) |
| `assets_viewer` | No | Sí | No | No | No |
| `desarrollador` | Según permisos SOX existentes | No | No | No | Según configuración previa |
| `gerencial` | Lectura/validaciones SOX existentes | No | No | No | No |

## Archivos modificados

- `backend/auth/dependencies.py`: incluye `administrador` en roles autorizados de Assets, conservando lectura para `assets_viewer`.
- `backend/auth/users.py`: permite que `administrador` gestione usuarios de ambos módulos. `/usuarios/permisos` indica `modulo: global`.
- `backend/tests/test_api_integrada.py`: actualiza pruebas de acceso global, creación de usuarios y segregación de Assets.
- `frontend/src/pages/ModuleSelector.jsx`: muestra Assets al administrador SOX; mantiene el portal principal.
- `frontend/src/routes/routerAssets.jsx`: permite que `administrador` navegue, importe y gestione usuarios en Assets.
- `frontend/src/components/Assets/Sidebar.jsx`: permite al administrador SOX acceder a carga y administración de usuarios en Assets.
- `frontend/src/pages/SOX/Control_7/Users.jsx`: indica administración global cuando corresponda.

## Instalación segura

**IMPORTANTE**: el ZIP contiene carpetas `backend/` y `frontend/`. Extraer en la **raíz `sox-dashboard/`**, no dentro de `backend/` ni de `frontend/`.

```bash
cd /data/sisauto/Proyecto_Sox/sox-dashboard
cp -a backend/auth backend/auth.bak_roles
cp -a backend/tests backend/tests.bak_roles
cp -a frontend/src frontend/src.bak_roles
unzip -l HITSS_SOX_parche_admin_global.zip
unzip -o HITSS_SOX_parche_admin_global.zip -d .
```

> El ZIP incluye este README en la raíz; no contiene contraseñas ni tokens.

Validación backend desde directorio `backend/` y su entorno virtual:

```bash
cd /data/sisauto/Proyecto_Sox/sox-dashboard/backend
source .venv/bin/activate
python -m compileall -q auth tests/test_api_integrada.py
python -m pytest tests/test_api_integrada.py -q  # requiere pytest y dependencias del backend
```

Compilación frontend:

```bash
cd /data/sisauto/Proyecto_Sox/sox-dashboard/frontend
npm run build
```

Publicar el nuevo `dist/` en la ubicación servida por Nginx y recargar sesión en navegador. Para backend, reiniciar el proceso o servicio FastAPI normalmente utilizado por HITSS.

## Comprobaciones después de reiniciar

1. Entrar con `administrador` y consultar `GET /auth/me`: debe incluir `"modulos": ["sox", "assets"]`.
2. Entrar al portal `/modules`: deben aparecer SOX y Assets.
3. En Assets, administrador SOX debe poder ver **Upload file** y **Administrar usuarios**.
4. `GET /usuarios/permisos` con administrador SOX: `"modulo":"global"`, incluyendo roles `assets_admin` y `assets_viewer`.
5. `POST /usuarios` (minúsculas) con administrador SOX y JSON válido para crear un usuario `assets_viewer`: `201 Created` si no existe.
6. `assets_admin` conserva acceso al módulo Assets y usuarios Assets, pero `POST /usuarios` con rol `gerencial` debe devolver `403`.
7. `assets_viewer` puede consultar inventario, pero no importar archivos.
8. Verificar acceso a Control 7, inicio de campañas e historial según las credenciales de cada rol.

**Nota**: el `404` previo de `POST /USUARIOS` proviene de la capitalización de la ruta. Debe invocarse `/usuarios`. La corrección de permisos por sí sola no altera esa ruta.

**Validación realizada fuera de HITSS**: `compileall` Python y parseo de los cuatro componentes JSX modificados. **No se ejecutó suite integrada en Oracle/LDAP ni la compilación Vite en HITSS**.
