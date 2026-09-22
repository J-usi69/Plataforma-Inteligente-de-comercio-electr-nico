from datetime import datetime, timezone
from typing import List, Optional

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_client_ip, get_current_active_user, get_db, get_user_roles, registrar_bitacora, require_roles
from app.core.config import settings

_ROLES_STAFF_VENTA = ["Cajero", "Encargado", "Administrador"]
from app.models.catalogo import Color, Prenda, Talla, VariantePrenda
from app.models.enums import CanalVenta, EstadoPago, EstadoReserva, EstadoVenta, TipoMovimiento
from app.models.inventario import InventarioSucursal, MovimientoInventario
from app.models.reserva import Reserva
from app.models.seguridad import Usuario
from app.models.sucursal import Ciudad, Personal, Sucursal
from app.models.venta import DetalleVenta, Pago, Venta
from app.schemas.venta import (
    CobroCajaCreate,
    ComprobanteItemOut,
    ComprobanteVentaOut,
    DetalleVentaOut,
    IntentoPagoOut,
    PagoDigitalCreate,
    PagoOut,
    VentaDigitalCreate,
    VentaOut,
    VentaPresencialCreate,
)
from app.services import push_service

router = APIRouter()

stripe.api_key = settings.stripe_secret_key


def _detalle_venta_a_out(db: Session, detalle: DetalleVenta) -> DetalleVentaOut:
    variante = db.get(VariantePrenda, detalle.variante_id)
    prenda = db.get(Prenda, variante.prenda_id) if variante else None
    talla = db.get(Talla, variante.talla_id) if variante else None
    color = db.get(Color, variante.color_id) if variante else None
    return DetalleVentaOut(
        id=detalle.id,
        variante_id=detalle.variante_id,
        cantidad=detalle.cantidad,
        precio_unitario=float(detalle.precio_unitario),
        subtotal=float(detalle.subtotal),
        prenda_id=prenda.id if prenda else None,
        prenda_nombre=prenda.nombre if prenda else None,
        talla_nombre=talla.nombre if talla else None,
        color_nombre=color.nombre if color else None,
        codigo_barras=variante.codigo_barras if variante else None,
    )


def _venta_a_out(db: Session, venta: Venta) -> VentaOut:
    sucursal = db.get(Sucursal, venta.sucursal_id)
    cliente = db.get(Usuario, venta.usuario_id) if venta.usuario_id else None
    personal = db.get(Personal, venta.personal_id) if venta.personal_id else None
    detalles = db.scalars(select(DetalleVenta).where(DetalleVenta.venta_id == venta.id)).all()
    pagos = db.scalars(select(Pago).where(Pago.venta_id == venta.id)).all()

    detalles_out = [_detalle_venta_a_out(db, d) for d in detalles]
    pagos_out = [
        PagoOut(
            id=p.id,
            venta_id=p.venta_id,
            metodo_pago=p.metodo_pago,
            pasarela=p.pasarela,
            estado=p.estado.value,
            monto=float(p.monto),
            transaccion_id=p.transaccion_id,
            fecha_pago=p.fecha_pago,
        )
        for p in pagos
    ]

    return VentaOut(
        id=venta.id,
        usuario_id=venta.usuario_id,
        cliente_nombre=cliente.correo if cliente else "Cliente Ocasional",
        cliente_correo=cliente.correo if cliente else None,
        personal_id=venta.personal_id,
        personal_nombre=f"{personal.nombres} {personal.apellidos}" if personal else None,
        sucursal_id=venta.sucursal_id,
        sucursal_nombre=sucursal.nombre if sucursal else None,
        reserva_id=venta.reserva_id,
        tipo_origen=venta.tipo_origen.value,
        estado=venta.estado.value,
        total=float(venta.total),
        fecha_venta=venta.fecha_venta,
        detalles=detalles_out,
        pagos=pagos_out,
    )


def _ventas_a_out_bulk(db: Session, ventas: List[Venta]) -> List[VentaOut]:
    """Misma salida que _venta_a_out pero cargando todo en lote (pocas consultas
    en vez de una por cada venta/detalle/pago), para listados como /mis-compras
    o /sucursal/{id} que pueden acumular muchas filas con el uso real."""
    if not ventas:
        return []

    venta_ids = [v.id for v in ventas]
    sucursal_ids = {v.sucursal_id for v in ventas}
    usuario_ids = {v.usuario_id for v in ventas if v.usuario_id}
    personal_ids = {v.personal_id for v in ventas if v.personal_id}

    sucursales = {s.id: s for s in db.scalars(select(Sucursal).where(Sucursal.id.in_(sucursal_ids)))}
    usuarios = {u.id: u for u in db.scalars(select(Usuario).where(Usuario.id.in_(usuario_ids)))} if usuario_ids else {}
    personales = {p.id: p for p in db.scalars(select(Personal).where(Personal.id.in_(personal_ids)))} if personal_ids else {}

    detalles = db.scalars(select(DetalleVenta).where(DetalleVenta.venta_id.in_(venta_ids))).all()
    pagos = db.scalars(select(Pago).where(Pago.venta_id.in_(venta_ids))).all()

    variante_ids = {d.variante_id for d in detalles}
    variantes = {v.id: v for v in db.scalars(select(VariantePrenda).where(VariantePrenda.id.in_(variante_ids)))} if variante_ids else {}
    prenda_ids = {v.prenda_id for v in variantes.values()}
    talla_ids = {v.talla_id for v in variantes.values()}
    color_ids = {v.color_id for v in variantes.values()}
    prendas = {p.id: p for p in db.scalars(select(Prenda).where(Prenda.id.in_(prenda_ids)))} if prenda_ids else {}
    tallas = {t.id: t for t in db.scalars(select(Talla).where(Talla.id.in_(talla_ids)))} if talla_ids else {}
    colores = {c.id: c for c in db.scalars(select(Color).where(Color.id.in_(color_ids)))} if color_ids else {}

    detalles_por_venta: dict[int, list[DetalleVenta]] = {}
    for d in detalles:
        detalles_por_venta.setdefault(d.venta_id, []).append(d)
    pagos_por_venta: dict[int, list[Pago]] = {}
    for p in pagos:
        pagos_por_venta.setdefault(p.venta_id, []).append(p)

    def _detalle_out(d: DetalleVenta) -> DetalleVentaOut:
        variante = variantes.get(d.variante_id)
        prenda = prendas.get(variante.prenda_id) if variante else None
        talla = tallas.get(variante.talla_id) if variante else None
        color = colores.get(variante.color_id) if variante else None
        return DetalleVentaOut(
            id=d.id,
            variante_id=d.variante_id,
            cantidad=d.cantidad,
            precio_unitario=float(d.precio_unitario),
            subtotal=float(d.subtotal),
            prenda_id=prenda.id if prenda else None,
            prenda_nombre=prenda.nombre if prenda else None,
            talla_nombre=talla.nombre if talla else None,
            color_nombre=color.nombre if color else None,
            codigo_barras=variante.codigo_barras if variante else None,
        )

    def _pago_out(p: Pago) -> PagoOut:
        return PagoOut(
            id=p.id,
            venta_id=p.venta_id,
            metodo_pago=p.metodo_pago,
            pasarela=p.pasarela,
            estado=p.estado.value,
            monto=float(p.monto),
            transaccion_id=p.transaccion_id,
            fecha_pago=p.fecha_pago,
        )

    resultado = []
    for venta in ventas:
        sucursal = sucursales.get(venta.sucursal_id)
        cliente = usuarios.get(venta.usuario_id) if venta.usuario_id else None
        personal = personales.get(venta.personal_id) if venta.personal_id else None
        resultado.append(VentaOut(
            id=venta.id,
            usuario_id=venta.usuario_id,
            cliente_nombre=cliente.correo if cliente else "Cliente Ocasional",
            cliente_correo=cliente.correo if cliente else None,
            personal_id=venta.personal_id,
            personal_nombre=f"{personal.nombres} {personal.apellidos}" if personal else None,
            sucursal_id=venta.sucursal_id,
            sucursal_nombre=sucursal.nombre if sucursal else None,
            reserva_id=venta.reserva_id,
            tipo_origen=venta.tipo_origen.value,
            estado=venta.estado.value,
            total=float(venta.total),
            fecha_venta=venta.fecha_venta,
            detalles=[_detalle_out(d) for d in detalles_por_venta.get(venta.id, [])],
            pagos=[_pago_out(p) for p in pagos_por_venta.get(venta.id, [])],
        ))
    return resultado


# ==============================================================================
# Registrar Venta Presencial (Cajero)
# ==============================================================================
@router.post("/presencial", response_model=VentaOut, status_code=status.HTTP_201_CREATED)
def registrar_venta_presencial(
    datos: VentaPresencialCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_roles(["Cajero", "Administrador"])),
):
    """El Cajero registra una venta presencial en el punto de atención"""
    if not datos.detalles:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La venta debe incluir al menos una prenda")

    # Determinar sucursal
    sucursal_id = datos.sucursal_id
    if not sucursal_id and current_user.personal and current_user.personal.sucursal_id:
        sucursal_id = current_user.personal.sucursal_id

    if not sucursal_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debe especificarse la sucursal de la venta",
        )

    sucursal = db.get(Sucursal, sucursal_id)
    if not sucursal or not sucursal.estado or sucursal.fecha_eliminacion is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Sucursal no válida")

    # Si viene vinculada a una reserva previa, validar que esté atendida
    reserva_origen = None
    if datos.reserva_id:
        reserva_origen = db.get(Reserva, datos.reserva_id)
        if not reserva_origen or reserva_origen.sucursal_id != sucursal_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La reserva indicada no corresponde a esta sucursal",
            )
        if reserva_origen.estado != EstadoReserva.atendida:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"La reserva debe estar en estado 'atendida' para registrar su venta (estado actual: {reserva_origen.estado.value})",
            )

    # Validar existencias y calcular subtotales
    items_calculados = []
    total_venta = 0.0

    for item in datos.detalles:
        variante = db.get(VariantePrenda, item.variante_id)
        if not variante or not variante.estado:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Variante #{item.variante_id} no válida",
            )

        prenda = db.get(Prenda, variante.prenda_id)
        precio_unitario = float(item.precio_unitario) if item.precio_unitario is not None else float(prenda.precio_base)
        subtotal = round(precio_unitario * item.cantidad, 2)
        total_venta += subtotal

        # Validar stock si NO proviene de reserva
        if not datos.reserva_id:
            inv = db.scalars(
                select(InventarioSucursal).where(
                    InventarioSucursal.variante_id == item.variante_id,
                    InventarioSucursal.sucursal_id == sucursal_id,
                )
            ).first()
            if not inv or inv.stock_disponible < item.cantidad:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Stock insuficiente para variante #{item.variante_id} (Disponible: {inv.stock_disponible if inv else 0})",
                )

        items_calculados.append({
            "variante_id": item.variante_id,
            "cantidad": item.cantidad,
            "precio_unitario": precio_unitario,
            "subtotal": subtotal,
        })

    # Crear la Venta
    nueva_venta = Venta(
        usuario_id=datos.cliente_id or (reserva_origen.usuario_id if reserva_origen else None),
        personal_id=current_user.personal.id if current_user.personal else None,
        sucursal_id=sucursal_id,
        reserva_id=datos.reserva_id,
        tipo_origen=CanalVenta.presencial,
        estado=EstadoVenta.pendiente,
        total=round(total_venta, 2),
        fecha_venta=datetime.now(timezone.utc),
    )
    db.add(nueva_venta)
    db.commit()
    db.refresh(nueva_venta)

    for item_data in items_calculados:
        db.add(
            DetalleVenta(
                venta_id=nueva_venta.id,
                variante_id=item_data["variante_id"],
                cantidad=item_data["cantidad"],
                precio_unitario=item_data["precio_unitario"],
                subtotal=item_data["subtotal"],
            )
        )

    db.commit()
    client_ip = get_client_ip(request)
    registrar_bitacora(db, current_user.id, f"Venta presencial #{nueva_venta.id} registrada en caja", client_ip)

    return _venta_a_out(db, nueva_venta)


# ==============================================================================
# Procesar Pago en Caja (Cajero)
# ==============================================================================
@router.post("/{venta_id}/cobrar-caja", response_model=VentaOut)
def procesar_pago_en_caja(
    venta_id: int,
    datos: CobroCajaCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_roles(["Cajero", "Administrador"])),
):
    """El cajero cobra la venta presencial y actualiza el inventario"""
    venta = db.get(Venta, venta_id)
    if not venta:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Venta no encontrada")
    if venta.estado == EstadoVenta.pagada:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Esta venta ya fue cobrada previamente")

    ahora = datetime.now(timezone.utc)

    # 1. Registrar el Pago
    nuevo_pago = Pago(
        venta_id=venta.id,
        metodo_pago=datos.metodo_pago,
        pasarela=None,
        estado=EstadoPago.aprobado,
        monto=venta.total,
        transaccion_id=f"CAJA-{venta.id}-{int(ahora.timestamp())}",
        fecha_pago=ahora,
    )
    db.add(nuevo_pago)

    # 2. Descontar Inventario según origen
    detalles = db.scalars(select(DetalleVenta).where(DetalleVenta.venta_id == venta.id)).all()

    for d in detalles:
        inv = db.scalars(
            select(InventarioSucursal).where(
                InventarioSucursal.variante_id == d.variante_id,
                InventarioSucursal.sucursal_id == venta.sucursal_id,
            )
        ).first()

        if inv:
            if venta.reserva_id is not None:
                # Venía de reserva: ya estaba en stock_reservado
                inv.stock_reservado = max(0, inv.stock_reservado - d.cantidad)
            else:
                # Venta directa: se descuenta del disponible
                inv.stock_disponible = max(0, inv.stock_disponible - d.cantidad)

        # Registrar movimiento kardex
        db.add(
            MovimientoInventario(
                variante_id=d.variante_id,
                sucursal_id=venta.sucursal_id,
                tipo_movimiento=TipoMovimiento.venta,
                cantidad=d.cantidad,
                referencia_id=venta.id,
                referencia_tipo="venta_presencial",
                usuario_id=current_user.id,
                fecha=ahora,
            )
        )

    venta.estado = EstadoVenta.pagada
    db.commit()
    db.refresh(venta)

    client_ip = get_client_ip(request)
    registrar_bitacora(db, current_user.id, f"Cobro en caja de venta #{venta.id} por Bs. {venta.total}", client_ip)

    if venta.usuario_id is not None:
        push_service.enviar_push_a_usuario(
            db, venta.usuario_id,
            "Pago aprobado",
            f"Tu pago de Bs. {venta.total} fue aprobado. ¡Gracias por tu compra!",
        )

    return _venta_a_out(db, venta)


# ==============================================================================
# Comprar desde Plataforma Web o Móvil (Cliente)
# ==============================================================================
@router.post("/digital", response_model=VentaOut, status_code=status.HTTP_201_CREATED)
def comprar_desde_plataforma_digital(
    datos: VentaDigitalCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    """El cliente confirma una compra digital desde su carrito en la web o app móvil"""
    if not datos.detalles:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El carrito de compra está vacío")

    sucursal = db.get(Sucursal, datos.sucursal_id)
    if not sucursal or not sucursal.estado or sucursal.fecha_eliminacion is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Sucursal de despacho no válida")

    # Determinar si es petición móvil o web
    user_agent = request.headers.get("user-agent", "").lower()
    tipo_origen = CanalVenta.movil if ("dart" in user_agent or "flutter" in user_agent) else CanalVenta.web

    items_calculados = []
    total_compra = 0.0

    for item in datos.detalles:
        variante = db.get(VariantePrenda, item.variante_id)
        if not variante or not variante.estado:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Variante #{item.variante_id} no disponible",
            )

        prenda = db.get(Prenda, variante.prenda_id)
        precio_unitario = float(prenda.precio_base)
        subtotal = round(precio_unitario * item.cantidad, 2)
        total_compra += subtotal

        # Validar stock en la sucursal de origen
        inv = db.scalars(
            select(InventarioSucursal).where(
                InventarioSucursal.variante_id == item.variante_id,
                InventarioSucursal.sucursal_id == datos.sucursal_id,
            )
        ).first()

        if not inv or inv.stock_disponible < item.cantidad:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Stock insuficiente para '{prenda.nombre}' en la sucursal seleccionada",
            )

        items_calculados.append({
            "variante_id": item.variante_id,
            "cantidad": item.cantidad,
            "precio_unitario": precio_unitario,
            "subtotal": subtotal,
        })

    nueva_venta = Venta(
        usuario_id=current_user.id,
        personal_id=None,
        sucursal_id=datos.sucursal_id,
        reserva_id=None,
        tipo_origen=tipo_origen,
        estado=EstadoVenta.pendiente,
        total=round(total_compra, 2),
        fecha_venta=datetime.now(timezone.utc),
    )
    db.add(nueva_venta)
    db.commit()
    db.refresh(nueva_venta)

    for item_data in items_calculados:
        db.add(
            DetalleVenta(
                venta_id=nueva_venta.id,
                variante_id=item_data["variante_id"],
                cantidad=item_data["cantidad"],
                precio_unitario=item_data["precio_unitario"],
                subtotal=item_data["subtotal"],
            )
        )

    db.commit()
    client_ip = get_client_ip(request)
    registrar_bitacora(db, current_user.id, f"Orden de compra digital #{nueva_venta.id} generada", client_ip)

    return _venta_a_out(db, nueva_venta)


# ==============================================================================
# Crear Intento de Pago con Stripe (solo para metodo_pago == "tarjeta")
# ==============================================================================
@router.post("/{venta_id}/crear-intento-pago", response_model=IntentoPagoOut)
def crear_intento_pago(
    venta_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    """Crea un PaymentIntent de Stripe por el total de la venta y devuelve el client_secret
    que el frontend usa para confirmar el pago con Stripe.js/Elements (nunca vemos el
    numero de tarjeta en nuestro backend)."""
    venta = db.get(Venta, venta_id)
    if not venta or venta.usuario_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Venta no encontrada")
    if venta.estado == EstadoVenta.pagada:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Esta compra ya se encuentra pagada")

    try:
        intento = stripe.PaymentIntent.create(
            amount=int(round(float(venta.total) * 100)),  # Stripe trabaja en centavos
            currency="usd",  # Stripe no soporta BOB; se usa USD para el entorno de pruebas
            payment_method_types=["card"],  # solo tarjeta: evita métodos que requieren redirect (return_url)
            metadata={"venta_id": str(venta.id), "usuario_id": str(current_user.id)},
        )
    except stripe.error.StripeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Error de Stripe: {exc.user_message or str(exc)}")

    return IntentoPagoOut(client_secret=intento.client_secret)


# ==============================================================================
# Procesar Pago Electrónico (Pasarela Digital)
# ==============================================================================
@router.post("/{venta_id}/pagar-digital", response_model=VentaOut)
def procesar_pago_electronico(
    venta_id: int,
    datos: PagoDigitalCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    """Cobro digital de la venta mediante Stripe (tarjeta)"""
    venta = db.get(Venta, venta_id)
    if not venta or venta.usuario_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Venta no encontrada")
    if venta.estado == EstadoVenta.pagada:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Esta compra ya se encuentra pagada")

    if datos.metodo_pago != "tarjeta":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El único método de pago digital disponible es tarjeta")

    ahora = datetime.now(timezone.utc)

    # El pago con tarjeta pasa por Stripe: no confiamos en lo que diga el
    # frontend, verificamos el estado real del PaymentIntent contra la API.
    if not datos.stripe_payment_intent_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Falta el identificador del pago de Stripe")

    try:
        intento = stripe.PaymentIntent.retrieve(datos.stripe_payment_intent_id)
    except stripe.error.StripeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Error de Stripe: {exc.user_message or str(exc)}")

    if intento.metadata.get("venta_id") != str(venta.id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El pago de Stripe no corresponde a esta venta")
    if intento.status != "succeeded":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"El pago con Stripe no se completó (estado: {intento.status})")

    transaccion_id = intento.id
    pasarela = "Stripe"

    # Registrar el pago digital
    nuevo_pago = Pago(
        venta_id=venta.id,
        metodo_pago=datos.metodo_pago,
        pasarela=pasarela,
        estado=EstadoPago.aprobado,
        monto=venta.total,
        transaccion_id=transaccion_id,
        fecha_pago=ahora,
    )
    db.add(nuevo_pago)

    # Descontar inventario digital
    detalles = db.scalars(select(DetalleVenta).where(DetalleVenta.venta_id == venta.id)).all()
    for d in detalles:
        inv = db.scalars(
            select(InventarioSucursal).where(
                InventarioSucursal.variante_id == d.variante_id,
                InventarioSucursal.sucursal_id == venta.sucursal_id,
            )
        ).first()

        if inv:
            inv.stock_disponible = max(0, inv.stock_disponible - d.cantidad)

        db.add(
            MovimientoInventario(
                variante_id=d.variante_id,
                sucursal_id=venta.sucursal_id,
                tipo_movimiento=TipoMovimiento.venta,
                cantidad=d.cantidad,
                referencia_id=venta.id,
                referencia_tipo="venta_digital",
                usuario_id=current_user.id,
                fecha=ahora,
            )
        )

    venta.estado = EstadoVenta.pagada
    db.commit()
    db.refresh(venta)

    client_ip = get_client_ip(request)
    registrar_bitacora(db, current_user.id, f"Pago electrónico aprobado para venta #{venta.id} ({transaccion_id})", client_ip)

    if venta.usuario_id is not None:
        push_service.enviar_push_a_usuario(
            db, venta.usuario_id,
            "Pago aprobado",
            f"Tu pedido #{venta.id} ya está pagado y listo para entrega/retiro.",
        )

    return _venta_a_out(db, venta)


# ==============================================================================
# Emitir Comprobante de Venta
# ==============================================================================
@router.get("/comprobante/{venta_id}", response_model=ComprobanteVentaOut)
def emitir_comprobante_venta(
    venta_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    """Generar comprobante oficial respaldando una venta pagada"""
    venta = db.get(Venta, venta_id)
    if not venta:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Venta no encontrada")
    if venta.usuario_id != current_user.id:
        roles = get_user_roles(current_user.id, db)
        if not any(rol in _ROLES_STAFF_VENTA for rol in roles):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Venta no encontrada")

    sucursal = db.get(Sucursal, venta.sucursal_id)
    ciudad = db.get(Ciudad, sucursal.ciudad_id) if sucursal else None
    cliente = db.get(Usuario, venta.usuario_id) if venta.usuario_id else None
    cajero = db.get(Personal, venta.personal_id) if venta.personal_id else None
    pago = db.scalars(select(Pago).where(Pago.venta_id == venta.id, Pago.estado == EstadoPago.aprobado)).first()

    detalles = db.scalars(select(DetalleVenta).where(DetalleVenta.venta_id == venta.id)).all()
    items_out = []
    for d in detalles:
        variante = db.get(VariantePrenda, d.variante_id)
        prenda = db.get(Prenda, variante.prenda_id) if variante else None
        talla = db.get(Talla, variante.talla_id) if variante else None
        color = db.get(Color, variante.color_id) if variante else None

        items_out.append(
            ComprobanteItemOut(
                descripcion=prenda.nombre if prenda else "Prenda de moda",
                talla=talla.nombre if talla else None,
                color=color.nombre if color else None,
                codigo_barras=variante.codigo_barras if variante else None,
                cantidad=d.cantidad,
                precio_unitario=float(d.precio_unitario),
                subtotal=float(d.subtotal),
            )
        )

    correlativo = f"FS-2026-{venta.id:06d}"

    return ComprobanteVentaOut(
        numero_comprobante=correlativo,
        venta_id=venta.id,
        fecha_emision=venta.fecha_venta,
        tipo_origen=venta.tipo_origen.value.upper(),
        sucursal_nombre=sucursal.nombre if sucursal else "Sucursal Central",
        sucursal_direccion=sucursal.direccion if sucursal else "Santa Cruz, Bolivia",
        sucursal_telefono=sucursal.telefono if sucursal else None,
        ciudad_nombre=ciudad.nombre if ciudad else "Santa Cruz",
        cajero_nombre=f"{cajero.nombres} {cajero.apellidos}" if cajero else "Sistema Online",
        cliente_nombre=cliente.correo if cliente else "Cliente Mostrador",
        cliente_correo=cliente.correo if cliente else None,
        metodo_pago=pago.metodo_pago.upper() if pago else "EFECTIVO",
        transaccion_id=pago.transaccion_id if pago else None,
        estado_venta=venta.estado.value.upper(),
        subtotal=float(venta.total),
        total=float(venta.total),
        items=items_out,
    )


# ==============================================================================
# Consultar Historial de Compras (Cliente)
# ==============================================================================
@router.get("/mis-compras", response_model=List[VentaOut])
def consultar_historial_compras(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    """El cliente consulta el historial de sus compras anteriores (presenciales y digitales)"""
    stmt = select(Venta).where(Venta.usuario_id == current_user.id).order_by(Venta.fecha_venta.desc())
    ventas = db.scalars(stmt).all()
    return _ventas_a_out_bulk(db, ventas)


@router.get("/sucursal/{sucursal_id}", response_model=List[VentaOut])
def listar_ventas_sucursal(
    sucursal_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_roles(_ROLES_STAFF_VENTA)),
):
    """Consultar las ventas registradas en una sucursal específica (Cajero/Encargado/Admin)"""
    stmt = select(Venta).where(Venta.sucursal_id == sucursal_id).order_by(Venta.id.desc())
    ventas = db.scalars(stmt).all()
    return _ventas_a_out_bulk(db, ventas)


@router.get("/{venta_id}", response_model=VentaOut)
def obtener_venta(
    venta_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    """Consultar el detalle de una venta por ID (dueño o personal)"""
    venta = db.get(Venta, venta_id)
    if not venta:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Venta no encontrada")
    if venta.usuario_id != current_user.id:
        roles = get_user_roles(current_user.id, db)
        if not any(rol in _ROLES_STAFF_VENTA for rol in roles):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Venta no encontrada")
    return _venta_a_out(db, venta)

