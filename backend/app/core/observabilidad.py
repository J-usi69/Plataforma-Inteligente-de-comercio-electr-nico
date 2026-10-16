"""Registro de cada pedido (método, ruta, estado, duración) con un id para rastrearlo, y una
respuesta genérica ante errores inesperados: el detalle va al log, nunca al cliente."""
import logging
import time
import uuid

from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("fashionstore")


def configurar_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


async def registrar_pedido(request: Request, call_next):
    # Si el proxy o el cliente ya mandan un id se respeta, así se sigue el mismo pedido de punta a punta
    request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
    request.state.request_id = request_id
    inicio = time.perf_counter()
    try:
        respuesta = await call_next(request)
    except Exception:
        logger.exception("%s %s falló [%s]", request.method, request.url.path, request_id)
        respuesta = JSONResponse(
            status_code=500,
            content={"detail": "Ocurrió un error inesperado. Intentá de nuevo.", "request_id": request_id},
        )
    duracion_ms = (time.perf_counter() - inicio) * 1000
    respuesta.headers["X-Request-ID"] = request_id
    logger.info("%s %s %s %.0fms [%s]", request.method, request.url.path, respuesta.status_code, duracion_ms, request_id)
    return respuesta
