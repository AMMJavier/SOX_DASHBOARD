# Correo formal SOX + archivado automático como evidencia (Controles 1, 2, 3 y 5)

Flujo: el responsable redacta el correo en **Control 1/2/3 → Evidencias → Enviar correo formal**
o, en el Control 5, en **Evidencias → abrir un evento → 3.1 Correo del evento**.
SOX lo envía desde el buzón corporativo (Microsoft Graph), localiza la copia en
*Elementos enviados*, guarda el **EML** original y un **PDF** legible en el repositorio
privado, y los registra como evidencias del control (estado `CARGADA`, pendiente de
verificación interna). Todo queda en `AUTOM.SOX_MAIL_OUTBOX` y en el historial del control.

| Control | Uso típico | Tipo de evidencia propuesto |
|---|---|---|
| 1 | Solicitar revisión/aprobación del SIS016 a Gerencia | Solicitud de actualización |
| 2 | Enviar el Plan de Seguridad anual a Jefatura/Gerencia | Revisión de Jefatura |
| 3 | Remitir avances semestrales o convocar la revisión | Matriz / informe de avances |
| 5 | Solicitar autorización o informar un alta/modificación/baja (por evento) | Solicitud (o Ejecución) |

**Control 5 (por evento):** el correo se envía desde el expediente de un evento, con
asunto y mensaje prellenados (operación, cuenta, perfil, fecha, ticket). El EML y el PDF
archivados quedan con el `EVENTO_ID` del expediente, igual que una evidencia cargada a
mano. Solo se pueden adjuntar evidencias **del mismo evento**. Los tipos permitidos son
*solicitud* y *ejecución*: el correo saliente **no** se registra como *aprobación*, porque
la aprobación la emite Jefatura; su respuesta se adjunta aparte y así el indicador
"Falta aprobación" no se da por cumplido con una simple solicitud.

**Adjuntar desde el repositorio:** el formulario permite adjuntar documentos ya
cargados en el control y año (sin volver a subirlos). El Control 3 puede adjuntar además
el **Plan de Seguridad verificado del Control 2**. Antes de adjuntar se comprueba el
SHA256 del archivo, y en el historial de la evidencia original queda
`DESCARGA — Adjuntada al correo SOX #N`. No se crean copias en Oracle.

**Control 3:** el aviso del plan de referencia incluye el botón **Descargar plan**, que
descarga el documento original del Control 2 (queda registrado en su historial).

`buzon_prciaut.py` **no se modifica**: `scripts/sox_graph_mail.py` lo importa y reutiliza
su conexión (`abrir_buzon`), su `cred.json` y sus validaciones.

## Archivos

| Archivo | Función |
|---|---|
| `backend/sql/sox_mail_outbox.sql` | Tabla `AUTOM.SOX_MAIL_OUTBOX` (estados y vínculo con evidencias) |
| `backend/sql/sox_mail_outbox_c5.sql` | Agrega `EVENTO_ID` (Control 5); ejecutar después del anterior |
| `frontend/src/components/SOX/control_5/Control5Events.jsx` | Panel "3.1 Correo del evento" en el expediente |
| `backend/sql/sox_mail_outbox_c7.sql` | Agrega `ID_CAMPANA`, `GERENTE`, `GERENTE_KEY` (Control 7) |
| `backend/services/sox_c7_notifications.py` | Cruce gerentes–contactos, vista previa y envío por lote |
| `backend/routes/SOX/control_7/notifications.py` | Rutas `/sox/campaign/notifications` |
| `backend/routes/SOX/control_7/campaigns.py` | El inicio de campaña ya no llama al mock: devuelve un resumen sin enviar |
| `frontend/src/components/SOX/control_7/CampaignNotifications.jsx` | Panel "Notificación a gerentes" en Campañas |
| `backend/scripts/sox_graph_mail.py` | Worker Graph: enviar con adjuntos, ubicar en Enviados, descargar EML, diagnóstico |
| `backend/services/sox_mail_service.py` | Validaciones, idempotencia, envío, archivado EML + PDF |
| `backend/routes/SOX/core/mail.py` | Rutas `/sox/controls/{control}/correos...` |
| `backend/routes/sox.py` | Registro del router (2 líneas) |
| `frontend/src/services/sox/controlMail.js` | Cliente API |
| `frontend/src/components/SOX/ControlMailPanel.jsx` | Formulario y tabla de correos enviados |
| `frontend/src/components/SOX/ControlWorkspace.jsx` | Muestra el panel en Evidencias de los Controles 1, 2 y 3; botón de descarga del plan C2 en C3 |

## Instalación en el servidor

1. **Respaldo** del código actual (como en etapas anteriores).
2. **Oracle**: ejecutar, en este orden y con el propietario de `AUTOM`:
   `sox_mail_outbox.sql`, `sox_mail_outbox_c5.sql` y `sox_mail_outbox_c7.sql`.
   **Los tres son necesarios** (el backend usa `EVENTO_ID` en todos los controles).
3. **Permisos Graph** (a confirmar con el senior). Además de `Mail.Send` (que ya usa el
   script), se necesita **`Mail.ReadWrite`** de aplicación, limitado al buzón con
   *Application Access Policy*, para crear el mensaje con adjuntos, leer Enviados y
   descargar el MIME.
4. **Permisos de archivos**: el usuario que ejecuta Uvicorn debe poder leer
   `buzon_prciaut.py` y `cred.json`, y **escribir** en la carpeta del token
   (`token_dir` de `cred.json`, por defecto la del script, archivo `o365_token.txt`).
5. **Variables en `backend/.env`** (dejar `SOX_MAIL_ENABLED=false` hasta la prueba):

   ```
   SOX_MAIL_ENABLED=false
   SOX_MAIL_SENDER=<buzón autorizado>
   SOX_MAIL_ALLOWED_DOMAINS=<dominios corporativos separados por coma>
   SOX_MAIL_CONTROLS=1,2,3,5,7
   SOX_PORTAL_URL=https://<servidor>:5173   # enlace del portal en el aviso del Control 7 (opcional)
   SOX_MAIL_MAX_ATTACH_MB=3
   SOX_MAIL_ARCHIVE_WAIT=20
   SOX_GRAPH_SCRIPT=/data/sisauto/buzon_prciaut/buzon_prciaut.py
   SOX_GRAPH_PYTHON=<ruta absoluta del python que tiene instalado O365>
   # Opcional: SOX_GRAPH_CREDENTIALS=<ruta absoluta de otro cred.json>
   ```
   Sin `SOX_MAIL_ALLOWED_DOMAINS` el envío queda bloqueado (no se permite enviar a
   cualquier dirección).
6. **Dependencias**: el backend ya usa `reportlab` (Control 6) y `python-multipart`
   (carga de evidencias). No se agregan paquetes nuevos.
7. Reiniciar el backend y compilar/publicar el frontend con el procedimiento habitual.

## Diagnóstico de permisos (no envía correos)

```bash
<SOX_GRAPH_PYTHON> backend/scripts/sox_graph_mail.py --script /data/sisauto/buzon_prciaut/buzon_prciaut.py diagnostico --emisor <buzón> --probar-borrador
```

Debe responder `{"ok": true, "lectura_enviados": true, "descarga_mime": true, "crear_borrador": true}`.
`--probar-borrador` crea y elimina un borrador para comprobar `Mail.ReadWrite`; no envía nada.

## Prueba controlada (correo de prueba autorizado)

1. `SOX_MAIL_ENABLED=true`, reiniciar backend.
2. Control 1 → Evidencias → *Enviar correo formal*: Para = correo de prueba, un PDF adjunto.
3. Esperado: mensaje "enviado y archivado"; en el repositorio aparecen dos evidencias
   (`.eml` y `.pdf`) con referencia `Correo SOX #N`; en Historial, dos `CARGA`.
4. Descargar el EML y abrirlo en Outlook: debe contener el adjunto.
5. Comprobar en Oracle:
   ```sql
   SELECT ID, ESTADO, DETALLE, INTERNET_MESSAGE_ID, EVIDENCIA_EML_ID, EVIDENCIA_PDF_ID
     FROM AUTOM.SOX_MAIL_OUTBOX ORDER BY ID DESC;
   ```
6. Si queda en `ACEPTADO` ("archivo pendiente"), usar **Reintentar archivado**: nunca reenvía.
7. Control 2: enviar con el plan marcado en *Adjuntar desde el repositorio*; el EML archivado debe
   contenerlo y el historial del plan debe mostrar `DESCARGA — Adjuntada al correo SOX #N`.
8. Control 3 (semestre 1 o 2): pulsar **Descargar plan**; luego enviar adjuntando el plan de C2 y
   comprobar que la evidencia queda en el semestre seleccionado.
9. Control 5: registrar un evento de prueba, abrirlo, enviar el correo prellenado. Esperado:
   el EML y el PDF aparecen en "3. Evidencias del evento #N" (tipo *solicitud*), el evento
   sigue mostrando **"Falta aprobación"** y `SELECT EVENTO_ID FROM AUTOM.SOX_MAIL_OUTBOX`
   devuelve el ID del evento. Luego adjuntar la respuesta de Jefatura como *aprobación*.
10. Para habilitar solo algunos controles, ajustar `SOX_MAIL_CONTROLS` (p. ej. `1`).

## Estados y reglas

- `PENDIENTE`: registrado, Graph no confirmó (p. ej. timeout). **Revisar Enviados antes de
  volver a enviar.**
- `ACEPTADO`: el correo salió; falta archivar. Reintentar solo el archivado.
- `ARCHIVANDO`: bloqueo de 5 minutos para que dos clics no generen evidencias dobles.
- `ARCHIVADO`: EML + PDF guardados como evidencia.
- `FALLIDO`: Graph rechazó el envío; no salió ningún correo.
- La clave de idempotencia del navegador impide que un doble clic envíe dos veces.
- "Aceptado por Graph" no significa recibido, leído ni aprobado. La respuesta de
  aprobación de Gerencia se sigue cargando como evidencia aparte (por ahora no se
  recupera automáticamente).

## Control 7: aviso de apertura de campaña a gerentes

- **Destinatarios**: solo los gerentes con VPN en la campaña ACTIVA (`CHECKPOINT_TRANSFORM`),
  agrupando escrituras distintas del mismo nombre (tildes, espacios, NBSP). El correo sale de
  `SOX_GERENTES_CONTACTO`; no se consulta LDAP al enviar.
- **Antes de enviar** (Campañas → *Notificación a gerentes*): gerentes listos, sin correo,
  con varios correos posibles (no se envía hasta corregir el contacto), dominio no permitido,
  y **registros sin gerente** de la campaña (para investigar la conciliación).
- **Mensaje**: período, cantidad de VPN del gerente, fecha límite y enlace al portal.
- **Sin duplicados**: un gerente notificado (`ACEPTADO`) o sin confirmar (`PENDIENTE`, p. ej.
  timeout) no recibe otro aviso. Solo los `FALLIDO` pueden reintentarse, como un nuevo
  intento auditado. Clave única `C7-<campaña>-<gerente>-<intento>`.
- **Envío en segundo plano**: la pantalla muestra el avance cada 5 s. Un solo lote a la vez
  por proceso de backend; con varios workers de Uvicorn la clave única sigue impidiendo duplicados.
- **Solo administrador**. No se envía si la fecha límite de la campaña ya venció.
- **Inicio de campaña**: `/sox/campaign/start` ya no llama al mock `email_service.py`; devuelve
  en `correo` un resumen de lo preparado, **sin enviar**. El envío automático al iniciar queda
  para cuando el cruce gerente–contacto esté validado en producción.
- Es una notificación, **no evidencia**: no se archiva como EML/PDF. La evidencia de revisión
  sigue siendo la validación del gerente en el portal.

Prueba controlada: con una campaña de prueba, revisar la vista previa (sin enviar) y corregir
contactos sin correo o ambiguos en `SOX_GERENTES_CONTACTO`; luego usar **Enviar** en una sola
fila (gerente de prueba) antes de **Notificar pendientes**. Verificar:

```sql
SELECT GERENTE, DESTINATARIOS, ESTADO, DETALLE, FECHA_ENVIO
  FROM AUTOM.SOX_MAIL_OUTBOX WHERE ORIGEN = 'CAMPANA' ORDER BY ID DESC;
```

## Formato MSG

Graph entrega el MIME (EML) de forma nativa; el EML abre en Outlook y conserva los
adjuntos. MSG requiere una conversión adicional que no está incluida.
