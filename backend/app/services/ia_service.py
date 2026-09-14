"""Integración con la API de Mensajes de Anthropic (Claude), usada por las
funcionalidades de IA del sistema (CU-28, CU-29, CU-30). Se llama directamente
por HTTP con httpx en vez de agregar el SDK de Anthropic como dependencia."""
import httpx

from app.core.config import settings

_ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
_ANTHROPIC_VERSION = "2023-06-01"
_TIMEOUT_SEGUNDOS = 20.0


class IAServiceError(Exception):
    """Se lanza cuando el servicio de IA no está configurado, no responde a
    tiempo, o devuelve un error. Cada endpoint decide cómo manejarla según la
    excepción documentada de su caso de uso (fallback o mensaje de limitación)."""


def llamar_claude(system_prompt: str, user_prompt: str, max_tokens: int = 500) -> str:
    if not settings.anthropic_api_key:
        raise IAServiceError("El servicio de IA no está configurado (falta ANTHROPIC_API_KEY)")

    try:
        respuesta = httpx.post(
            _ANTHROPIC_URL,
            headers={
                "x-api-key": settings.anthropic_api_key,
                "anthropic-version": _ANTHROPIC_VERSION,
                "content-type": "application/json",
            },
            json={
                "model": settings.anthropic_model,
                "max_tokens": max_tokens,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_prompt}],
            },
            timeout=_TIMEOUT_SEGUNDOS,
        )
    except httpx.TimeoutException as exc:
        raise IAServiceError("El servicio de IA no respondió a tiempo") from exc
    except httpx.HTTPError as exc:
        raise IAServiceError(f"No se pudo contactar al servicio de IA: {exc}") from exc

    if respuesta.status_code != 200:
        raise IAServiceError(f"El servicio de IA respondió con error {respuesta.status_code}: {respuesta.text}")

    try:
        bloques = respuesta.json()["content"]
        return "".join(b.get("text", "") for b in bloques if b.get("type") == "text").strip()
    except (KeyError, ValueError, TypeError) as exc:
        raise IAServiceError("Respuesta inesperada del servicio de IA") from exc
