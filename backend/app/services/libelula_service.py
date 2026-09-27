"""Pago con QR a través de Libélula, pasarela de pagos boliviana (Manual de Integración v2.145).

El flujo tiene tres partes:
1. "Registrar deuda": se le manda a Libélula la venta y devuelve el QR Simple (PNG) y el link
   de su pasarela.
2. El cliente escanea el QR con la app de su banco.
3. Libélula llama a nuestro callback_url con ?transaction_id=... cuando se paga (con algunos
   bancos, horas después). Ese aviso no viene firmado, así que el pago siempre se confirma
   consultando la deuda con "consultar deudas por identificador".

Se llama directamente por HTTP con httpx, igual que ia_service.py: Libélula no tiene SDK.

Sin LIBELULA_APPKEY funciona en modo de prueba: no se llama a Libélula, se muestra un QR de
demostración y el pago se confirma con el botón "Simular pago" (para mostrar el flujo sin
tener cuenta de comercio)."""
import logging
import uuid
from datetime import date, timedelta
from typing import Optional

import httpx
import segno

from app.core.config import settings

logger = logging.getLogger(__name__)

_TIMEOUT_SEGUNDOS = 20.0


class LibelulaError(Exception):
    """Libélula no respondió o rechazó la solicitud."""


def modo_prueba() -> bool:
    return not settings.libelula_appkey


def identificador_de_pago(pago_id: int) -> str:
    """Identificador único de la deuda en Libélula. Sale del id del Pago, así que con el Pago
    (que el callback encuentra por transaction_id) siempre se sabe qué deuda consultar."""
    return f"FASHIONSTORE-PAGO-{pago_id}"


def _qr_data_uri(contenido: str) -> str:
    return segno.make(contenido, error="m").png_data_uri(scale=8, border=2)


def _hubo_error(valor) -> bool:
    # Según el servicio, "error" llega como 0/1, true/false o texto
    return str(valor).strip().lower() not in ("0", "false", "none", "")


def _post(ruta: str, cuerpo: dict) -> dict:
    url = settings.libelula_api_url.rstrip("/") + ruta
    try:
        respuesta = httpx.post(url, json=cuerpo, timeout=_TIMEOUT_SEGUNDOS)
        respuesta.raise_for_status()
        datos = respuesta.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("Libélula no respondió en %s: %s", ruta, exc)
        raise LibelulaError("No se pudo comunicar con Libélula. Inténtalo de nuevo en unos minutos.") from exc
    if not isinstance(datos, dict) or _hubo_error(datos.get("error")):
        mensaje = datos.get("mensaje") if isinstance(datos, dict) else None
        raise LibelulaError(mensaje or "Libélula rechazó la solicitud de pago.")
    return datos


def registrar_deuda(
    *,
    identificador: str,
    email_cliente: str,
    nombre_cliente: Optional[str],
    descripcion: str,
    lineas: list[dict],
) -> dict:
    """Registra la venta como deuda en Libélula. Devuelve id_transaccion, qr_url (imagen del
    QR: URL o data URI) y url_pasarela (None en modo de prueba)."""
    if modo_prueba():
        return {
            "id_transaccion": f"PRUEBA-{uuid.uuid4()}",
            "qr_url": _qr_data_uri(f"FASHIONSTORE|PAGO DE PRUEBA|{identificador}"),
            "url_pasarela": None,
        }

    datos = _post(
        "/rest/deuda/registrar",
        {
            "appkey": settings.libelula_appkey,
            "email_cliente": email_cliente,
            # El manual nombra este campo "identificador_deuda" en la tabla de parámetros e
            # "identificador" en todos sus ejemplos: se mandan los dos con el mismo valor.
            "identificador": identificador,
            "identificador_deuda": identificador,
            "descripcion": descripcion,
            "callback_url": f"{settings.backend_public_url.rstrip('/')}/api/v1/ventas/libelula/callback",
            "url_retorno": f"{settings.frontend_public_url.rstrip('/')}/mis-compras",
            "nombre_cliente": nombre_cliente or "",
            "moneda": "BOB",
            # Un QR de compra no debería quedar pagable para siempre
            "fecha_vencimiento": (date.today() + timedelta(days=1)).isoformat(),
            "lineas_detalle_deuda": lineas,
        },
    )
    id_transaccion = datos.get("id_transaccion")
    if not id_transaccion:
        raise LibelulaError(datos.get("mensaje") or "Libélula no devolvió el identificador de la transacción.")
    url_pasarela = datos.get("url_pasarela_pagos")
    qr_url = datos.get("qr_simple_url")
    if not qr_url and url_pasarela:
        # Comercio sin el canal QR Simple habilitado: QR con el link de la pasarela de Libélula,
        # que se abre con la cámara del celular y ahí se elige cómo pagar
        qr_url = _qr_data_uri(url_pasarela)
    if not qr_url:
        raise LibelulaError("Libélula no devolvió el QR ni el link de pago.")
    return {"id_transaccion": id_transaccion, "qr_url": qr_url, "url_pasarela": url_pasarela}


def consultar_deuda(identificador: str) -> Optional[dict]:
    """Estado real de la deuda en Libélula (pagado, valor_total, forma_pago, ...)."""
    datos = _post(
        "/rest/deuda/consultar_deudas/por_identificador",
        {"appkey": settings.libelula_appkey, "identificador": identificador},
    )
    deuda = datos.get("datos")
    if isinstance(deuda, list):
        return deuda[0] if deuda else None
    return deuda if isinstance(deuda, dict) else None
