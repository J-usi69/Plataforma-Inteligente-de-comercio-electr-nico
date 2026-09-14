"""Consultas de agregación reutilizadas por los reportes predefinidos (CU-31, CU-32)
y por el reporte generado mediante IA (CU-30)."""
from datetime import date, datetime, time, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.catalogo import Prenda, VariantePrenda
from app.models.enums import EstadoReserva, EstadoVenta
from app.models.inventario import InventarioSucursal
from app.models.reserva import Reserva
from app.models.sucursal import Sucursal
from app.models.venta import DetalleVenta, Venta


def _inicio_dia(d: Optional[date]) -> Optional[datetime]:
    return datetime.combine(d, time.min, tzinfo=timezone.utc) if d else None


def _fin_dia(d: Optional[date]) -> Optional[datetime]:
    return datetime.combine(d, time.max, tzinfo=timezone.utc) if d else None


def ventas_por_sucursal(db: Session, desde: Optional[date] = None, hasta: Optional[date] = None) -> list[dict]:
    stmt = select(
        Venta.sucursal_id,
        func.count(Venta.id),
        func.coalesce(func.sum(Venta.total), 0),
    ).where(Venta.estado == EstadoVenta.pagada)
    if desde:
        stmt = stmt.where(Venta.fecha_venta >= _inicio_dia(desde))
    if hasta:
        stmt = stmt.where(Venta.fecha_venta <= _fin_dia(hasta))
    stmt = stmt.group_by(Venta.sucursal_id).order_by(func.sum(Venta.total).desc())

    resultado = []
    for sucursal_id, cantidad, total in db.execute(stmt).all():
        sucursal = db.get(Sucursal, sucursal_id)
        resultado.append({
            "sucursal_id": sucursal_id,
            "sucursal_nombre": sucursal.nombre if sucursal else "Sucursal eliminada",
            "cantidad_ventas": cantidad,
            "total_ventas": float(total),
        })
    return resultado


def prendas_mas_vendidas(db: Session, desde: Optional[date] = None, hasta: Optional[date] = None, limit: int = 10) -> list[dict]:
    stmt = (
        select(
            DetalleVenta.variante_id,
            func.sum(DetalleVenta.cantidad),
            func.sum(DetalleVenta.subtotal),
        )
        .join(Venta, Venta.id == DetalleVenta.venta_id)
        .where(Venta.estado == EstadoVenta.pagada)
    )
    if desde:
        stmt = stmt.where(Venta.fecha_venta >= _inicio_dia(desde))
    if hasta:
        stmt = stmt.where(Venta.fecha_venta <= _fin_dia(hasta))
    stmt = stmt.group_by(DetalleVenta.variante_id).order_by(func.sum(DetalleVenta.cantidad).desc()).limit(limit)

    resultado = []
    for variante_id, cantidad, total in db.execute(stmt).all():
        variante = db.get(VariantePrenda, variante_id)
        prenda = db.get(Prenda, variante.prenda_id) if variante else None
        resultado.append({
            "prenda_id": prenda.id if prenda else None,
            "prenda_nombre": prenda.nombre if prenda else "Prenda eliminada",
            "cantidad_vendida": int(cantidad),
            "total_vendido": float(total),
        })
    return resultado


def quiebres_stock(db: Session, sucursal_id: Optional[int] = None) -> list[dict]:
    stmt = select(InventarioSucursal).where(InventarioSucursal.stock_disponible < InventarioSucursal.stock_minimo)
    if sucursal_id:
        stmt = stmt.where(InventarioSucursal.sucursal_id == sucursal_id)

    resultado = []
    for inv in db.scalars(stmt).all():
        variante = db.get(VariantePrenda, inv.variante_id)
        prenda = db.get(Prenda, variante.prenda_id) if variante else None
        sucursal = db.get(Sucursal, inv.sucursal_id)
        resultado.append({
            "variante_id": inv.variante_id,
            "prenda_nombre": prenda.nombre if prenda else "Prenda eliminada",
            "sucursal_id": inv.sucursal_id,
            "sucursal_nombre": sucursal.nombre if sucursal else "Sucursal eliminada",
            "stock_disponible": inv.stock_disponible,
            "stock_minimo": inv.stock_minimo,
        })
    return resultado


def resumen_dashboard(
    db: Session,
    sucursal_id: Optional[int] = None,
    ciudad_id: Optional[int] = None,
    desde: Optional[date] = None,
    hasta: Optional[date] = None,
) -> dict:
    ventas_stmt = select(func.count(Venta.id), func.coalesce(func.sum(Venta.total), 0)).where(Venta.estado == EstadoVenta.pagada)
    if sucursal_id:
        ventas_stmt = ventas_stmt.where(Venta.sucursal_id == sucursal_id)
    if ciudad_id:
        ventas_stmt = ventas_stmt.join(Sucursal, Sucursal.id == Venta.sucursal_id).where(Sucursal.ciudad_id == ciudad_id)
    if desde:
        ventas_stmt = ventas_stmt.where(Venta.fecha_venta >= _inicio_dia(desde))
    if hasta:
        ventas_stmt = ventas_stmt.where(Venta.fecha_venta <= _fin_dia(hasta))
    cantidad_ventas, total_ventas = db.execute(ventas_stmt).one()
    total_ventas = float(total_ventas)
    ticket_promedio = total_ventas / cantidad_ventas if cantidad_ventas else 0.0

    reservas_stmt = select(func.count(Reserva.id)).where(Reserva.estado == EstadoReserva.pendiente)
    if sucursal_id:
        reservas_stmt = reservas_stmt.where(Reserva.sucursal_id == sucursal_id)
    reservas_pendientes = db.execute(reservas_stmt).scalar() or 0

    quiebres = quiebres_stock(db, sucursal_id)

    return {
        "cantidad_ventas": cantidad_ventas,
        "total_ventas": total_ventas,
        "ticket_promedio": round(ticket_promedio, 2),
        "reservas_pendientes": reservas_pendientes,
        "variantes_bajo_minimo": len(quiebres),
        "quiebres": quiebres[:10],
    }
