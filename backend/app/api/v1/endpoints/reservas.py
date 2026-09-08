from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user, get_db
from app.models.catalogo import Color, Prenda, Talla, VariantePrenda
from app.models.enums import EstadoReserva, TipoMovimiento
from app.models.inventario import InventarioSucursal, MovimientoInventario
from app.models.reserva import DetalleReserva, Reserva
from app.models.seguridad import Usuario
from app.models.sucursal import Sucursal
from app.schemas.reserva import DetalleReservaOut, ReservaCreate, ReservaOut

router = APIRouter()


def _detalle_a_out(db: Session, detalle: DetalleReserva) -> DetalleReservaOut:
    variante = db.get(VariantePrenda, detalle.variante_id)
    prenda = db.get(Prenda, variante.prenda_id) if variante else None
    talla = db.get(Talla, variante.talla_id) if variante else None
    color = db.get(Color, variante.color_id) if variante else None
    return DetalleReservaOut(
        id=detalle.id,
        variante_id=detalle.variante_id,
        cantidad=detalle.cantidad,
        prenda_nombre=prenda.nombre if prenda else None,
        talla_nombre=talla.nombre if talla else None,
        color_nombre=color.nombre if color else None,
        codigo_barras=variante.codigo_barras if variante else None,
    )


def _reserva_a_out(db: Session, reserva: Reserva) -> ReservaOut:
    sucursal = db.get(Sucursal, reserva.sucursal_id)
    detalles = db.scalars(select(DetalleReserva).where(DetalleReserva.reserva_id == reserva.id)).all()
    return ReservaOut(
        id=reserva.id,
        usuario_id=reserva.usuario_id,
        sucursal_id=reserva.sucursal_id,
        sucursal_nombre=sucursal.nombre if sucursal else None,
        personal_id=reserva.personal_id,
        fecha_reserva=reserva.fecha_reserva,
        horario_atencion=reserva.horario_atencion,
        estado=reserva.estado.value,
        detalles=[_detalle_a_out(db, d) for d in detalles],
    )


@router.post("", response_model=ReservaOut, status_code=status.HTTP_201_CREATED)
def crear_reserva(
    datos: ReservaCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    """CU-15: Reservar una o varias prendas en una sucursal para probarlas físicamente"""
    if not datos.detalles:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La reserva debe incluir al menos una prenda")

    sucursal = db.get(Sucursal, datos.sucursal_id)
    if not sucursal or not sucursal.estado or sucursal.fecha_eliminacion is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La sucursal especificada no es válida")

    # 3. Validar stock disponible suficiente para cada variante en esa sucursal
    inventarios: dict[int, InventarioSucursal] = {}
    for detalle in datos.detalles:
        variante = db.get(VariantePrenda, detalle.variante_id)
        if not variante or not variante.estado:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"La variante {detalle.variante_id} no existe o no está activa",
            )

        inventario = db.scalars(
            select(InventarioSucursal).where(
                InventarioSucursal.variante_id == detalle.variante_id,
                InventarioSucursal.sucursal_id == datos.sucursal_id,
            )
        ).first()

        if not inventario or inventario.stock_disponible < detalle.cantidad:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Stock insuficiente para la variante {detalle.variante_id} en la sucursal seleccionada "
                    f"(disponible: {inventario.stock_disponible if inventario else 0}, solicitado: {detalle.cantidad})"
                ),
            )
        inventarios[detalle.variante_id] = inventario

    # 4. Crear la reserva y sus detalles
    nueva_reserva = Reserva(
        usuario_id=current_user.id,
        sucursal_id=datos.sucursal_id,
        fecha_reserva=datetime.now(timezone.utc),
        horario_atencion=datos.horario_atencion,
        estado=EstadoReserva.pendiente,
    )
    db.add(nueva_reserva)
    db.commit()
    db.refresh(nueva_reserva)

    ahora = datetime.now(timezone.utc)
    for detalle in datos.detalles:
        db.add(DetalleReserva(reserva_id=nueva_reserva.id, variante_id=detalle.variante_id, cantidad=detalle.cantidad))

        # 5. Incrementar stockReservado (y descontar de stockDisponible) por sucursal
        inventario = inventarios[detalle.variante_id]
        inventario.stock_disponible -= detalle.cantidad
        inventario.stock_reservado += detalle.cantidad

        db.add(
            MovimientoInventario(
                variante_id=detalle.variante_id,
                sucursal_id=datos.sucursal_id,
                tipo_movimiento=TipoMovimiento.reserva,
                cantidad=detalle.cantidad,
                referencia_id=nueva_reserva.id,
                referencia_tipo="reserva",
                usuario_id=current_user.id,
                fecha=ahora,
            )
        )

    db.commit()
    return _reserva_a_out(db, nueva_reserva)


@router.get("", response_model=List[ReservaOut])
def listar_mis_reservas(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    """CU-16: Consultar las reservas del cliente autenticado"""
    stmt = select(Reserva).where(Reserva.usuario_id == current_user.id).order_by(Reserva.id.desc())
    reservas = db.scalars(stmt).all()
    return [_reserva_a_out(db, r) for r in reservas]


@router.get("/{reserva_id}", response_model=ReservaOut)
def obtener_reserva(
    reserva_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    """CU-16: Consultar el detalle de una reserva propia"""
    reserva = db.get(Reserva, reserva_id)
    if not reserva or reserva.usuario_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reserva no encontrada")
    return _reserva_a_out(db, reserva)


@router.post("/{reserva_id}/cancelar", response_model=ReservaOut)
def cancelar_reserva(
    reserva_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    """CU-16: Cancelar una reserva propia que aún esté pendiente"""
    reserva = db.get(Reserva, reserva_id)
    if not reserva or reserva.usuario_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reserva no encontrada")

    if reserva.estado != EstadoReserva.pendiente:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se puede cancelar una reserva en estado '{reserva.estado.value}'",
        )

    detalles = db.scalars(select(DetalleReserva).where(DetalleReserva.reserva_id == reserva.id)).all()
    ahora = datetime.now(timezone.utc)
    for detalle in detalles:
        inventario = db.scalars(
            select(InventarioSucursal).where(
                InventarioSucursal.variante_id == detalle.variante_id,
                InventarioSucursal.sucursal_id == reserva.sucursal_id,
            )
        ).first()
        if inventario:
            inventario.stock_disponible += detalle.cantidad
            inventario.stock_reservado = max(0, inventario.stock_reservado - detalle.cantidad)

        db.add(
            MovimientoInventario(
                variante_id=detalle.variante_id,
                sucursal_id=reserva.sucursal_id,
                tipo_movimiento=TipoMovimiento.ajuste,
                cantidad=-detalle.cantidad,
                referencia_id=reserva.id,
                referencia_tipo="reserva_cancelada",
                usuario_id=current_user.id,
                fecha=ahora,
            )
        )

    reserva.estado = EstadoReserva.cancelada
    db.commit()
    return _reserva_a_out(db, reserva)
