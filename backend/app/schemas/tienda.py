from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

COLOR_HEX = r"^#[0-9a-fA-F]{6}$"


class FuncionesOut(BaseModel):
    """Qué incluye el plan: la web y la app muestran u ocultan cada función según esto."""

    model_config = ConfigDict(from_attributes=True)

    operacion_offline: bool
    reportes: bool
    reportes_ia: bool
    asistente_ia: bool
    vestidor_ar: bool
    pago_qr: bool


class PlanOut(FuncionesOut):
    codigo: str
    nombre: str
    descripcion: Optional[str]
    precio_mensual: float
    moneda: str
    # None = sin límite
    max_sucursales: Optional[int]
    max_prendas: Optional[int]
    max_personal: Optional[int]


class PlanAdminOut(PlanOut):
    """El plan visto por el superadmin: también los desactivados (ya no se ofrecen) y cuántas
    empresas lo tienen contratado."""

    estado: bool
    empresas: int = 0


class PlanCreate(BaseModel):
    """Plan nuevo creado por el superadmin (CU-02). Un límite en null significa "sin límite"."""

    codigo: str = Field(..., pattern=r"^[a-z0-9](?:[a-z0-9-]{0,28}[a-z0-9])?$")
    nombre: str = Field(..., min_length=2, max_length=60)
    descripcion: Optional[str] = Field(None, max_length=200)
    precio_mensual: float = Field(0, ge=0)
    max_sucursales: Optional[int] = Field(None, ge=1)
    max_prendas: Optional[int] = Field(None, ge=1)
    max_personal: Optional[int] = Field(None, ge=1)
    operacion_offline: bool = True
    reportes: bool = True
    reportes_ia: bool = False
    asistente_ia: bool = True
    vestidor_ar: bool = True
    pago_qr: bool = True


class PlanUpdate(BaseModel):
    """Configuración de un plan por el superadmin. Un límite en null significa "sin límite"."""

    nombre: Optional[str] = Field(None, min_length=2, max_length=60)
    descripcion: Optional[str] = Field(None, max_length=200)
    precio_mensual: Optional[float] = Field(None, ge=0)
    max_sucursales: Optional[int] = Field(None, ge=1)
    max_prendas: Optional[int] = Field(None, ge=1)
    max_personal: Optional[int] = Field(None, ge=1)
    operacion_offline: Optional[bool] = None
    reportes: Optional[bool] = None
    reportes_ia: Optional[bool] = None
    asistente_ia: Optional[bool] = None
    vestidor_ar: Optional[bool] = None
    pago_qr: Optional[bool] = None
    estado: Optional[bool] = None

    @model_validator(mode="after")
    def _solo_limites_y_descripcion_pueden_ser_null(self):
        anulables = {"max_sucursales", "max_prendas", "max_personal", "descripcion"}
        vacios = [campo for campo in self.model_fields_set - anulables if getattr(self, campo) is None]
        if vacios:
            raise ValueError(f"No pueden quedar vacíos: {', '.join(sorted(vacios))}")
        return self


class TiendaPublicaOut(BaseModel):
    """Lo que la web y la app necesitan para vestirse con la marca de la tienda."""

    slug: str
    nombre: str
    logo_url: Optional[str]
    color_primario: str
    color_acento: str
    plan: str
    plan_nombre: str
    funciones: FuncionesOut
    # False: suscripción vencida o cancelada, la tienda está en modo consulta
    suscripcion_vigente: bool
    dias_para_cambio: int  # plazo para cambiar una prenda comprada


class TiendaUpdate(BaseModel):
    nombre: Optional[str] = Field(None, min_length=2, max_length=80)
    logo_url: Optional[str] = Field(None, max_length=500)
    color_primario: Optional[str] = Field(None, pattern=COLOR_HEX)
    color_acento: Optional[str] = Field(None, pattern=COLOR_HEX)
    correo_contacto: Optional[EmailStr] = None
    dias_para_cambio: Optional[int] = Field(None, ge=0, le=90)  # 0: no se aceptan cambios


class SuscripcionOut(BaseModel):
    estado: str  # activa, vencida, cancelada
    fecha_inicio: datetime
    fecha_vencimiento: Optional[datetime]
    dias_restantes: Optional[int]
    cobro: str  # simulado o stripe


class MovimientoOut(BaseModel):
    fecha: datetime
    tipo: str
    plan: str
    monto: float
    origen: str
    detalle: Optional[str]


class UsoPlanOut(BaseModel):
    plan: PlanOut
    suscripcion: SuscripcionOut
    uso: dict[str, int]
    planes_disponibles: list[PlanOut]
    movimientos: list[MovimientoOut]


class CambioPlanIn(BaseModel):
    plan_codigo: str


class CambioPlanOut(BaseModel):
    # Con cobro por Stripe: URL de Checkout y estado vacío. Con cobro simulado: sin URL y el
    # estado ya con el plan nuevo
    url: Optional[str]
    estado: Optional[UsoPlanOut]


class RenovarIn(BaseModel):
    meses: int = Field(1, ge=1, le=12)


class ConfirmarSuscripcionIn(BaseModel):
    session_id: str


class RegistroTiendaIn(BaseModel):
    nombre_tienda: str = Field(..., min_length=2, max_length=80)
    slug: str = Field(..., min_length=3, max_length=40)
    correo: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    plan_codigo: str = "basico"


class RegistroTiendaOut(BaseModel):
    slug: str
    nombre: str
    access_token: str
    token_type: str = "bearer"


class LoginPlataformaIn(BaseModel):
    # Sin validar el formato: alcanza con que exista la cuenta de la plataforma (p. ej. un dominio
    # .local de pruebas). Si no existe o la contraseña no coincide, responde 401 igual que siempre.
    correo: str = Field(..., min_length=3, max_length=120)
    password: str


class TiendaAdminOut(BaseModel):
    id: int
    slug: str
    nombre: str
    estado: str
    plan: str
    plan_codigo: str
    estado_suscripcion: str
    fecha_inicio: Optional[datetime]
    fecha_vencimiento: Optional[datetime]
    creado_en: datetime
    sucursales: int
    usuarios: int
    prendas: int
    ventas: int


class TiendaAdminUpdate(BaseModel):
    estado: Optional[str] = Field(None, pattern=r"^(activa|suspendida)$")
    plan_codigo: Optional[str] = None
    estado_suscripcion: Optional[str] = Field(None, pattern=r"^(activa|cancelada)$")
    fecha_vencimiento: Optional[datetime] = None


# --- Reportes e indicadores de la plataforma (superadmin) ---------------------------------------

class ReportePlataformaOut(BaseModel):
    """Un reporte de la plataforma listo para mostrar como tabla o exportar."""

    tipo: str
    titulo: str
    columnas: list[str]
    filas: list[list[Any]]
    totales: Optional[dict[str, Any]] = None
    narrativa: str
    columnas_monto: list[str] = []
    filtros: str = ""


class CatalogoReporteOut(BaseModel):
    """Un reporte disponible en el constructor: sus columnas y el orden por defecto."""

    tipo: str
    titulo: str
    descripcion: str
    columnas: list[str]
    orden: str
    descendente: bool
    columnas_monto: list[str]


class EnviarReporteIn(BaseModel):
    """Enviar un reporte por correo con las mismas opciones con que se ve en pantalla."""

    destinatario: EmailStr
    formato: str = Field("pdf", pattern=r"^(excel|pdf|html)$")
    desde: Optional[date] = None
    hasta: Optional[date] = None
    columnas: list[str] = []
    criterios: list[str] = []  # columna|operador|valor
    orden: Optional[str] = None
    descendente: Optional[bool] = None


class IngresoMesOut(BaseModel):
    mes: str
    etiqueta: str
    monto: float


class EmpresasPorPlanOut(BaseModel):
    plan: str
    cantidad: int
    ingreso_mensual: float


class VentasEmpresaOut(BaseModel):
    empresa: str
    ventas: int
    total: float


class VencimientoOut(BaseModel):
    empresa: str
    slug: str
    vence: datetime
    dias: int


class IndicadoresPlataformaOut(BaseModel):
    empresas: int
    vigentes: int
    suspendidas: int
    sin_suscripcion_vigente: int
    ingreso_mensual: float
    ingresos_mes_actual: float
    ingresos_por_mes: list[IngresoMesOut]
    empresas_por_plan: list[EmpresasPorPlanOut]
    ventas_por_empresa: list[VentasEmpresaOut]
    proximos_vencimientos: list[VencimientoOut]


class PedidoReporteIn(BaseModel):
    """Pedido de reporte en lenguaje natural (escrito o dictado por voz)."""

    pedido: str = Field(..., min_length=3, max_length=500)


class CriterioOut(BaseModel):
    columna: str
    operador: str
    valor: str


class OpcionesReporteOut(BaseModel):
    """Cómo interpretó la IA el pedido: la web lo carga en el constructor para ajustarlo."""

    tipo: str
    columnas: Optional[list[str]] = None
    criterios: list[CriterioOut] = []
    desde: Optional[date] = None
    hasta: Optional[date] = None
    orden: Optional[str] = None
    descendente: Optional[bool] = None


class ReporteIAPlataformaOut(BaseModel):
    pedido: str
    opciones: OpcionesReporteOut
    reporte: ReportePlataformaOut


class RestauracionOut(BaseModel):
    """Qué se restauró (o se restauraría, si simulado) desde un respaldo."""

    simulado: bool
    alcance: str  # "empresa" o "sistema"
    empresa: Optional[str] = None
    respaldo_del: Optional[str] = None  # fecha en que se generó el respaldo (ISO, UTC)
    tablas: dict[str, int]  # filas del respaldo por tabla
    filas: int
    usuarios_desactivados: int  # cuentas creadas después del respaldo
    empresas_suspendidas: int  # empresas dadas de alta después del respaldo (solo sistema)
