"""Respuestas a correos SOX con código: se leen del buzón y se archivan como evidencia.

Flujo:
  1. Correos con código (SOX_MAIL_OUTBOX.CODIGO) aún no aprobados -> se pide al worker
     Graph (scripts/sox_graph_mail.py respuestas) los mensajes de la Bandeja de entrada
     cuyo asunto lleve "[SOX <código>]".
  2. Cada respuesta nueva se guarda en el repositorio (formato de formatos.json) y en
     AUTOM.SOX_MAIL_RESPUESTAS, asociada al correo original.
  3. Si la respuesta la envía un destinatario (Para/CC) del correo y su texto nuevo
     contiene una palabra de aprobación ("OK"...), el correo pasa a APROBADO y sus
     evidencias quedan VERIFICADAS. Si no, queda RESPONDIDO para revisión manual.

Se ejecuta cada N minutos (formatos.json > revision_respuestas_min) y con el botón
"Buscar respuestas". Un candado evita dos revisiones simultáneas en el mismo proceso y la
clave única GRAPH_MESSAGE_ID evita registrar dos veces la misma respuesta.
"""
from __future__ import annotations  # Python 3.9 en el servidor

from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import threading
import time
import unicodedata

from fastapi import HTTPException
from sqlalchemy import Integer, outparam, text
from sqlalchemy.exc import IntegrityError

from routes.sox.common.evidence import EVIDENCE_TYPES, MAX_BYTES
from services.sox.common import mail_codes
from services.sox.common import mail_service as mail

LOOKBACK_DAYS = 180
NOTA_RESPUESTA = ("Representación PDF de la respuesta recibida en el buzón SOX (Microsoft Graph). "
                  "El código del asunto la asocia al correo enviado desde la plataforma.")
_run_lock = threading.Lock()
_started = False
_start_lock = threading.Lock()


def _parse_utc(value):
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc).replace(tzinfo=None)
    except (TypeError, ValueError):
        return mail._now()


def _normalize(value):
    value = unicodedata.normalize("NFKD", str(value or "")).casefold()
    return "".join(c for c in value if not unicodedata.combining(c))


def approves(texto, palabras):
    """True si el texto nuevo de la respuesta contiene una palabra de aprobación como palabra completa."""
    body = _normalize(texto)
    return any(re.search(rf"(?<![a-z0-9]){re.escape(_normalize(w))}(?![a-z0-9])", body) for w in palabras)


def _addresses(*values):
    found = set()
    for value in values:
        for item in re.split(r"[,;\s]+", value or ""):
            if "@" in item:
                found.add(item.strip().casefold())
    return found


def _pending(db, controls):
    params = {f"c{i}": c for i, c in enumerate(sorted(controls))}
    params["p_desde"] = mail._now() - timedelta(days=LOOKBACK_DAYS)
    rows = db.execute(text(f"""
        SELECT ID AS "id", CONTROL_NUMERO AS "control", ANIO AS "anio", SEMESTRE AS "semestre",
               CODIGO AS "codigo", EMISOR AS "emisor", DESTINATARIOS AS "destinatarios", CC AS "cc",
               ESTADO AS "estado", ORIGEN AS "origen", FECHA_ENVIO AS "fecha_envio",
               SOLICITADO_POR AS "solicitado_por", EVIDENCIA_EML_ID AS "eml_id", EVIDENCIA_PDF_ID AS "pdf_id"
          FROM AUTOM.SOX_MAIL_OUTBOX
         WHERE CODIGO IS NOT NULL AND ESTADO IN ('ACEPTADO', 'ARCHIVADO')
           AND NVL(ESTADO_RESPUESTA, 'PENDIENTE') <> 'APROBADO'
           AND FECHA_ENVIO >= :p_desde
           AND CONTROL_NUMERO IN ({', '.join(':' + k for k in params if k.startswith('c'))})
    """), params).mappings()
    return [dict(r) for r in rows]


def _verify_evidences(db, evidence_ids, user_id, detail):
    for evidence_id in [x for x in evidence_ids if x]:
        updated = db.execute(text("""
            UPDATE AUTOM.SOX_CONTROL_EVIDENCIAS SET ESTADO = 'VERIFICADA', VERIFICADO_POR = :p_user, VERIFICADO_EN = :p_now
             WHERE ID = :p_id AND ESTADO = 'CARGADA'
        """), {"p_user": user_id, "p_now": mail._now(), "p_id": evidence_id})
        if updated.rowcount:
            db.execute(text("""
                INSERT INTO AUTOM.SOX_CONTROL_EVIDENCIA_AUD (EVIDENCIA_ID, ACCION, USUARIO_ID, FECHA, DETALLE)
                VALUES (:p_id, 'VERIFICACION', :p_user, :p_now, :p_det)
            """), {"p_id": evidence_id, "p_user": user_id, "p_now": mail._now(), "p_det": detail[:500]})


def _reply_evidence_ids(db, outbox_id):
    return [r[0] for r in db.execute(text(
        "SELECT EVIDENCIA_ID FROM AUTOM.SOX_MAIL_RESPUESTAS WHERE OUTBOX_ID = :p_id AND EVIDENCIA_ID IS NOT NULL"),
        {"p_id": outbox_id})]


def _register(db, outbox, reply, cfg):
    """Guarda una respuesta como evidencia y actualiza el estado del correo. Devuelve 'APROBADO', 'RESPONDIDO' o None."""
    eml = Path(reply["archivo"]).read_bytes()
    if not eml or len(eml) > MAX_BYTES:
        mail.console(f"RESPUESTAS {outbox['codigo']}: respuesta vacía o mayor a 15 MB; no se registra")
        return None
    remitente = (reply.get("remitente") or "").strip()[:254]
    allowed = _addresses(outbox["destinatarios"], outbox["cc"])
    aprueba = remitente.casefold() in allowed and approves(reply.get("texto"), cfg["palabras_aprobacion"])
    received = _parse_utc(reply.get("recibido"))
    control = outbox["control"]
    tipo = cfg["tipo_evidencia_respuesta"]
    if tipo not in EVIDENCE_TYPES.get(control, ()):
        tipo = sorted(EVIDENCE_TYPES.get(control, {"aprobacion"}))[0]
    fmt = cfg["formato_archivo"]
    safe_from = re.sub(r"[^A-Za-z0-9_-]+", "_", remitente.split("@")[0])[:40] or "remitente"
    base_name = f"Control{control}_Respuesta_{outbox['codigo']}_{received:%Y%m%d_%H%M%S}_{safe_from}"
    common = {"control": control, "anio": outbox["anio"], "semestre": outbox["semestre"], "tipo": tipo,
              "referencia": f"Respuesta a {outbox['codigo']} · {remitente}"[:250],
              "observaciones": ("Respuesta recibida en el buzón SOX y archivada automáticamente. "
                                + ("Contiene aprobación (OK) de un destinatario." if aprueba
                                   else "Sin aprobación automática: requiere revisión.")),
              "autor": outbox["solicitado_por"], "actor": outbox["solicitado_por"], "outbox_id": outbox["id"]}
    stored = []
    try:
        evidence_id = None
        if fmt in ("pdf", "ambos"):
            pdf = mail.eml_to_pdf(eml, outbox_id=outbox["id"], control=control,
                                  titulo=f"Respuesta al correo {outbox['codigo']}", nota=NOTA_RESPUESTA)
            evidence_id = mail._store_evidence(db, stored, filename=f"{base_name}.pdf", content=pdf, **common)
        if fmt in ("eml", "ambos"):
            eml_id = mail._store_evidence(db, stored, filename=f"{base_name}.eml", content=eml, **common)
            evidence_id = evidence_id or eml_id
        db.execute(text("""
            INSERT INTO AUTOM.SOX_MAIL_RESPUESTAS
              (OUTBOX_ID, GRAPH_MESSAGE_ID, INTERNET_MESSAGE_ID, REMITENTE, ASUNTO, FECHA_RECIBIDO,
               EXTRACTO, APRUEBA, EVIDENCIA_ID, REGISTRADO_EN)
            VALUES (:p_out, :p_gid, :p_imid, :p_from, :p_subject, :p_received, :p_text, :p_ok, :p_evid, :p_now)
        """), {"p_out": outbox["id"], "p_gid": reply["graph_message_id"][:500],
               "p_imid": (reply.get("internet_message_id") or "")[:500] or None, "p_from": remitente or None,
               "p_subject": (reply.get("asunto") or "")[:255] or None, "p_received": received,
               "p_text": " ".join(str(reply.get("texto") or "").split())[:600] or None,
               "p_ok": 1 if aprueba else 0, "p_evid": evidence_id, "p_now": mail._now()})
        estado = "APROBADO" if aprueba else "RESPONDIDO"
        db.execute(text("""
            UPDATE AUTOM.SOX_MAIL_OUTBOX SET ESTADO_RESPUESTA = :p_estado, FECHA_RESPUESTA = :p_received
             WHERE ID = :p_id AND NVL(ESTADO_RESPUESTA, 'PENDIENTE') <> 'APROBADO'
        """), {"p_estado": estado, "p_received": received, "p_id": outbox["id"]})
        if aprueba:
            _verify_evidences(db, [outbox["pdf_id"], outbox["eml_id"]] + _reply_evidence_ids(db, outbox["id"]),
                              outbox["solicitado_por"],
                              f"Aprobado por respuesta de {remitente} al correo {outbox['codigo']} (palabra de aprobación detectada)")
        db.commit()
        stored.clear()
        return estado
    except IntegrityError:  # La misma respuesta ya fue registrada (otra revisión simultánea).
        db.rollback()
        return None
    except Exception:
        db.rollback()
        raise
    finally:
        for path in stored:
            path.unlink(missing_ok=True)


def check_replies(db, controls=None):
    """Revisa el buzón y registra las respuestas nuevas. Devuelve un resumen."""
    summary = {"revisados": 0, "nuevas": 0, "aprobados": 0, "por_revisar": 0}
    if not mail._env_bool("SOX_MAIL_ENABLED"):
        raise HTTPException(503, "Envíos deshabilitados (SOX_MAIL_ENABLED): no se consulta el buzón")
    active = mail_codes.reply_controls() if controls is None else set(controls) & mail_codes.reply_controls()
    if not active:
        return summary
    if not _run_lock.acquire(blocking=False):
        raise HTTPException(409, "Ya hay una búsqueda de respuestas en curso; intenta en unos segundos.")
    try:
        pending = _pending(db, active)
        # Notificaciones con código cuyo archivado quedó pendiente: se reintenta aquí.
        for item in [p for p in pending if p["estado"] == "ACEPTADO"]:
            try:
                from types import SimpleNamespace
                result = mail.archive_mail(db, control=item["control"], outbox_id=item["id"],
                                           user=SimpleNamespace(id=item["solicitado_por"], username="sistema"))
                item["pdf_id"], item["eml_id"] = result.get("evidencia_pdf_id"), result.get("evidencia_eml_id")
            except HTTPException:
                pass
        summary["revisados"] = len(pending)
        if not pending:
            return summary
        by_sender = {}
        for item in pending:
            by_sender.setdefault(item["emisor"], []).append(item)
        for emisor, items in by_sender.items():
            codes = {i["codigo"].casefold(): i for i in items}
            since = min(i["fecha_envio"] for i in items) - timedelta(minutes=1)
            known = [r[0] for r in db.execute(text("""
                SELECT r.GRAPH_MESSAGE_ID FROM AUTOM.SOX_MAIL_RESPUESTAS r
                  JOIN AUTOM.SOX_MAIL_OUTBOX o ON o.ID = r.OUTBOX_ID
                 WHERE r.FECHA_RECIBIDO >= :p_desde AND o.EMISOR = :p_emisor
            """), {"p_desde": since, "p_emisor": emisor})]
            outdir = tempfile.mkdtemp(prefix="sox_resp_")
            os.chmod(outdir, 0o700)
            try:
                try:
                    code, out = mail._run_worker("respuestas", {
                        "emisor": emisor, "codigos": [i["codigo"] for i in items], "excluir": known,
                        "desde_utc": since.strftime("%Y-%m-%dT%H:%M:%SZ"), "salida_dir": outdir, "max": 30,
                    }, timeout=150)
                except subprocess.TimeoutExpired:
                    raise HTTPException(504, "Graph no respondió a tiempo al buscar respuestas")
                if code != 0 or not out.get("ok"):
                    mail.logger.error("Búsqueda de respuestas falló: %s", out.get("error"))
                    raise HTTPException(502, "No se pudo consultar la bandeja de entrada en Microsoft Graph")
                mail.console(f"RESPUESTAS buzón {emisor}: códigos={[i['codigo'] for i in items]} "
                             f"desde={since:%Y-%m-%d %H:%M:%S} UTC | encontradas={len(out.get('respuestas') or [])} "
                             f"| diagnóstico={out.get('diagnostico')}")
                # Las más antiguas primero: el orden de llegada define el estado final.
                for reply in sorted(out.get("respuestas") or [], key=lambda r: str(r.get("recibido") or "")):
                    outbox = codes.get(str(reply.get("codigo") or "").casefold())
                    if not outbox:
                        continue
                    cfg = mail_codes.settings(outbox["control"])
                    estado = _register(db, outbox, reply, cfg)
                    if estado:
                        summary["nuevas"] += 1
                        mail.console(f"RESPUESTAS {outbox['codigo']}: respuesta de {reply.get('remitente')} -> {estado}")
                        if estado == "APROBADO":
                            summary["aprobados"] += 1
                            codes.pop(outbox["codigo"].casefold(), None)  # Ya aprobado: no cambia más.
                        else:
                            summary["por_revisar"] += 1
            finally:
                shutil.rmtree(outdir, ignore_errors=True)
        return summary
    finally:
        _run_lock.release()


def approve_manual(db, *, control, outbox_id, user):
    """Aprobación manual (administrador) de un correo RESPONDIDO sin "OK" automático."""
    row = db.execute(text("""
        SELECT CODIGO AS "codigo", ESTADO_RESPUESTA AS "estado_respuesta", EVIDENCIA_PDF_ID AS "pdf_id",
               EVIDENCIA_EML_ID AS "eml_id"
          FROM AUTOM.SOX_MAIL_OUTBOX WHERE ID = :p_id AND CONTROL_NUMERO = :p_control
    """), {"p_id": outbox_id, "p_control": control}).mappings().first()
    if not row or not row["codigo"]:
        raise HTTPException(404, "Correo con código inexistente")
    if row["estado_respuesta"] != "RESPONDIDO":
        raise HTTPException(409, "Solo se aprueba manualmente un correo que ya tiene respuesta")
    db.execute(text("UPDATE AUTOM.SOX_MAIL_OUTBOX SET ESTADO_RESPUESTA = 'APROBADO' WHERE ID = :p_id"),
               {"p_id": outbox_id})
    _verify_evidences(db, [row["pdf_id"], row["eml_id"]] + _reply_evidence_ids(db, outbox_id), user.id,
                      f"Aprobación manual del correo {row['codigo']} por {user.username} tras revisar la respuesta")
    db.commit()
    return {"id": outbox_id, "codigo": row["codigo"], "estado_respuesta": "APROBADO"}


# ---------------------------------------------------------------- revisión periódica

def _loop():
    time.sleep(30)
    while True:
        try:
            if mail._env_bool("SOX_MAIL_ENABLED") and mail_codes.reply_controls():
                from database.oracle_database import SessionLocal
                db = SessionLocal()
                try:
                    result = check_replies(db)
                    if result["nuevas"]:
                        mail.console(f"RESPUESTAS: revisión automática -> {result}")
                finally:
                    db.close()
        except HTTPException as exc:
            if exc.status_code != 409:
                mail.console(f"RESPUESTAS: revisión automática no completada | HTTP {exc.status_code}: {exc.detail}")
        except Exception as exc:
            mail.console(f"RESPUESTAS: error en la revisión automática | {type(exc).__name__}: {exc}")
        time.sleep(mail_codes.check_minutes() * 60)


def start():
    """Arranca la revisión periódica una sola vez por proceso."""
    global _started
    with _start_lock:
        if _started:
            return
        _started = True
    mail.console(f"RESPUESTAS: revisión del buzón cada {mail_codes.check_minutes()} min "
                 f"(controles {sorted(mail_codes.reply_controls()) or 'ninguno'})")
    threading.Thread(target=_loop, name="sox-respuestas", daemon=True).start()
