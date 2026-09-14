from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends

from app.api.deps import get_db, require_roles
from app.schemas.reporte import DashboardOut, PrendaVendidaOut, QuiebreStockOut, VentaPorSucursalOut
from app.services import reportes_service

router = APIRouter()

_ROLES_REPORTES = ["Administrador"]


@router.get("/dashboard", response_model=DashboardOut)
def obtener_dashboard(
    sucursal_id: Optional[int] = None,
    ciudad_id: Optional[int] = None,
    desde: Optional[date] = None,
    hasta: Optional[date] = None,
    db=Depends(get_db),
    current_user=Depends(require_roles(_ROLES_REPORTES)),
):
    """CU-32: indicadores consolidados de ventas, reservas e inventario."""
    return reportes_service.resumen_dashboard(db, sucursal_id=sucursal_id, ciudad_id=ciudad_id, desde=desde, hasta=hasta)


@router.get("/ventas", response_model=List[VentaPorSucursalOut])
def obtener_reporte_ventas(
    desde: Optional[date] = None,
    hasta: Optional[date] = None,
    db=Depends(get_db),
    current_user=Depends(require_roles(_ROLES_REPORTES)),
):
    """CU-31: ventas consolidadas por sucursal en el periodo indicado."""
    return reportes_service.ventas_por_sucursal(db, desde=desde, hasta=hasta)


@router.get("/prendas-mas-vendidas", response_model=List[PrendaVendidaOut])
def obtener_prendas_mas_vendidas(
    desde: Optional[date] = None,
    hasta: Optional[date] = None,
    limit: int = 10,
    db=Depends(get_db),
    current_user=Depends(require_roles(_ROLES_REPORTES)),
):
    """CU-31: ranking de prendas más vendidas en el periodo indicado."""
    return reportes_service.prendas_mas_vendidas(db, desde=desde, hasta=hasta, limit=limit)


@router.get("/inventario", response_model=List[QuiebreStockOut])
def obtener_reporte_inventario(
    sucursal_id: Optional[int] = None,
    db=Depends(get_db),
    current_user=Depends(require_roles(_ROLES_REPORTES)),
):
    """CU-31: variantes con stockDisponible por debajo del stockMinimo (quiebres)."""
    return reportes_service.quiebres_stock(db, sucursal_id=sucursal_id)
