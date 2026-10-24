"""Stock por sucursal: cómo se modifica sin que dos operaciones simultáneas se pisen.

Regla única para todo el backend: toda escritura de stock bloquea antes sus filas de inventario
(SELECT ... FOR UPDATE), siempre en el mismo orden (por variante), y descuenta en la misma
transacción en la que verificó. Si dos personas van por la última unidad al mismo tiempo, la
segunda espera a que la primera termine y recién entonces ve lo que quedó: una se la lleva y la
otra recibe "sin stock". Funciona igual con varias instancias del backend, porque quien ordena es
Postgres.

Apartado al pagar: pagar con tarjeta o QR puede tardar minutos. Mientras tanto las prendas pasan
de disponibles a reservadas (venta.apartado_hasta), así otro cliente no puede empezar a pagar la
misma última unidad y terminar pagando algo que no se le puede entregar. Si el pago no se
completa a tiempo, liberar_apartados_vencidos las devuelve.
"""
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.catalogo import Prenda, VariantePrenda
from app.models.enums import EstadoVenta
from app.models.inventario import InventarioSucursal
from app.models.venta import DetalleVenta, Venta

logger = logging.getLogger("fashionstore.inventario")


def bloquear_inventario(db: Session, sucursal_id: int, variante_ids: Iterable[int]) -> dict[int, InventarioSucursal]:
    """Filas de inventario bloqueadas hasta el commit y releídas de la base. El orden fijo hace
    que dos operaciones sobre las mismas prendas esperen una a la otra en vez de trabarse."""
    filas = db.scalars(
        select(InventarioSucursal)
        .where(InventarioSucursal.sucursal_id == sucursal_id, InventarioSucursal.variante_id.in_(set(variante_ids)))
        .order_by(InventarioSucursal.variante_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).all()
    return {fila.variante_id: fila for fila in filas}


def bloquear_venta(db: Session, venta_id: int) -> Optional[Venta]:
    """La venta releída y bloqueada. Siempre antes que su inventario (venta -> inventario), el
    mismo orden en todos lados."""
    return db.scalars(
        select(Venta).where(Venta.id == venta_id).with_for_update().execution_options(populate_existing=True)
    ).first()


def _cantidades_de_la_venta(db: Session, venta_id: int) -> dict[int, int]:
    cantidades: dict[int, int] = defaultdict(int)
    for detalle in db.scalars(select(DetalleVenta).where(DetalleVenta.venta_id == venta_id)):
        cantidades[detalle.variante_id] += detalle.cantidad
    return dict(cantidades)


def apartar_para_pagar(db: Session, venta: Venta, ahora: Optional[datetime] = None) -> tuple[Venta, bool]:
    """Aparta las prendas de la venta mientras se paga (sin commit). Devuelve la venta releída y
    si el apartado es nuevo (False: ya estaba apartada y solo se extendió el plazo, por ejemplo
    al volver a generar el QR). 400 si ya no hay stock: nadie llega a pagar lo que no hay."""
    ahora = ahora or datetime.now(timezone.utc)
    venta = bloquear_venta(db, venta.id)
    if venta is None or venta.estado != EstadoVenta.pendiente:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Esta venta ya fue pagada o anulada")
    if venta.reserva_id is not None:
        return venta, False  # viene de una reserva: sus prendas ya están apartadas
    vence = ahora + timedelta(minutes=settings.minutos_apartado_pago)
    if venta.apartado_hasta is not None:
        venta.apartado_hasta = vence
        return venta, False

    pedidas = _cantidades_de_la_venta(db, venta.id)
    filas = bloquear_inventario(db, venta.sucursal_id, pedidas)
    for variante_id, cantidad in sorted(pedidas.items()):
        fila = filas.get(variante_id)
        if not fila or fila.stock_disponible < cantidad:
            variante = db.get(VariantePrenda, variante_id)
            prenda = db.get(Prenda, variante.prenda_id) if variante else None
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Ya no hay stock suficiente de '{prenda.nombre if prenda else 'Prenda'}' en la sucursal",
            )
    for variante_id, cantidad in pedidas.items():
        filas[variante_id].stock_disponible -= cantidad
        filas[variante_id].stock_reservado += cantidad
    venta.apartado_hasta = vence
    return venta, True


def devolver_apartado(db: Session, venta: Venta) -> None:
    """Devuelve a disponible lo apartado para pagar (sin commit). La venta tiene que estar
    bloqueada por quien llama."""
    if venta.apartado_hasta is None:
        return
    pedidas = _cantidades_de_la_venta(db, venta.id)
    filas = bloquear_inventario(db, venta.sucursal_id, pedidas)
    for variante_id, cantidad in pedidas.items():
        fila = filas.get(variante_id)
        if fila:
            devuelto = min(cantidad, fila.stock_reservado)
            fila.stock_reservado -= devuelto
            fila.stock_disponible += devuelto
    venta.apartado_hasta = None


def liberar_apartados_vencidos(ahora: Optional[datetime] = None, maximo: int = 200) -> int:
    """Devuelve el stock de los pagos que no se completaron a tiempo. Recorre todas las tiendas
    (sesión de la plataforma) de a una venta por transacción y salta las que otro proceso tiene
    bloqueadas (SKIP LOCKED): si justo se está confirmando su pago, esa confirmación gana. Por
    eso puede correr en varias instancias a la vez sin pisarse."""
    from app.db.session import SessionLocal

    ahora = ahora or datetime.now(timezone.utc)
    liberadas = 0
    with SessionLocal() as db:
        for _ in range(maximo):
            venta = db.scalars(
                select(Venta)
                .where(Venta.apartado_hasta < ahora, Venta.estado != EstadoVenta.pagada)
                .order_by(Venta.apartado_hasta)
                .limit(1)
                .with_for_update(skip_locked=True)
            ).first()
            if venta is None:
                break
            devolver_apartado(db, venta)
            db.commit()
            liberadas += 1
    if liberadas:
        logger.info("apartados de pago vencidos liberados: %d", liberadas)
    return liberadas
