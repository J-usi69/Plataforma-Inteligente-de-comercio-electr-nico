"""Integraciones con las APIs de IA usadas por el sistema (CU-28, CU-29, CU-30).
Se usan tres proveedores gratuitos distintos -uno por caso de uso- para no agotar
la cuota gratuita de uno solo repartiendo todo el tráfico en una sola API:
- Gemini (Google AI Studio) para recomendaciones (CU-28): es el de mayor volumen,
  se llama cada vez que un cliente entra al catálogo.
- Groq para el chat (CU-29): prioriza velocidad de respuesta para conversación en vivo.
- Mistral para reportes por IA (CU-30): lo usa solo el Administrador, ocasionalmente.
Se llama por HTTP directo con httpx en cada caso, sin agregar SDKs nuevos."""
import httpx

from app.core.config import settings

_TIMEOUT_SEGUNDOS = 20.0


class IAServiceError(Exception):
    """Se lanza cuando un servicio de IA no está configurado, no responde a
    tiempo, o devuelve un error. Cada endpoint decide cómo manejarla según la
    excepción documentada de su caso de uso (fallback o mensaje de limitación)."""


def _llamar_chat_compatible_openai(
    *, url: str, api_key: str, model: str, nombre_servicio: str,
    system_prompt: str, user_prompt: str, max_tokens: int,
    extra_campos: dict | None = None, historial: list[dict] | None = None,
) -> str:
    """Groq y Mistral exponen una API de chat compatible con el formato de OpenAI."""
    if not api_key:
        raise IAServiceError(f"El servicio de IA ({nombre_servicio}) no está configurado")

    mensajes = [{"role": "system", "content": system_prompt}]
    if historial:
        mensajes.extend(historial)
    mensajes.append({"role": "user", "content": user_prompt})

    try:
        respuesta = httpx.post(
            url,
            headers={"Authorization": f"Bearer {api_key}", "content-type": "application/json"},
            json={
                "model": model,
                "max_tokens": max_tokens,
                "messages": mensajes,
                **(extra_campos or {}),
            },
            timeout=_TIMEOUT_SEGUNDOS,
        )
    except httpx.TimeoutException as exc:
        raise IAServiceError(f"El servicio de IA ({nombre_servicio}) no respondió a tiempo") from exc
    except httpx.HTTPError as exc:
        raise IAServiceError(f"No se pudo contactar a {nombre_servicio}: {exc}") from exc

    if respuesta.status_code != 200:
        raise IAServiceError(f"{nombre_servicio} respondió con error {respuesta.status_code}: {respuesta.text}")

    try:
        return respuesta.json()["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, ValueError, TypeError) as exc:
        raise IAServiceError(f"Respuesta inesperada de {nombre_servicio}") from exc


def llamar_groq(system_prompt: str, user_prompt: str, max_tokens: int = 500, historial: list[dict] | None = None) -> str:
    """CU-29: asistente conversacional. Usa Groq por su baja latencia."""
    return _llamar_chat_compatible_openai(
        url="https://api.groq.com/openai/v1/chat/completions",
        api_key=settings.groq_api_key,
        model=settings.groq_model,
        nombre_servicio="Groq",
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        max_tokens=max_tokens,
        historial=historial,
        # reasoning_effort "low": el modelo gpt-oss de Groq por defecto gasta parte
        # de max_tokens "razonando" antes de responder (visible aparte, en el campo
        # "reasoning"), lo que cortaba respuestas cortas a mitad de frase.
        extra_campos={"reasoning_effort": "low"},
    )


def llamar_mistral(system_prompt: str, user_prompt: str, max_tokens: int = 500) -> str:
    """CU-30: reportes por IA. Uso ocasional del Administrador."""
    return _llamar_chat_compatible_openai(
        url="https://api.mistral.ai/v1/chat/completions",
        api_key=settings.mistral_api_key,
        model=settings.mistral_model,
        nombre_servicio="Mistral",
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        max_tokens=max_tokens,
    )


def llamar_gemini(system_prompt: str, user_prompt: str, max_tokens: int = 500) -> str:
    """CU-28: recomendaciones de prendas. Es el de mayor volumen de llamadas."""
    if not settings.gemini_api_key:
        raise IAServiceError("El servicio de IA (Gemini) no está configurado")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.gemini_model}:generateContent"
    try:
        respuesta = httpx.post(
            url,
            params={"key": settings.gemini_api_key},
            headers={"content-type": "application/json"},
            json={
                "system_instruction": {"parts": [{"text": system_prompt}]},
                "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
                # thinkingBudget en 0: los modelos Gemini recientes gastan tokens en
                # razonamiento interno antes de responder, y para textos cortos
                # (recomendaciones, chat, reportes) eso agotaba max_tokens sin llegar
                # a generar contenido visible (finishReason MAX_TOKENS, content vacío).
                "generationConfig": {
                    "maxOutputTokens": max_tokens,
                    "thinkingConfig": {"thinkingBudget": 0},
                },
            },
            timeout=_TIMEOUT_SEGUNDOS,
        )
    except httpx.TimeoutException as exc:
        raise IAServiceError("El servicio de IA (Gemini) no respondió a tiempo") from exc
    except httpx.HTTPError as exc:
        raise IAServiceError(f"No se pudo contactar a Gemini: {exc}") from exc

    if respuesta.status_code != 200:
        raise IAServiceError(f"Gemini respondió con error {respuesta.status_code}: {respuesta.text}")

    try:
        partes = respuesta.json()["candidates"][0]["content"]["parts"]
        return "".join(p.get("text", "") for p in partes).strip()
    except (KeyError, IndexError, ValueError, TypeError) as exc:
        raise IAServiceError("Respuesta inesperada de Gemini") from exc
