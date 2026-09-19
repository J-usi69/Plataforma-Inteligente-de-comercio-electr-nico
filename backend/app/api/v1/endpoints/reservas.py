from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_client_ip, get_current_active_user, get_db, get_user_roles, registrar_bitacora, require_roles

_ROLES_STAFF_SUCURSAL = ["Encargado", "Administrador"]
# El Cajero necesita poder ver las reservas de su sucursal (para cargar una
# reserva "atendida" al momento de cobrar en caja), aunque no pueda
# confirmar/atender/marcar no-show — esas acciones siguen siendo solo del Encargado.
_ROLES_LECTURA_RESERVAS_SUCURSAL = ["Encargado", "Cajero", "Administrador"]
from app.models.catalogo import Color, Prenda, Talla, VariantePrenda
from app.models.enums import EstadoReserva, TipoMovimiento
from app.models.inventario import InventarioSucursal, MovimientoInventario
from app.models.reserva import DetalleReserva, Reserva
from app.models.seguridad import Usuario
from app.models.sucursal import Sucursal
from app.schemas.reserva import DetalleReservaOut, ReservaCreate, ReservaOut
from app.services import push_service

router = APIRouter()


def _detalle_a_out(db: Session, detalle: DetalleReserva) -> DetalleReservaOut:
    variante = db.get(VariantePrenda, detalle.variante_id)
    prenda = db.get(Prenda, variante.prenda_id) if variante else None
    talla = db.get(Talla, variante.talla_id) if variante else None
    color = db.get(Color, variante.color_id) if variante else None
    precio = float(prenda.precio_base) if prenda else 0.0
    subtotal = round(precio * detalle.cantidad, 2)
    return DetalleReservaOut(
        id=detalle.id,
        variante_id=detalle.variante_id,
        cantidad=detalle.cantidad,
        prenda_id=prenda.id if prenda else None,
        prenda_nombre=prenda.nombre if prenda else None,
        talla_nombre=talla.nombre if talla else None,
        color_nombre=color.nombre if color else None,
        codigo_barras=variante.codigo_barras if variante else None,
        precio_unitario=precio,
        subtotal=subtotal,
    )


def _reserva_a_out(db: Session, reserva: Reserva) -> ReservaOut:
    sucursal = db.get(Sucursal, reserva.sucursal_id)
    cliente = db.get(Usuario, reserva.usuario_id)
    detalles = db.scalars(select(DetalleReserva).where(DetalleReserva.reserva_id == reserva.id)).all()
    detalles_out = [_detalle_a_out(db, d) for d in detalles]
    total_estimado = round(sum(d.subtotal or 0.0 for d in detalles_out), 2)
    return ReservaOut(
        id=reserva.id,
        usuario_id=reserva.usuario_id,
        cliente_correo=cliente.correo if cliente else None,
        cliente_celular=cliente.celular if cliente else None,
        sucursal_id=reserva.sucursal_id,
        sucursal_nombre=sucursal.nombre if sucursal else None,
        personal_id=reserva.personal_id,
        fecha_reserva=reserva.fecha_reserva,
        horario_atencion=reserva.horario_atencion,
        estado=reserva.estado.value,
        total_estimado=total_estimado,
        detalles=detalles_out,
    )


def _reservas_a_out_bulk(db: Session, reservas: List[Reserva]) -> List[ReservaOut]:
    """Igual que _reserva_a_out pero para listados: precarga todo en pocas consultas
    en lugar de una consulta por reserva y por detalle (evita el N+1 que hacia muy
    lento el listado de reservas de una sucursal con varias decenas de reservas)."""
    if not reservas:
        return []

    reserva_ids = [r.id for r in reservas]
    sucursal_ids = {r.sucursal_id for r in reservas}
    usuario_ids = {r.usuario_id for r in reservas}

    sucursales = {s.id: s for s in db.scalars(select(Sucursal).where(Sucursal.id.in_(sucursal_ids)))}
    usuarios = {u.id: u for u in db.scalars(select(Usuario).where(Usuario.id.in_(usuario_ids)))}

    detalles = db.scalars(select(DetalleReserva).where(DetalleReserva.reserva_id.in_(reserva_ids))).all()
    variante_ids = {d.variante_id for d in detalles}
    variantes = {v.id: v for v in db.scalars(select(VariantePrenda).where(VariantePrenda.id.in_(variante_ids)))} if variante_ids else {}
    prenda_ids = {v.prenda_id for v in variantes.values()}
    talla_ids = {v.talla_id for v in variantes.values()}
    color_ids = {v.color_id for v in variantes.values()}
    prendas = {p.id: p for p in db.scalars(select(Prenda).where(Prenda.id.in_(prenda_ids)))} if prenda_ids else {}
    tallas = {t.id: t for t in db.scalars(select(Talla).where(Talla.id.in_(talla_ids)))} if talla_ids else {}
    colores = {c.id: c for c in db.scalars(select(Color).where(Color.id.in_(color_ids)))} if color_ids else {}

    detalles_por_reserva: dict[int, list[DetalleReserva]] = {}
    for d in detalles:
        detalles_por_reserva.setdefault(d.reserva_id, []).append(d)

    def _detalle_out(d: DetalleReserva) -> DetalleReservaOut:
        variante = variantes.get(d.variante_id)
        prenda = prendas.get(variante.prenda_id) if variante else None
        talla = tallas.get(variante.talla_id) if variante else None
        color = colores.get(variante.color_id) if variante else None
        precio = float(prenda.precio_base) if prenda else 0.0
        subtotal = round(precio * d.cantidad, 2)
        return DetalleReservaOut(
            id=d.id,
            variante_id=d.variante_id,
            cantidad=d.cantidad,
            prenda_id=prenda.id if prenda else None,
            prenda_nombre=prenda.nombre if prenda else None,
            talla_nombre=talla.nombre if talla else None,
            color_nombre=color.nombre if color else None,
            codigo_barras=variante.codigo_barras if variante else None,
            precio_unitario=precio,
            subtotal=subtotal,
        )

    resultado = []
    for r in reservas:
        sucursal = sucursales.get(r.sucursal_id)
        cliente = usuarios.get(r.usuario_id)
        detalles_out = [_detalle_out(d) for d in detalles_por_reserva.get(r.id, [])]
        total_estimado = round(sum(d.subtotal or 0.0 for d in detalles_out), 2)
        resultado.append(
            ReservaOut(
                id=r.id,
                usuario_id=r.usuario_id,
                cliente_correo=cliente.correo if cliente else None,
                cliente_celular=cliente.celular if cliente else None,
                sucursal_id=r.sucursal_id,
                sucursal_nombre=sucursal.nombre if sucursal else None,
                personal_id=r.personal_id,
                fecha_reserva=r.fecha_reserva,
                horario_atencion=r.horario_atencion,
                estado=r.estado.value,
                total_estimado=total_estimado,
                detalles=detalles_out,
            )
        )
    return resultado


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

    # Validar stock disponible suficiente para cada variante en esa sucursal
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

    # Crear la reserva y sus detalles
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

        # Incrementar stockReservado (y descontar de stockDisponible) por sucursal
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
    return _reservas_a_out_bulk(db, reservas)


@router.get("/sucursal/{sucursal_id}", response_model=List[ReservaOut])
def listar_reservas_sucursal(
    sucursal_id: int,
    estado: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_roles(_ROLES_LECTURA_RESERVAS_SUCURSAL)),
):
    """Listar reservas asignadas a una sucursal para preparación, recepción y cobro en caja"""
    stmt = select(Reserva).where(Reserva.sucursal_id == sucursal_id)
    if estado:
        stmt = stmt.where(Reserva.estado == EstadoReserva(estado))
    stmt = stmt.order_by(Reserva.id.desc())
    reservas = db.scalars(stmt).all()
    return _reservas_a_out_bulk(db, reservas)


@router.get("/{reserva_id}", response_model=ReservaOut)
def obtener_reserva(
    reserva_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    """Consultar el detalle de una reserva (dueño o personal de sucursal)"""
    reserva = db.get(Reserva, reserva_id)
    if not reserva:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reserva no encontrada")
    if reserva.usuario_id != current_user.id:
        roles = get_user_roles(current_user.id, db)
        if not any(rol in _ROLES_LECTURA_RESERVAS_SUCURSAL for rol in roles):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reserva no encontrada")
    return _reserva_a_out(db, reserva)


@router.post("/{reserva_id}/confirmar", response_model=ReservaOut)
def confirmar_preparacion_reserva(
    reserva_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_roles(_ROLES_STAFF_SUCURSAL)),
):
    """El Encargado de Sucursal confirma que apartó físicamente las prendas de la reserva"""
    reserva = db.get(Reserva, reserva_id)
    if not reserva:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reserva no encontrada")
    if reserva.estado != EstadoReserva.pendiente:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Solo se pueden confirmar reservas en estado 'pendiente' (estado actual: {reserva.estado.value})",
        )

    reserva.estado = EstadoReserva.confirmada
    if current_user.personal:
        reserva.personal_id = current_user.personal.id

    db.commit()
    db.refresh(reserva)

    client_ip = get_client_ip(request)
    registrar_bitacora(db, current_user.id, f"Reserva #{reserva.id} confirmada/apartada", client_ip)
    push_service.enviar_push_a_usuario(
        db, reserva.usuario_id,
        "Reserva confirmada",
        f"Tu reserva #{reserva.id} fue confirmada, ya apartamos tus prendas en la sucursal.",
    )
    return _reserva_a_out(db, reserva)


@router.post("/{reserva_id}/atender", response_model=ReservaOut)
def confirmar_recepcion_cliente(
    reserva_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_roles(_ROLES_STAFF_SUCURSAL)),
):
    """El Encargado confirma la llegada del cliente a la sucursal y entrega las prendas al vestidor"""
    reserva = db.get(Reserva, reserva_id)
    if not reserva:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reserva no encontrada")
    if reserva.estado != EstadoReserva.confirmada:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Solo se puede atender una reserva previamente confirmada (estado actual: {reserva.estado.value})",
        )

    reserva.estado = EstadoReserva.atendida
    if current_user.personal:
        reserva.personal_id = current_user.personal.id

    db.commit()
    db.refresh(reserva)

    client_ip = get_client_ip(request)
    registrar_bitacora(db, current_user.id, f"Cliente recibido en sucursal - Reserva #{reserva.id} atendida", client_ip)
    push_service.enviar_push_a_usuario(
        db, reserva.usuario_id,
        "Reserva atendida",
        f"¡Gracias por tu visita! Tu reserva #{reserva.id} fue atendida.",
    )
    return _reserva_a_out(db, reserva)


@router.post("/{reserva_id}/no-show", response_model=ReservaOut)
def marcar_reserva_no_show(
    reserva_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_roles(_ROLES_STAFF_SUCURSAL)),
):
    """Excepción: el cliente no se presentó a su cita, liberando el stock reservado"""
    reserva = db.get(Reserva, reserva_id)
    if not reserva:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reserva no encontrada")
    if reserva.estado not in [EstadoReserva.pendiente, EstadoReserva.confirmada]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se puede marcar como no-show una reserva en estado '{reserva.estado.value}'",
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
                referencia_tipo="reserva_noshow",
                usuario_id=current_user.id,
                fecha=ahora,
            )
        )

    reserva.estado = EstadoReserva.expirada
    db.commit()
    db.refresh(reserva)

    client_ip = get_client_ip(request)
    registrar_bitacora(db, current_user.id, f"Reserva #{reserva.id} marcada no-show (stock liberado)", client_ip)
    push_service.enviar_push_a_usuario(
        db, reserva.usuario_id,
        "Reserva vencida",
        f"Tu reserva #{reserva.id} venció por no haberse presentado a la sucursal.",
    )
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
