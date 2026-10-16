from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field

COLOR_HEX = r"^#[0-9a-fA-F]{6}$"


class PlanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    codigo: str
    nombre: str
    precio_mensual: float
    moneda: str
    max_sucursales: Optional[int]
    max_prendas: Optional[int]
    max_personal: Optional[int]
    ia: bool
    vestidor_ar: bool
    pago_qr: bool


class FuncionesOut(BaseModel):
    ia: bool
    vestidor_ar: bool
    pago_qr: bool


class TiendaPublicaOut(BaseModel):
    """Lo que la web y la app necesitan para vestirse con la marca de la tienda."""

    slug: str
    nombre: str
    logo_url: Optional[str]
    color_primario: str
    color_acento: str
    plan: str
    funciones: FuncionesOut


class TiendaUpdate(BaseModel):
    nombre: Optional[str] = Field(None, min_length=2, max_length=80)
    logo_url: Optional[str] = Field(None, max_length=500)
    color_primario: Optional[str] = Field(None, pattern=COLOR_HEX)
    color_acento: Optional[str] = Field(None, pattern=COLOR_HEX)
    correo_contacto: Optional[EmailStr] = None


class UsoPlanOut(BaseModel):
    plan: PlanOut
    estado_suscripcion: str
    periodo_fin: Optional[datetime]
    uso: dict[str, int]
    planes_disponibles: list[PlanOut]


class CambioPlanIn(BaseModel):
    plan_codigo: str


class CheckoutOut(BaseModel):
    # URL de Stripe Checkout; None si el cambio se aplicó sin pago (pasar al plan Gratis)
    url: Optional[str]
    plan: str


class ConfirmarSuscripcionIn(BaseModel):
    session_id: str


class RegistroTiendaIn(BaseModel):
    nombre_tienda: str = Field(..., min_length=2, max_length=80)
    slug: str = Field(..., min_length=3, max_length=40)
    correo: EmailStr
    password: str = Field(..., min_length=8, max_length=128)


class RegistroTiendaOut(BaseModel):
    slug: str
    nombre: str
    access_token: str
    token_type: str = "bearer"


class LoginPlataformaIn(BaseModel):
    correo: EmailStr
    password: str


class TiendaAdminOut(BaseModel):
    id: int
    slug: str
    nombre: str
    estado: str
    plan: str
    estado_suscripcion: str
    creado_en: datetime
    usuarios: int
    prendas: int
    ventas: int


class TiendaAdminUpdate(BaseModel):
    estado: Optional[str] = Field(None, pattern=r"^(activa|suspendida)$")
    plan_codigo: Optional[str] = None
