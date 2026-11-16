# SOX Dashboard — Portal de Control Tecnológico

Portal web interno para gestionar los **controles SOX** de seguridad de red (evidencias, validaciones,
notificaciones y auditoría) y el **inventario de activos** de red.

| Módulo | Qué hace | Base de datos |
|---|---|---|
| **SOX** | Controles 1, 2, 3, 4, 5, 6, 7 y 10: repositorio de evidencias, validación semestral de VPN, correos y recordatorios | Oracle |
| **Assets** | Inventario de dispositivos de red, carga masiva y historial de cambios | PostgreSQL |
| **Network / Maintenance** | Pantallas informativas | — |

El acceso es con cuenta **local** (contraseña cifrada con bcrypt) o **corporativa LDAP / Active Directory**.

---

## Contenido

- [Arquitectura](#arquitectura)
- [Estructura del proyecto](#estructura-del-proyecto)
- [Requisitos](#requisitos)
- [Instalación y ejecución](#instalación-y-ejecución)
- [Configuración](#configuración)
- [Base de datos](#base-de-datos)
- [Controles SOX](#controles-sox)
- [Control 7: validación semestral de VPN](#control-7-validación-semestral-de-vpn)
- [Correos, recordatorios y alertas](#correos-recordatorios-y-alertas)
- [Roles y permisos](#roles-y-permisos)
- [Despliegue](#despliegue)
- [Diagnóstico](#diagnóstico)
- [Documentación adicional](#documentación-adicional)

---

## Arquitectura

```
Navegador
   │
   ▼
Frontend React + Vite ──── /api/... ────► Backend FastAPI (uvicorn, main.py)
                                              ├── /auth, /usuarios ...... login y usuarios ........ Oracle
                                              ├── /sox/... .............. controles SOX ........... Oracle
                                              └── /assets/... ........... inventario de activos ... PostgreSQL
                                              │
                                              ├── LDAP / AD ......... login y correos de gerentes
                                              ├── Check Point API ... extracción de VPN (Control 7)
                                              └── Microsoft Graph ... envío de correos y archivado como evidencia
```

| Capa | Tecnología |
|---|---|
| Frontend | React 19, Vite, Tailwind CSS, React Router, ExcelJS, jsPDF |
| Backend | Python 3.9, FastAPI, SQLAlchemy 2, oracledb, psycopg2, ldap3 |
| Bases de datos | Oracle (esquema `AUTOM`) y PostgreSQL (esquema `autom`) |
| Integraciones | Check Point Management API, LDAP/AD, Microsoft Graph (vía script corporativo) |

---

## Estructura del proyecto

Criterio: lo que pertenece a un solo control va en su carpeta `control_N`; lo compartido por
varios controles va en `common`.

```
backend/
├── main.py                     App FastAPI, routers y arranque del programador de recordatorios
├── models.py · schemas.py      Modelos SQLAlchemy y esquemas Pydantic
├── auth/                       Login local/LDAP, JWT, sesiones, administración de usuarios
├── database/                   Conexiones Oracle (SQLAlchemy y oracledb) y PostgreSQL
├── checkpoint/                 Extracción de VPN desde Check Point (python -m checkpoint.sync_service)
├── routes/
│   ├── assets/                 API de Assets
│   └── sox/
│       ├── common/             Evidencias, correo formal, notificaciones y calendario
│       ├── control_5/          Eventos de administradores de firewall
│       ├── control_6/          Conciliación de cesantes y accesos internos
│       └── control_7/          Campañas, validaciones, dashboard, histórico, logs, avisos
├── services/sox/
│   ├── common/                 mail_config (correos.json), mail_service, reminder_service,
│   │                           reminder_scheduler (envío automático)
│   ├── control_6/              Conciliación, cortes LDAP
│   └── control_7/              Avisos a gerentes, sincronización de contactos LDAP
├── scripts/                    sox_graph_mail.py (worker Graph), migración Assets, utilidades
├── sql/                        Scripts Oracle y PostgreSQL
└── config/                     correos.example.json (plantilla; los .json reales no se versionan)

frontend/src/
├── routes/ · layouts/          Rutas y layouts por módulo
├── pages/Admin/                Administración de usuarios
├── pages/SOX/Control_N/        Página de cada control
├── pages/Assets/ ...           Páginas de Assets
├── components/common/          Componentes compartidos (paginación, generador de claves)
├── components/SOX/common/      Espacio de trabajo de controles, correo formal, notificaciones
├── components/SOX/control_N/   Componentes propios de cada control
├── services/                   Clientes de la API (common y por control)
└── utils/                      Utilidades (exportación Excel/PDF del Control 7, generador de claves)
```

---

## Requisitos

- **Python 3.9** (el código evita sintaxis de versiones posteriores).
- **Node.js** 20 o superior y npm.
- **Oracle** con el esquema `AUTOM` y **PostgreSQL** para Assets.
- Acceso de red a LDAP/AD, a la API de Check Point y al buzón corporativo de Microsoft Graph
  (el envío usa un script corporativo con su propio entorno Python que incluye la librería `O365`).

---

## Instalación y ejecución

### Backend

```bash
cd backend
python3.9 -m venv .venv
source .venv/bin/activate
pip install -r requirements-lock.txt
cp .env.example .env                                  # completar credenciales
cp config/correos.example.json config/correos.json    # completar remitente, dominios y destinatarios
uvicorn main:app --host 0.0.0.0 --port 8000
```

> En el servidor **no usar `--reload`**: deja un proceso hijo que puede seguir sirviendo código viejo.
> Para reiniciar:
> `pkill -f "uvicorn main:app"; sleep 2; nohup uvicorn main:app --host 0.0.0.0 --port 8000 > uvicorn.log 2>&1 &`

### Frontend

```bash
cd frontend
npm install
npm run dev        # desarrollo (puerto 5173)
npm run build      # genera dist/ para publicar
```

### Arranque conjunto

`start_sox.sh` sincroniza Check Point, levanta la API y el frontend.

---

## Configuración

Nada sensible se guarda en el repositorio. Los archivos reales están en `.gitignore`.

| Archivo | Contenido | En git |
|---|---|---|
| `backend/.env` | Credenciales Oracle/PostgreSQL/LDAP, JWT, interruptores de correo, rutas | No (plantilla: `.env.example`) |
| `backend/config/correos.json` | Remitente, dominios, destinatarios, copias, plantillas, calendario | No (plantilla: `correos.example.json`) |
| `backend/config/config.json` | Conexión a Check Point | No |
| `backend/config/oracle_config.json` | Conexión Oracle (respaldo del `.env`) | No |

Variables principales del `.env` (ver `backend/.env.example`):

| Variable | Uso |
|---|---|
| `ORACLE_*` | Conexión Oracle (SOX y login) |
| `POSTGRES_*` o `ASSETS_DATABASE_URL` | Conexión PostgreSQL (Assets) |
| `LDAP_SERVER`, `LDAP_BASE_DN`, `LDAP_SERVICE_USER`, `LDAP_SERVICE_PASSWORD`, `LDAP_PREFIX` | Login y búsqueda de correos |
| `JWT_SECRET_KEY`, `JWT_ALGORITHM`, `JWT_EXPIRE_MINUTES` | Sesiones |
| `CORS_ORIGINS` | Orígenes permitidos del frontend |
| `SOX_EVIDENCE_DIR` | Carpeta privada de evidencias (fuera del proyecto) |
| `SOX_MAIL_ENABLED`, `SOX_MAIL_CONTROLS` | Habilitan el envío de correos y los controles que pueden enviar |
| `SOX_GRAPH_SCRIPT`, `SOX_GRAPH_PYTHON` | Script corporativo de Graph y el Python que tiene `O365` |
| `SOX_PORTAL_URL` | Enlace al portal en los avisos |
| `SOX_SCHEDULER_DISABLED` | `true` desactiva por completo los envíos automáticos |

---

## Base de datos

### Oracle (esquema `AUTOM`)

| Tabla / objeto | Uso |
|---|---|
| `USUARIOS`, `SOX_SESIONES` | Cuentas y sesiones |
| `SOX_CONTROL_EVIDENCIAS`, `SOX_CONTROL_EVIDENCIA_AUD` | Evidencias de los controles y su auditoría |
| `SOX_MAIL_OUTBOX` | Bandeja y auditoría de **todos** los correos SOX (estado, destinatarios, clave anti-duplicados) |
| `CAMPANAS_SOX` | Campañas del Control 7 |
| `FUENTE_CHECKPOINT` | VPN extraídas de Check Point, tal cual |
| `CHECKPOINT_TRANSFORM` | VPN válidas para validar (REQ, solicitante, gerente, decisión) |
| `CHECKPOINT_RECHAZADOS` | VPN cuyo comentario no cumple el formato, con el motivo |
| `CHECKPOINT_HISTORICO` | VPN de campañas cerradas |
| `SOX_GERENTES_CONTACTO` | Gerente → correo y usuario LDAP |
| `TRG_FUENTE_CHECKPOINT_TRANSFORM`, `F_CHECKPOINT_MOTIVO` | Trigger y función que clasifican las VPN |

Scripts en `backend/sql/` (ejecutar con el propietario del esquema):

| Script | Uso |
|---|---|
| `sox_mail_outbox.sql`, `sox_mail_outbox_c5.sql`, `sox_mail_outbox_c7.sql` | Bandeja de correos (en ese orden) |
| `checkpoint_rechazados.sql` | Tabla de VPN rechazadas, función de motivo y trigger |
| `respaldo_trg_fuente_checkpoint_transform.sql` | Vuelve el trigger a su versión original |
| `postgres/assets_schema.sql` | Esquema de Assets en PostgreSQL |

---

## Controles SOX

Cada control muestra qué hace, cuál es su evidencia y un panel con **total de evidencias,
confirmadas, pendientes y vencidas**. La plataforma es el repositorio interno de evidencias;
auditoría recibe lo que se exporta, no accede a la plataforma.

| Control | Descripción | Periodicidad | En la plataforma |
|---|---|---|---|
| 1 | Revisión del procedimiento SIS016 | Anual (varias versiones en el año) | Repositorio, correo formal, notificación |
| 2 | Plan de Seguridad de firewalls | Anual | Repositorio, correo formal, notificación con el plan adjunto |
| 3 | Seguimiento del Plan de Seguridad | Semestral | Repositorio, correo formal, notificación con el último plan |
| 4 | Accesos remotos VPN vía Workflow | Por solicitud | Informativo: automatizado, auditoría accede a Workflow (Remedy) |
| 5 | Cambios de administradores de firewall | Por evento | Expediente por evento + consolidado semestral |
| 6 | Cesantes vs accesos VPN internos | Semestral | Conciliación RR. HH. vs LDAP (rediseño pendiente) |
| 7 | Validación de VPN por gerentes | Semestral (campañas) | Ver sección siguiente |
| 10 | Control automatizado | — | Informativo |

**Correo formal** (Controles 1, 2, 3 y 5): se envía desde el buzón corporativo y la copia enviada
se guarda automáticamente como evidencia en dos formatos: **EML** (original íntegro con adjuntos)
y **PDF** (legible). Ambos quedan en estado *Cargada* hasta que un administrador los verifica.

---

## Control 7: validación semestral de VPN

```
Check Point ─(sync)─► FUENTE_CHECKPOINT ─(trigger)─┬─► CHECKPOINT_TRANSFORM ─► validación de gerentes
                                                   └─► CHECKPOINT_RECHAZADOS ─► "VPN sin parametrizar"
CHECKPOINT_TRANSFORM.GERENTE ─(LDAP)─► SOX_GERENTES_CONTACTO ─► aviso por correo ─► SOX_MAIL_OUTBOX
```

1. **Extracción**: al iniciar o actualizar la campaña se consultan las VPN en Check Point.
2. **Clasificación** (trigger en Oracle): el comentario debe tener el formato
   `REQ - SOLICITANTE - GERENTE` (exactamente dos separadores `" - "`, ninguna parte vacía).
   Las válidas pasan a validación; las demás quedan en *VPN sin parametrizar* con el motivo exacto.
3. **Contactos**: se busca el correo de cada gerente en LDAP (también sin el prefijo de área,
   p. ej. `TIC Nombre Apellido` → `Nombre Apellido`).
4. **Aviso a gerentes**: un correo por gerente con la lista de sus VPN. Sin duplicados: un gerente
   queda notificado en el correo al que se le envió; si su correo cambia, vuelve a quedar pendiente.
   Existe un **modo prueba** que envía todo a destinatarios fijos con asunto `[PRUEBA]`.
5. **Validación**: cada gerente (rol *gerencial*, vinculado por su usuario LDAP) ve solo sus VPN y
   decide mantener/eliminar. Puede modificar su decisión hasta la fecha límite de la campaña.
   Si una VPN cambia de gerente, conserva la decisión y el nuevo gerente puede modificarla.
6. **Reportes**: dashboard (total de VPN de Check Point vs conciliadas), histórico, logs de
   auditoría y exportación a Excel/PDF de lo que muestra cada pantalla.

"Actualizar campaña" vuelve a sincronizar las VPN y los correos de los gerentes.
Una campaña no se inicia si la sincronización con Check Point falla.

---

## Correos, recordatorios y alertas

Toda la configuración de correo está en `backend/config/correos.json` y **se relee sola al guardar**
(no requiere reiniciar). Si el archivo queda mal escrito se conserva la última versión válida.

| Clave | Uso |
|---|---|
| `remitente`, `dominios_permitidos` | Buzón que envía y dominios a los que se permite enviar |
| `copias_generales`, `controles.<n>.copias` | Copias (CC) automáticas |
| `controles.<n>.notificacion` | Destinatarios y texto de la notificación del control |
| `controles.5.correo_formal` | Plantilla del correo por evento del Control 5 |
| `controles.7.aviso_gerentes` | Modo prueba, sincronización LDAP y texto del aviso del Control 7 |
| `automatico` | `activo`, `hora_desde` (`HH:MM`) y usuario de los envíos automáticos |
| `controles.<n>.calendario` | `recordatorios` (`MM-DD`), `fecha_tope`, `alerta_dias_antes`, `adjuntar_ultimo` |
| `controles.<n>.alerta` | Texto de la alerta de evidencia faltante |

**Envío automático**: un proceso dentro de la API revisa cada minuto y envía los recordatorios en
sus fechas (con hasta 7 días de gracia) y una alerta si, antes de la fecha tope, el período no
tiene evidencia. Cada envío usa una clave única en `SOX_MAIL_OUTBOX`, por lo que **nunca se repite**.
Con `automatico.activo = false` no se envía nada automáticamente.

Detalle técnico del correo: [`backend/README_CORREO_SOX.md`](backend/README_CORREO_SOX.md).

---

## Roles y permisos

| Rol | Acceso |
|---|---|
| `administrador` | SOX completo, Assets, administración de todos los usuarios, envíos de correo |
| `desarrollador` | SOX (evidencias) según permisos |
| `gerencial` | Control 7: valida solo las VPN de su gerencia |
| `assets_admin` | Assets completo y usuarios de Assets |
| `assets_viewer` | Assets solo lectura |

Una cuenta LDAP con credenciales correctas pero no activa en SOX recibe el aviso
"Cuenta no activa en SOX" (distinto de "Credenciales incorrectas").

---

## Despliegue

1. Generar el paquete desde la rama a publicar: `git archive --format=zip --prefix=sox-dashboard/ -o despliegue.zip HEAD`.
2. En el servidor, **conservar** los archivos que no viajan en git: `backend/.env`,
   `backend/config/*.json`, `backend/.venv` y `frontend/node_modules`.
3. Reemplazar el código, restaurar esos archivos y reiniciar la API (sin `--reload`).
4. Si hay scripts SQL nuevos, ejecutarlos antes de usar las funciones que los requieren.

La carpeta de evidencias (`SOX_EVIDENCE_DIR`) debe estar **fuera** del proyecto para no
perderla al reemplazar el código.

---

## Diagnóstico

Los envíos y sincronizaciones escriben trazas en la consola de uvicorn (`uvicorn.log` si se usa `nohup`):

| Prefijo | Qué muestra |
|---|---|
| `[SOX CORREO]` | Cada correo: inicio, resultado de Graph, duración y motivo de error; envíos automáticos |
| `[SOX CONTACTOS]` | Sincronización de correos de gerentes desde LDAP |
| `[SOX LDAP]` | Motivo de cada búsqueda LDAP fallida (sin contraseñas) |
| `[SOX GERENTES]` | Vínculo usuario ↔ gerente |

```bash
tail -f backend/uvicorn.log | grep -E "SOX CORREO|SOX CONTACTOS|SOX LDAP"
```

Comprobar la conexión con Microsoft Graph sin enviar correos:

```bash
<python con O365> backend/scripts/sox_graph_mail.py --script <ruta>/buzon.py diagnostico --emisor <buzón>
```

Comprobar que el código carga antes de reiniciar: `python -c "import main; print('OK')"`.

---

## Documentación adicional

| Documento | Tema |
|---|---|
| [`backend/README_CORREO_SOX.md`](backend/README_CORREO_SOX.md) | Correo formal, archivado como evidencia, `correos.json`, recordatorios |
| [`README_PERMISOS_HITSS.md`](README_PERMISOS_HITSS.md) | Jerarquía de roles y permisos |
| [`frontend/README_SEGURIDAD_XLSX.md`](frontend/README_SEGURIDAD_XLSX.md) | Sustitución de la librería `xlsx` por ExcelJS |
