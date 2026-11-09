#!/usr/bin/env python3
"""
sox_graph_mail - Envío y archivado de correos SOX mediante Microsoft Graph.

NO modifica el script corporativo buzon_prciaut.py: lo importa desde su ruta
para reutilizar exactamente la misma conexión (abrir_buzon), las mismas
credenciales (cred.json) y sus validaciones. Este archivo solo agrega lo que
SOX necesita y el script original no hace:

  - adjuntos,
  - una cabecera de correlación (x-sox-correlation) para ubicar la copia,
  - búsqueda del mensaje en Elementos enviados,
  - descarga del mensaje completo en formato MIME (.eml).

Se ejecuta con el intérprete que tiene instalada la librería O365
(SOX_GRAPH_PYTHON), igual que buzon_prciaut.py. FastAPI lo invoca como
subproceso; nunca recibe credenciales por la línea de comandos.

Uso:
  python sox_graph_mail.py --script /ruta/buzon_prciaut.py [-c cred.json] enviar      -m mensaje.json
  python sox_graph_mail.py --script /ruta/buzon_prciaut.py [-c cred.json] archivar    -m consulta.json
  python sox_graph_mail.py --script /ruta/buzon_prciaut.py [-c cred.json] diagnostico --emisor buzon@dominio [--probar-borrador]

Salida: UNA línea JSON por stdout. Los registros van por stderr.
Códigos: 0 = correcto, 1 = error, 3 = copia todavía no disponible en Enviados.

Permisos de aplicación necesarios en Microsoft Graph (limitados al buzón por
Application Access Policy):
  Mail.Send      -> enviar
  Mail.ReadWrite -> crear el mensaje con adjuntos, leer Enviados y descargar el MIME
"""
import argparse
import base64
import importlib.util
import json
import os
import sys
import time
from urllib.parse import quote

GRAPH = "https://graph.microsoft.com/v1.0"
CORRELATION_HEADER = "x-sox-correlation"
EXIT_NOT_FOUND = 3


def _out(data, code=0):
    sys.stdout.write(json.dumps(data, ensure_ascii=False) + "\n")
    sys.stdout.flush()
    return code


def _load_buzon(script_path):
    """Importa buzon_prciaut.py desde su ubicación sin copiarlo ni modificarlo."""
    if not os.path.isfile(script_path):
        raise FileNotFoundError(f"No existe el script corporativo: {script_path}")
    spec = importlib.util.spec_from_file_location("buzon_prciaut", script_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for name in ("abrir_buzon", "cargar_json", "construir_cuerpo", "a_lista", "validar_correos"):
        if not hasattr(module, name):
            raise RuntimeError(f"buzon_prciaut.py no expone '{name}'; revisar versión del script")
    return module


def _base(emisor):
    return f"{GRAPH}/users/{quote(emisor, safe='@')}"


def _id(value):
    return quote(value, safe="")


def _recipients(addresses):
    return [{"emailAddress": {"address": a}} for a in addresses]


def cmd_enviar(buzon, cred, mensaje):
    emisor = mensaje["emisor"].strip()
    destinatarios = buzon.a_lista(mensaje["destinatarios"])
    cc = buzon.a_lista(mensaje.get("cc"))
    correlacion = str(mensaje["correlacion"]).strip()
    formato = str(mensaje.get("formato", "texto")).lower()
    if not destinatarios:
        raise ValueError("La lista de destinatarios está vacía")
    if not correlacion.isalnum() or len(correlacion) > 64:
        raise ValueError("Correlación inválida")
    buzon.validar_correos([emisor], "emisor")
    buzon.validar_correos(destinatarios, "destinatarios")
    buzon.validar_correos(cc, "cc")

    attachments = []
    for item in mensaje.get("adjuntos") or []:
        with open(item["ruta"], "rb") as handle:
            content = handle.read()
        attachments.append({
            "@odata.type": "#microsoft.graph.fileAttachment",
            "name": item["nombre"],
            "contentType": item.get("content_type") or "application/octet-stream",
            "contentBytes": base64.b64encode(content).decode("ascii"),
        })

    payload = {
        "subject": mensaje["asunto"],
        "body": {"contentType": "HTML", "content": buzon.construir_cuerpo(mensaje["cuerpo"], formato)},
        "toRecipients": _recipients(destinatarios),
        "internetMessageHeaders": [{"name": CORRELATION_HEADER, "value": correlacion}],
    }
    if cc:
        payload["ccRecipients"] = _recipients(cc)
    if attachments:
        payload["attachments"] = attachments

    buzon.log(f"SOX: preparando '{mensaje['asunto']}' desde {emisor} ({len(attachments)} adjunto(s))")
    mailbox = buzon.abrir_buzon(cred, emisor)
    con = mailbox.con
    base = _base(emisor)

    # 1) Crear el mensaje (borrador) para conocer su internetMessageId antes de enviarlo.
    created = con.post(f"{base}/messages", data=payload).json()
    draft_id = created["id"]
    internet_id = created.get("internetMessageId")
    if not internet_id:
        detail = con.get(f"{base}/messages/{_id(draft_id)}",
                         params={"$select": "internetMessageId"}).json()
        internet_id = detail.get("internetMessageId")

    # 2) Enviar. Si falla, eliminar el borrador para no dejar residuos en el buzón.
    try:
        con.post(f"{base}/messages/{_id(draft_id)}/send")
    except Exception:
        try:
            con.delete(f"{base}/messages/{_id(draft_id)}")
        except Exception:
            buzon.log("SOX: no se pudo eliminar el borrador tras el error de envío")
        raise
    buzon.log(f"SOX: Graph aceptó el correo (correlación {correlacion})")
    return {"ok": True, "internet_message_id": internet_id, "correlacion": correlacion}


def _find_sent(con, base, internet_id, correlacion, desde):
    url = f"{base}/mailFolders/sentitems/messages"
    if internet_id:
        escaped = internet_id.replace("'", "''")
        found = con.get(url, params={
            "$filter": f"internetMessageId eq '{escaped}'",
            "$select": "id,internetMessageId,sentDateTime,subject",
        }).json().get("value", [])
        if found:
            return found[0]
    # Respaldo: revisar los últimos enviados desde la solicitud y comparar la cabecera.
    params = {
        "$select": "id,internetMessageId,sentDateTime,subject,internetMessageHeaders",
        "$orderby": "sentDateTime desc",
        "$top": "50",
    }
    if desde:
        params["$filter"] = f"sentDateTime ge {desde}"
    for item in con.get(url, params=params).json().get("value", []):
        for header in item.get("internetMessageHeaders") or []:
            if str(header.get("name", "")).lower() == CORRELATION_HEADER and header.get("value") == correlacion:
                return item
    return None


def cmd_archivar(buzon, cred, consulta):
    emisor = consulta["emisor"].strip()
    buzon.validar_correos([emisor], "emisor")
    salida = consulta["salida"]
    espera = max(0, min(int(consulta.get("espera_seg", 20)), 60))
    mailbox = buzon.abrir_buzon(cred, emisor)
    con = mailbox.con
    base = _base(emisor)

    limite = time.monotonic() + espera
    item = None
    while True:
        item = _find_sent(con, base, consulta.get("internet_message_id"),
                          str(consulta["correlacion"]), consulta.get("desde_utc"))
        if item or time.monotonic() >= limite:
            break
        time.sleep(4)
    if not item:
        return {"ok": False, "encontrado": False}, EXIT_NOT_FOUND

    mime = con.get(f"{base}/messages/{_id(item['id'])}/$value").content
    if not mime:
        raise RuntimeError("Graph devolvió un MIME vacío")
    fd = os.open(salida, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(mime)
    return {"ok": True, "encontrado": True, "graph_message_id": item["id"],
            "internet_message_id": item.get("internetMessageId"),
            "sent_datetime": item.get("sentDateTime"), "bytes": len(mime)}, 0


def cmd_diagnostico(buzon, cred, emisor, probar_borrador):
    """Comprueba permisos efectivos SIN enviar ningún correo."""
    buzon.validar_correos([emisor], "emisor")
    mailbox = buzon.abrir_buzon(cred, emisor)
    con = mailbox.con
    base = _base(emisor)
    result = {"ok": True, "emisor": emisor}
    sent = con.get(f"{base}/mailFolders/sentitems/messages",
                   params={"$top": "1", "$select": "id,sentDateTime"}).json().get("value", [])
    result["lectura_enviados"] = True
    if sent:
        mime = con.get(f"{base}/messages/{_id(sent[0]['id'])}/$value").content
        result["descarga_mime"] = bool(mime)
    if probar_borrador:
        draft = con.post(f"{base}/messages", data={
            "subject": "SOX diagnóstico (borrador, no se envía)",
            "body": {"contentType": "Text", "content": "Prueba de permisos"},
            "internetMessageHeaders": [{"name": CORRELATION_HEADER, "value": "diagnostico"}],
        }).json()
        con.delete(f"{base}/messages/{_id(draft['id'])}")
        result["crear_borrador"] = True
    return result


def main():
    parser = argparse.ArgumentParser(description="Envío/archivado de correos SOX vía Microsoft Graph")
    parser.add_argument("--script", required=True, help="Ruta de buzon_prciaut.py")
    parser.add_argument("-c", "--credenciales", default=None,
                        help="cred.json (por defecto, el de la carpeta de buzon_prciaut.py)")
    sub = parser.add_subparsers(dest="comando", required=True)
    p_env = sub.add_parser("enviar")
    p_env.add_argument("-m", "--mensaje", required=True)
    p_arc = sub.add_parser("archivar")
    p_arc.add_argument("-m", "--mensaje", required=True)
    p_diag = sub.add_parser("diagnostico")
    p_diag.add_argument("--emisor", required=True)
    p_diag.add_argument("--probar-borrador", action="store_true")
    args = parser.parse_args()

    try:
        buzon = _load_buzon(args.script)
        cred_path = args.credenciales or os.path.join(os.path.dirname(os.path.abspath(args.script)), "cred.json")
        if not os.path.isfile(cred_path):
            raise FileNotFoundError("No se encontró el archivo de credenciales de Graph")
        cred = buzon.cargar_json(cred_path, "credenciales")
        for key in ("tenant_id", "client_id", "client_secret"):
            if not cred.get(key):
                raise ValueError(f"Falta '{key}' en credenciales")

        if args.comando == "enviar":
            return _out(cmd_enviar(buzon, cred, buzon.cargar_json(args.mensaje, "mensaje")))
        if args.comando == "archivar":
            data, code = cmd_archivar(buzon, cred, buzon.cargar_json(args.mensaje, "consulta"))
            return _out(data, code)
        return _out(cmd_diagnostico(buzon, cred, args.emisor, args.probar_borrador))
    except Exception as exc:  # El backend registra el detalle; al usuario solo llega un mensaje genérico.
        sys.stderr.write(f"SOX Graph error: {type(exc).__name__}: {exc}\n")
        return _out({"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:300]}"}, 1)


if __name__ == "__main__":
    sys.exit(main())
