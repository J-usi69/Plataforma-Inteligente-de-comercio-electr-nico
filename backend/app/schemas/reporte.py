from datetime import datetime
from typing import Any, List, Optional
from pydantic import BaseModel


class VentaPorSucursalOut(BaseModel):
    sucursal_id: int
    sucursal_nombre: str
    cantidad_ventas: int
    total_ventas: float


class PrendaVendidaOut(BaseModel):
    prenda_id: Optional[int] = None
    prenda_nombre: str
    cantidad_vendida: int
    total_vendido: float


class QuiebreStockOut(BaseModel):
    variante_id: int
    prenda_nombre: str
    sucursal_id: int
    sucursal_nombre: str
    stock_disponible: int
    stock_minimo: int


class InventarioGlobalItemOut(BaseModel):
    variante_id: int
    prenda_nombre: str
    categoria_id: Optional[int] = None
    categoria_nombre: Optional[str] = None
    talla_nombre: Optional[str] = None
    color_nombre: Optional[str] = None
    sucursal_id: int
    sucursal_nombre: str
    ciudad_id: int
    ciudad_nombre: str
    stock_disponible: int
    stock_minimo: int
    es_quiebre: bool


class RendimientoCategoriaOut(BaseModel):
    categoria_id: int
    categoria_nombre: str
    cantidad_prendas_vendidas: int
    total_ingresos: float
    porcentaje_ventas: float


class DashboardOut(BaseModel):
    cantidad_ventas: int
    total_ventas: float
    ticket_promedio: float
    reservas_pendientes: int
    variantes_bajo_minimo: int
    quiebres: List[QuiebreStockOut]


# CU-17: Exportar reporte
class ExportarReporteIn(BaseModel):
    tipo: str  # ventas, prendas_vendidas, inventario, rendimiento_categorias
    formato: str  # excel, pdf
    titulo: Optional[str] = None
    desde: Optional[str] = None
    hasta: Optional[str] = None
    sucursal_id: Optional[int] = None


# CU-18: Dashboard de analítica con Machine Learning
class PrediccionDemandaItem(BaseModel):
    periodo: str
    fecha: str
    ventas_proyectadas: float
    unidades_estimadas: int
    limite_inferior: float
    limite_superior: float


class ClusterClienteItem(BaseModel):
    cluster_id: int
    nombre_segmento: str
    descripcion: str
    cantidad_clientes: int
    porcentaje: float
    ticket_promedio: float
    frecuencia_visitas: float
    estrategia_recomendada: str


class MetricasModeloML(BaseModel):
    modelo_supervisado_nombre: str
    r2_score: float
    mae: float
    rmse: float
    modelo_no_supervisado_nombre: str
    silhouette_score: float
    total_observaciones: int
    fecha_entrenamiento: str
    es_datos_sinteticos: bool


class DashboardAnaliticaMLOut(BaseModel):
    metricas: MetricasModeloML
    predicciones_demanda: List[PrediccionDemandaItem]
    segmentacion_clientes: List[ClusterClienteItem]
    resumen_ejecutivo: str
