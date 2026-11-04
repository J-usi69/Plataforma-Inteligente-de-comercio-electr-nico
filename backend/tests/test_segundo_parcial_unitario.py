"""Tests unitarios rápidos del Segundo Parcial (sin requerir base de datos activa).
Valida las fórmulas de Machine Learning (R², MAE, Silueta),
la generación de archivos binarios Excel (.xlsx) y PDF (.pdf),
y la validación de esquemas de datos para CU-14, CU-16, CU-17 y CU-18.
"""
from datetime import datetime, timezone
import pytest
from app.schemas.ia import ReporteIARequest, ReporteIAResponse
from app.schemas.reporte import (
    ClusterClienteItem,
    DashboardAnaliticaMLOut,
    ExportarReporteIn,
    MetricasModeloML,
    PrediccionDemandaItem,
    RendimientoCategoriaOut,
)
from app.schemas.sincronizacion import ResolverConflictoIn
from app.services import ml_analytics_service, reportes_service


def test_esquema_resolver_conflicto_cu14():
    """CU-14: Valida que ResolverConflictoIn soporte aceptar, anular y reasignar."""
    # Aceptar con ajuste
    obj1 = ResolverConflictoIn(accion="aceptar", nota="Aprobado por faltante")
    assert obj1.accion == "aceptar"

    # Anular
    obj2 = ResolverConflictoIn(accion="anular", nota="Cancelado por discrepancia")
    assert obj2.accion == "anular"

    # Reasignar a otra sucursal
    obj3 = ResolverConflictoIn(accion="reasignar", nueva_sucursal_id=3, nota="Transferido")
    assert obj3.accion == "reasignar"
    assert obj3.nueva_sucursal_id == 3


def test_esquema_reporte_ia_cu16():
    """CU-16: Valida el esquema de reporte IA con narrativa ejecutiva y tipo de gráfico."""
    req = ReporteIARequest(prompt="ventas de este mes")
    assert req.prompt == "ventas de este mes"

    res = ReporteIAResponse(
        tipo="rendimiento_categorias",
        parametros={"desde": None, "hasta": None},
        datos=[{"categoria": "Vestidos", "total": 4500.0}],
        narrativa_ia="Categoría líder en el mes actual con 45% de participación.",
        tipo_grafico="pastel",
    )
    assert res.tipo == "rendimiento_categorias"
    assert res.tipo_grafico == "pastel"
    assert "Categoría líder" in res.narrativa_ia


def test_exportar_excel_binario_valido_cu17():
    """CU-17: Generación de libro Excel XLSX con formato corporativo."""
    tienda = "Moda Primavera S.R.L."
    titulo = "Reporte de Ventas por Sucursal"
    columnas = ["Sucursal", "Ventas", "Total Recaudado (Bs.)"]
    filas = [
        ["Sucursal Equipetrol", 25, 6250.00],
        ["Sucursal Centro", 14, 3500.00],
    ]
    totales = {"Sucursal": "TOTAL", "Ventas": 39, "Total Recaudado (Bs.)": 9750.00}

    archivo_bytes = reportes_service.generar_excel_reporte(
        tienda_nombre=tienda,
        titulo=titulo,
        columnas=columnas,
        filas=filas,
        resumen_totales=totales,
    )

    assert isinstance(archivo_bytes, bytes)
    assert len(archivo_bytes) > 2000
    # Encabezado ZIP/XLSX: b'PK\x03\x04'
    assert archivo_bytes[:2] == b"PK"


def test_exportar_pdf_binario_valido_cu17():
    """CU-17: Generación de documento PDF con membrete corporativo y narrativa IA."""
    tienda = "Moda Primavera S.R.L."
    titulo = "Ranking de Prendas Más Vendidas"
    columnas = ["Prenda", "Cant. Vendida", "Total (Bs.)"]
    filas = [
        ["Vestido de Gala", "12", "Bs. 3600.00"],
        ["Campera Cuero", "8", "Bs. 2400.00"],
    ]
    narrativa = "El 60% de los ingresos provino de prendas de fiesta y alta costura."

    archivo_pdf = reportes_service.generar_pdf_reporte(
        tienda_nombre=tienda,
        titulo=titulo,
        columnas=columnas,
        filas=filas,
        narrativa_ia=narrativa,
    )

    assert isinstance(archivo_pdf, bytes)
    assert len(archivo_pdf) > 1000
    # Encabezado oficial PDF: %PDF-
    assert archivo_pdf.startswith(b"%PDF-")


def test_ml_supervisado_ridge_forecasting_cu18():
    """CU-18: Evaluación del modelo de regresión Ridge para pronóstico de demanda."""
    from sklearn.linear_model import Ridge
    from sklearn.metrics import mean_absolute_error, r2_score

    X, y, unidades = ml_analytics_service._generar_datos_sinteticos_ventas(num_semanas=24)
    assert len(y) == 24
    assert len(unidades) == 24

    modelo = Ridge(alpha=1.0)
    modelo.fit(X, y)
    y_pred = modelo.predict(X)

    r2 = r2_score(y, y_pred)
    mae = mean_absolute_error(y, y_pred)

    assert r2 >= 0.70, f"R² de ajuste deficiente: {r2}"
    assert mae > 0, "MAE debe ser mayor a 0"


def test_ml_no_supervisado_kmeans_clustering_cu18():
    """CU-18: Evaluación del modelo no supervisado K-Means para segmentación RFM."""
    from sklearn.cluster import KMeans
    from sklearn.metrics import silhouette_score

    datos_rfm = ml_analytics_service._generar_datos_sinteticos_clientes(n_clientes=120)
    assert datos_rfm.shape == (120, 3)

    norm_rfm = (datos_rfm - datos_rfm.min(axis=0)) / (datos_rfm.max(axis=0) - datos_rfm.min(axis=0) + 1e-6)

    kmeans = KMeans(n_clusters=4, random_state=42, n_init=10)
    labels = kmeans.fit_predict(norm_rfm)

    sil = silhouette_score(norm_rfm, labels)
    assert sil >= 0.45, f"Coeficiente de silueta deficiente: {sil}"
