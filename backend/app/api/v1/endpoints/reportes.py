from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.models.seguridad import Usuario
from app.models.tienda import Tienda
from app.schemas.reporte import (
    DashboardAnaliticaMLOut,
    DashboardOut,
    ExportarReporteIn,
    InventarioGlobalItemOut,
    PrendaVendidaOut,
    QuiebreStockOut,
    RendimientoCategoriaOut,
    VentaPorSucursalOut,
)
from app.services import ml_analytics_service, reportes_service
from app.services.planes_service import exigir_funcion

router = APIRouter()

_ROLES_REPORTES = ["Administrador", "Encargado"]


@router.get("/dashboard", response_model=DashboardOut)
def obtener_dashboard(
    sucursal_id: Optional[int] = None,
    ciudad_id: Optional[int] = None,
    desde: Optional[date] = None,
    hasta: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_roles(_ROLES_REPORTES)),
):
    """CU-32: indicadores consolidados de ventas, reservas e inventario."""
    return reportes_service.resumen_dashboard(db, sucursal_id=sucursal_id, ciudad_id=ciudad_id, desde=desde, hasta=hasta)


@router.get("/ventas", response_model=List[VentaPorSucursalOut])
def obtener_reporte_ventas(
    desde: Optional[date] = None,
    hasta: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_roles(_ROLES_REPORTES)),
):
    """CU-31: ventas consolidadas por sucursal en el periodo indicado."""
    return reportes_service.ventas_por_sucursal(db, desde=desde, hasta=hasta)


@router.get("/prendas-mas-vendidas", response_model=List[PrendaVendidaOut])
def obtener_prendas_mas_vendidas(
    desde: Optional[date] = None,
    hasta: Optional[date] = None,
    limit: int = 10,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_roles(_ROLES_REPORTES)),
):
    """CU-31: ranking de prendas más vendidas en el periodo indicado."""
    return reportes_service.prendas_mas_vendidas(db, desde=desde, hasta=hasta, limit=limit)


@router.get("/inventario", response_model=List[QuiebreStockOut])
def obtener_reporte_inventario(
    sucursal_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_roles(_ROLES_REPORTES)),
):
    """CU-31: variantes con stockDisponible por debajo del stockMinimo (quiebres)."""
    return reportes_service.quiebres_stock(db, sucursal_id=sucursal_id)


@router.get("/inventario-global", response_model=List[InventarioGlobalItemOut])
def obtener_inventario_global(
    ciudad_id: Optional[int] = None,
    categoria_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_roles(_ROLES_REPORTES)),
):
    """CU-27: existencias consolidadas de todas las sucursales, con filtros por
    ciudad y categoría y marca de quiebre de stock."""
    return reportes_service.inventario_global(db, ciudad_id=ciudad_id, categoria_id=categoria_id)


@router.get("/rendimiento-categorias", response_model=List[RendimientoCategoriaOut])
def obtener_rendimiento_categorias(
    desde: Optional[date] = None,
    hasta: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_roles(_ROLES_REPORTES)),
):
    """CU-16 (RF21): Rendimiento de ventas y volumen agrupado por categoría textil."""
    return reportes_service.rendimiento_categorias(db, desde=desde, hasta=hasta)


# =====================================================================
# CU-18: GENERAR DASHBOARD DE ANALÍTICA CON MACHINE LEARNING
# =====================================================================
@router.get(
    "/analitica-ml",
    response_model=DashboardAnaliticaMLOut,
    dependencies=[Depends(exigir_funcion("reportes_ia"))],
)
def obtener_analitica_ml(
    sucursal_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_roles(["Administrador"])),
):
    """CU-18: Genera indicadores de analítica con Machine Learning (modelo supervisado
    de proyección de demanda + clustering no supervisado de segmentación de clientes).
    Requiere plan Profesional."""
    return ml_analytics_service.generar_dashboard_analitica_ml(db, sucursal_id=sucursal_id)


# =====================================================================
# CU-17: EXPORTAR REPORTE A EXCEL (XLSX) Y PDF
# =====================================================================
@router.post("/exportar/excel")
def exportar_reporte_excel(
    datos: ExportarReporteIn,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_roles(_ROLES_REPORTES)),
):
    """CU-17: Exporta el reporte solicitado a formato Excel XLSX profesional."""
    tienda = db.get(Tienda, current_user.tienda_id) if current_user.tienda_id else None
    nombre_tienda = tienda.nombre if tienda else "FashionStore"

    d_desde = date.fromisoformat(datos.desde) if datos.desde else None
    d_hasta = date.fromisoformat(datos.hasta) if datos.hasta else None

    if datos.tipo == "ventas":
        rows = reportes_service.ventas_por_sucursal(db, desde=d_desde, hasta=d_hasta)
        titulo = datos.titulo or "Reporte Consolidado de Ventas por Sucursal"
        columnas = ["Sucursal", "Cantidad Ventas", "Total Recaudado (Bs.)"]
        filas = [[r["sucursal_nombre"], r["cantidad_ventas"], r["total_ventas"]] for r in rows]
        tot_monto = sum(r["total_ventas"] for r in rows)
        tot_ventas = sum(r["cantidad_ventas"] for r in rows)
        totales = {"Sucursal": "TOTAL GENERAL", "Cantidad Ventas": tot_ventas, "Total Recaudado (Bs.)": tot_monto}

    elif datos.tipo == "prendas_vendidas":
        rows = reportes_service.prendas_mas_vendidas(db, desde=d_desde, hasta=d_hasta, limit=50)
        titulo = datos.titulo or "Ranking de Prendas Más Vendidas"
        columnas = ["Prenda", "Cantidad Vendida", "Total Generado (Bs.)"]
        filas = [[r["prenda_nombre"], r["cantidad_vendida"], r["total_vendido"]] for r in rows]
        totales = {
            "Prenda": "TOTAL RANKING",
            "Cantidad Vendida": sum(r["cantidad_vendida"] for r in rows),
            "Total Generado (Bs.)": sum(r["total_vendido"] for r in rows),
        }

    elif datos.tipo == "rendimiento_categorias":
        rows = reportes_service.rendimiento_categorias(db, desde=d_desde, hasta=d_hasta)
        titulo = datos.titulo or "Rendimiento Comercial por Categoría"
        columnas = ["Categoría", "Prendas Vendidas", "Ingresos (Bs.)", "Participación (%)"]
        filas = [[r["categoria_nombre"], r["cantidad_prendas_vendidas"], r["total_ingresos"], f"{r['porcentaje_ventas']}%"] for r in rows]
        totales = {
            "Categoría": "TOTAL CONSOLIDADO",
            "Prendas Vendidas": sum(r["cantidad_prendas_vendidas"] for r in rows),
            "Ingresos (Bs.)": sum(r["total_ingresos"] for r in rows),
            "Participación (%)": "100.0%",
        }

    elif datos.tipo == "inventario":
        rows = reportes_service.quiebres_stock(db, sucursal_id=datos.sucursal_id)
        titulo = datos.titulo or "Quiebres de Stock e Inventario Crítico"
        columnas = ["Prenda", "Sucursal", "Stock Disponible", "Stock Mínimo"]
        filas = [[r["prenda_nombre"], r["sucursal_nombre"], r["stock_disponible"], r["stock_minimo"]] for r in rows]
        totales = {"Prenda": f"TOTAL QUIEBRES: {len(rows)}", "Sucursal": "", "Stock Disponible": "", "Stock Mínimo": ""}

    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Tipo de reporte '{datos.tipo}' no soportado")

    contenido_excel = reportes_service.generar_excel_reporte(
        tienda_nombre=nombre_tienda,
        titulo=titulo,
        columnas=columnas,
        filas=filas,
        resumen_totales=totales,
    )

    return Response(
        content=contenido_excel,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="reporte_{datos.tipo}.xlsx"'},
    )


@router.post("/exportar/pdf")
def exportar_reporte_pdf(
    datos: ExportarReporteIn,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_roles(_ROLES_REPORTES)),
):
    """CU-17: Exporta el reporte solicitado a formato PDF corporativo con membrete."""
    tienda = db.get(Tienda, current_user.tienda_id) if current_user.tienda_id else None
    nombre_tienda = tienda.nombre if tienda else "FashionStore"

    d_desde = date.fromisoformat(datos.desde) if datos.desde else None
    d_hasta = date.fromisoformat(datos.hasta) if datos.hasta else None

    if datos.tipo == "ventas":
        rows = reportes_service.ventas_por_sucursal(db, desde=d_desde, hasta=d_hasta)
        titulo = datos.titulo or "Reporte Consolidado de Ventas por Sucursal"
        columnas = ["Sucursal", "Ventas", "Total (Bs.)"]
        filas = [[r["sucursal_nombre"], str(r["cantidad_ventas"]), f"{r['total_ventas']:.2f}"] for r in rows]
        narrativa = f"Se consolidaron {sum(r['cantidad_ventas'] for r in rows)} transacciones por un importe global de Bs. {sum(r['total_ventas'] for r in rows):,.2f}."

    elif datos.tipo == "prendas_vendidas":
        rows = reportes_service.prendas_mas_vendidas(db, desde=d_desde, hasta=d_hasta, limit=20)
        titulo = datos.titulo or "Top Prendas Más Vendidas"
        columnas = ["Prenda", "Cant. Vendida", "Total (Bs.)"]
        filas = [[r["prenda_nombre"], str(r["cantidad_vendida"]), f"{r['total_vendido']:.2f}"] for r in rows]
        narrativa = f"Prendas de mayor rotación comercial en el periodo evaluado. Lidera {rows[0]['prenda_nombre'] if rows else 'N/A'}."

    elif datos.tipo == "rendimiento_categorias":
        rows = reportes_service.rendimiento_categorias(db, desde=d_desde, hasta=d_hasta)
        titulo = datos.titulo or "Rendimiento por Categoría"
        columnas = ["Categoría", "Prendas", "Total (Bs.)", "Part. (%)"]
        filas = [[r["categoria_nombre"], str(r["cantidad_prendas_vendidas"]), f"{r['total_ingresos']:.2f}", f"{r['porcentaje_ventas']}%"] for r in rows]
        narrativa = f"Participación sobre el total de ventas. {len(rows)} categorías analizadas con facturación registrada."

    elif datos.tipo == "inventario":
        rows = reportes_service.quiebres_stock(db, sucursal_id=datos.sucursal_id)
        titulo = datos.titulo or "Quiebres de Stock"
        columnas = ["Prenda", "Sucursal", "Disponible", "Mínimo"]
        filas = [[r["prenda_nombre"], r["sucursal_nombre"], str(r["stock_disponible"]), str(r["stock_minimo"])] for r in rows]
        narrativa = f"Alerta de inventario: {len(rows)} variantes en estado de quiebre que requieren abastecimiento prioritario."

    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Tipo de reporte '{datos.tipo}' no soportado")

    contenido_pdf = reportes_service.generar_pdf_reporte(
        tienda_nombre=nombre_tienda,
        titulo=titulo,
        columnas=columnas,
        filas=filas,
        narrativa_ia=narrativa,
    )

    return Response(
        content=contenido_pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="reporte_{datos.tipo}.pdf"'},
    )
