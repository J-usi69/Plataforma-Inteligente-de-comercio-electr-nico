import io

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from PIL import Image, ImageOps
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import settings
from app.models.catalogo import Prenda
from app.schemas.vestidor_ar import TryOnCapabilities, TryOnJobOut

router = APIRouter()

MAX_INPUT_BYTES = 5 * 1024 * 1024  # 5 MB, igual que el límite usado en la referencia (VÉLORA)

_STATUS_MAP = {
    "starting": "QUEUED",
    "queued": "QUEUED",
    "pending": "QUEUED",
    "processing": "PROCESSING",
    "running": "PROCESSING",
    "succeeded": "SUCCEEDED",
    "success": "SUCCEEDED",
    "completed": "SUCCEEDED",
    "canceled": "CANCELLED",
    "cancelled": "CANCELLED",
    "failed": "FAILED",
    "error": "FAILED",
}


def _detect_image_type(content: bytes) -> str | None:
    if content[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if content[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp"
    return None


def _normalizar_orientacion(content: bytes) -> bytes:
    """Las cámaras de celular suelen guardar los píxeles en la orientación cruda del
    sensor y solo un tag EXIF indicando cómo rotarla para verse derecha. Replicate
    ignora ese tag y procesa los píxeles tal cual, por eso el resultado de la IA
    salía "de costado". Acá se aplica la rotación real sobre los píxeles antes de
    enviarla, y se reencodea siempre a JPEG."""
    imagen = Image.open(io.BytesIO(content))
    imagen = ImageOps.exif_transpose(imagen)
    if imagen.mode not in ("RGB", "L"):
        imagen = imagen.convert("RGB")
    buffer = io.BytesIO()
    imagen.save(buffer, format="JPEG", quality=95)
    return buffer.getvalue()


def _replicate_client():
    try:
        from replicate.client import Client
    except ImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="La dependencia 'replicate' no está instalada en el backend",
        ) from exc

    if not settings.replicate_api_token.strip():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El vestidor virtual no está configurado (falta REPLICATE_API_TOKEN)",
        )

    return Client(api_token=settings.replicate_api_token.strip())


def _prediction_to_out(prediction) -> TryOnJobOut:
    raw_status = str(getattr(prediction, "status", "")).strip().lower()
    normalized = _STATUS_MAP.get(raw_status, "FAILED")

    result_url = None
    if normalized == "SUCCEEDED":
        output = getattr(prediction, "output", None)
        if isinstance(output, str):
            result_url = output
        elif isinstance(output, (list, tuple)) and output:
            first = output[0]
            result_url = first if isinstance(first, str) else str(getattr(first, "url", "")) or None

    error = getattr(prediction, "error", None)

    return TryOnJobOut(
        provider="replicate",
        job_id=str(getattr(prediction, "id")),
        status=normalized,
        result_url=result_url,
        error=str(error).strip() if error else None,
    )


@router.get("/capabilities", response_model=TryOnCapabilities)
def capabilities():
    """CU-14: Indica si el vestidor virtual (RA) está disponible en el servidor"""
    return TryOnCapabilities(
        configured=bool(settings.replicate_api_token.strip()),
        model=settings.tryon_replicate_model.strip(),
    )


@router.post("/jobs", response_model=TryOnJobOut, status_code=status.HTTP_202_ACCEPTED)
async def crear_generacion(
    prenda_id: int = Form(...),
    persona: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """CU-14: Generar una imagen del cliente probándose una prenda, usando IA (Replicate)"""
    prenda = db.get(Prenda, prenda_id)
    if not prenda or not prenda.estado:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prenda no encontrada")
    if not prenda.imagen_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La prenda no tiene una imagen de referencia configurada para el vestidor virtual",
        )

    content = await persona.read()
    await persona.close()

    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La foto de la persona está vacía")
    if len(content) > MAX_INPUT_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="La foto supera el límite de 5 MB")

    detected_type = _detect_image_type(content)
    if detected_type is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La foto debe ser una imagen PNG, JPG/JPEG o WEBP válida",
        )

    try:
        content = _normalizar_orientacion(content)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se pudo procesar la foto enviada",
        ) from exc

    client = _replicate_client()
    person_file = io.BytesIO(content)
    person_file.name = "persona.jpg"

    # El modelo indica que para fotos de referencia "con más de un elemento" (ej. una
    # modelo con fondo, en vez de una foto plana del producto) hay que decirle explícitamente
    # qué prenda usar con el prompt; si no, puede alucinar una prenda distinta.
    prompt = f"Usa la prenda: {prenda.nombre}."

    try:
        prediction = client.predictions.create(
            model=settings.tryon_replicate_model.strip(),
            input={
                "person_image": person_file,
                "garment_images": [prenda.imagen_url],
                "prompt": prompt,
                "output_format": "jpg",
                "output_quality": 95,
                "preserve_input_size": True,
            },
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"No se pudo generar la imagen del vestidor virtual: {_replicate_error_detail(exc)}",
        ) from exc
    finally:
        person_file.close()

    return _prediction_to_out(prediction)


def _replicate_error_detail(exc: Exception) -> str:
    try:
        from replicate.exceptions import ReplicateError
    except ImportError:
        return str(exc)

    if isinstance(exc, ReplicateError):
        return getattr(exc, "detail", None) or str(exc)
    return str(exc)


@router.get("/jobs/{job_id}", response_model=TryOnJobOut)
def consultar_generacion(job_id: str):
    """CU-14: Consultar el estado de una generación del vestidor virtual"""
    client = _replicate_client()
    try:
        prediction = client.predictions.get(job_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"No se pudo consultar el estado de la generación: {_replicate_error_detail(exc)}",
        ) from exc

    return _prediction_to_out(prediction)
