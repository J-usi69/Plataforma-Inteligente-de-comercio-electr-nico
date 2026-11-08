"""Envío de correos con un adjunto (reportes exportados).

En la nube se usa la API HTTPS de Brevo, porque Railway bloquea el SMTP saliente en los planes
Trial y Hobby. En local se puede usar SMTP. Si no hay ninguno configurado se responde 503: el
resto del sistema sigue funcionando y el usuario puede descargar el reporte.
"""
import base64
import logging
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Optional

import httpx
from fastapi import HTTPException, status

from app.core.config import settings

log = logging.getLogger(__name__)
URL_BREVO = "https://api.brevo.com/v3/smtp/email"


@dataclass
class Adjunto:
    nombre: str
    contenido: bytes
    tipo_mime: str


def configurado() -> bool:
    return bool(settings.correo_remitente and (settings.brevo_api_key or settings.smtp_host))


def _por_brevo(destinatario: str, asunto: str, texto: str, html: str, adjunto: Optional[Adjunto]) -> None:
    cuerpo = {
        "sender": {"email": settings.correo_remitente, "name": "FashionStore"},
        "to": [{"email": destinatario}],
        "subject": asunto,
        "textContent": texto,
        "htmlContent": html,
    }
    if adjunto:
        cuerpo["attachment"] = [{"name": adjunto.nombre, "content": base64.b64encode(adjunto.contenido).decode()}]
    respuesta = httpx.post(URL_BREVO, json=cuerpo, headers={"api-key": settings.brevo_api_key}, timeout=20)
    if respuesta.status_code >= 300:
        log.warning("Brevo rechazó el correo (%s): %s", respuesta.status_code, respuesta.text[:300])
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="El servicio de correo rechazó el envío. Revisá el remitente configurado.")


def _por_smtp(destinatario: str, asunto: str, texto: str, html: str, adjunto: Optional[Adjunto]) -> None:
    mensaje = EmailMessage()
    mensaje["Subject"], mensaje["From"], mensaje["To"] = asunto, settings.correo_remitente, destinatario
    mensaje.set_content(texto)
    mensaje.add_alternative(html, subtype="html")
    if adjunto:
        principal, secundario = adjunto.tipo_mime.split("/", 1)
        mensaje.add_attachment(adjunto.contenido, maintype=principal, subtype=secundario, filename=adjunto.nombre)
    contexto = ssl.create_default_context()
    if settings.smtp_port == 465:
        servidor = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, context=contexto, timeout=20)
    else:
        servidor = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20)
        servidor.starttls(context=contexto)
    with servidor:
        if settings.smtp_user:
            servidor.login(settings.smtp_user, settings.smtp_password)
        servidor.send_message(mensaje)


def enviar(destinatario: str, asunto: str, texto: str, html: str, adjunto: Optional[Adjunto] = None) -> None:
    if not configurado():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El envío por correo no está configurado en el servidor. Descargá el reporte y envialo vos.",
        )
    try:
        if settings.brevo_api_key:
            _por_brevo(destinatario, asunto, texto, html, adjunto)
        else:
            _por_smtp(destinatario, asunto, texto, html, adjunto)
    except HTTPException:
        raise
    except (httpx.HTTPError, smtplib.SMTPException, OSError) as exc:
        log.warning("No se pudo enviar el correo a %s: %s", destinatario, exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="No se pudo enviar el correo: el servicio de correo no respondió.")
