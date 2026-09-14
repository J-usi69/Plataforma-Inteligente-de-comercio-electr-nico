from typing import Any, List, Optional

from pydantic import BaseModel

from app.schemas.catalogo import PrendaOut


class RecomendacionOut(BaseModel):
    prendas: List[PrendaOut]
    fuente: str  # "ia" o "mas_vendidas" (fallback documentado en la excepción de CU-28)


class ChatRequest(BaseModel):
    mensaje: str


class ChatResponse(BaseModel):
    respuesta: str


class ReporteIARequest(BaseModel):
    prompt: str


class ReporteIAResponse(BaseModel):
    tipo: str
    parametros: dict
    datos: Any
