"""Notificaciones push a la app móvil vía Firebase Cloud Messaging (API HTTP v1).
Se llama directamente por HTTP con httpx (mismo criterio que ia_service.py) y solo se
usa `google-auth` para firmar el JWT de la cuenta de servicio y obtener el access token
de OAuth2 -no se agrega el SDK completo de firebase-admin.

Un push es siempre una notificación secundaria de un flujo principal (confirmar una
reserva, aprobar un pago, publicar una prenda...). Por eso ninguna función de este
módulo relanza excepciones: cualquier fallo se registra en el log y se ignora, para
que jamás rompa el flujo que la disparó."""
import json
import logging
from datetime import datetime, timezone
from typing import Optional

import httpx
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2 import service_account
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.seguridad import PushToken, Rol, Usuario, UsuarioRol

logger = logging.getLogger(__name__)

_SCOPES = ["https://www.googleapis.com/auth/firebase.messaging"]
_TIMEOUT_SEGUNDOS = 10.0

_credenciales: Optional[service_account.Credentials] = None


def _proyecto_id() -> Optional[str]:
    if not settings.firebase_credentials_json:
        return None
    try:
        return json.loads(settings.firebase_credentials_json).get("project_id")
    except (json.JSONDecodeError, TypeError):
        logger.exception("FIREBASE_CREDENTIALS_JSON no es un JSON válido")
        return None


def _access_token() -> Optional[str]:
    global _credenciales
    if not settings.firebase_credentials_json:
        return None
    try:
        if _credenciales is None:
            info = json.loads(settings.firebase_credentials_json)
            _credenciales = service_account.Credentials.from_service_account_info(info, scopes=_SCOPES)
        if not _credenciales.valid:
            _credenciales.refresh(GoogleAuthRequest())
        return _credenciales.token
    except Exception:
        logger.exception("No se pudo obtener el access token de Firebase")
        return None


def _enviar_a_token(
    token: str, titulo: str, cuerpo: str, data: Optional[dict],
    access_token: str, project_id: str,
) -> str:
    """Devuelve 'ok', 'invalido' (el token ya no sirve, se puede borrar) o 'error' (fallo transitorio)."""
    mensaje = {
        "message": {
            "token": token,
            "notification": {"title": titulo, "body": cuerpo},
            "data": {k: str(v) for k, v in (data or {}).items()},
        }
    }
    try:
        respuesta = httpx.post(
            f"https://fcm.googleapis.com/v1/projects/{project_id}/messages:send",
            headers={"Authorization": f"Bearer {access_token}", "content-type": "application/json"},
            json=mensaje,
            timeout=_TIMEOUT_SEGUNDOS,
        )
    except httpx.HTTPError:
        logger.exception("No se pudo contactar a Firebase Cloud Messaging")
        return "error"

    if respuesta.status_code == 200:
        return "ok"
    if respuesta.status_code in (400, 404):
        # INVALID_ARGUMENT / UNREGISTERED: el token ya no es válido (token rotado, app desinstalada, etc.)
        return "invalido"
    logger.warning("FCM respondió %s: %s", respuesta.status_code, respuesta.text)
    return "error"


def _enviar_a_usuarios(db: Session, usuario_ids: list[int], titulo: str, cuerpo: str, data: Optional[dict] = None) -> None:
    try:
        access_token = _access_token()
        project_id = _proyecto_id()
        if not access_token or not project_id or not usuario_ids:
            return

        tokens = db.scalars(select(PushToken).where(PushToken.usuario_id.in_(usuario_ids))).all()
        invalidos = []
        for pt in tokens:
            estado = _enviar_a_token(pt.token, titulo, cuerpo, data, access_token, project_id)
            if estado == "invalido":
                invalidos.append(pt.token)

        if invalidos:
            db.query(PushToken).filter(PushToken.token.in_(invalidos)).delete(synchronize_session=False)
            db.commit()
    except Exception:
        logger.exception("Fallo inesperado enviando notificaciones push")


def enviar_push_a_usuario(db: Session, usuario_id: int, titulo: str, cuerpo: str, data: Optional[dict] = None) -> None:
    _enviar_a_usuarios(db, [usuario_id], titulo, cuerpo, data)


def enviar_push_a_administradores(db: Session, titulo: str, cuerpo: str, data: Optional[dict] = None) -> None:
    try:
        admin_ids = list(db.scalars(
            select(Usuario.id)
            .join(UsuarioRol, UsuarioRol.usuario_id == Usuario.id)
            .join(Rol, Rol.id == UsuarioRol.rol_id)
            .where(Rol.nombre == "Administrador", Usuario.estado.is_(True))
        ))
        _enviar_a_usuarios(db, admin_ids, titulo, cuerpo, data)
    except Exception:
        logger.exception("Fallo inesperado buscando administradores para notificar")


def enviar_push_broadcast_clientes(db: Session, titulo: str, cuerpo: str, data: Optional[dict] = None) -> None:
    try:
        cliente_ids = list(db.scalars(
            select(Usuario.id)
            .join(UsuarioRol, UsuarioRol.usuario_id == Usuario.id)
            .join(Rol, Rol.id == UsuarioRol.rol_id)
            .where(Rol.nombre == "Cliente", Usuario.estado.is_(True))
        ))
        _enviar_a_usuarios(db, cliente_ids, titulo, cuerpo, data)
    except Exception:
        logger.exception("Fallo inesperado buscando clientes para notificar")


def registrar_o_actualizar_token(db: Session, usuario_id: int, token: str, plataforma: str) -> None:
    ahora = datetime.now(timezone.utc)
    existente = db.scalars(select(PushToken).where(PushToken.token == token)).first()
    if existente:
        existente.usuario_id = usuario_id
        existente.plataforma = plataforma
        existente.actualizado_en = ahora
    else:
        db.add(PushToken(
            usuario_id=usuario_id, token=token, plataforma=plataforma,
            creado_en=ahora, actualizado_en=ahora,
        ))
    db.commit()
