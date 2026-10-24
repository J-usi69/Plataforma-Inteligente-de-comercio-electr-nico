"""Sincronización de la operación sin conexión (PWA y app móvil).

El dispositivo registra ventas de contado, reservas y cambios de prendas sin Internet, cada uno
con un id propio (UUID), y al volver la conexión los sube en lote. Reglas:

- Idempotencia (RNF05): el id es único por tienda. Si la operación vuelve a llegar (se cortó la
  respuesta, se tocó "sincronizar" dos veces) se devuelve el resultado guardado sin aplicarla de
  nuevo.
- Integridad (RNF04): cada operación es una transacción. La venta, su pago, el descuento del
  inventario con su kardex y el registro de la operación se guardan juntos o no se guarda nada.
  Una operación que no se puede aplicar no frena a las demás del lote.
- Resultado de cada una:
  * confirmada.
  * rechazada: no cumple una regla y no tiene arreglo (variante inexistente, fuera del plazo de
    cambio, sucursal ajena...). El dispositivo muestra el motivo y no la reintenta.
  * conflicto: la venta o el cambio ya ocurrieron en la tienda (se entregó la prenda y se cobró)
    pero el inventario central no alcanza. Ni se descarta ni se aplica sola: la resuelve un
    encargado (aceptar la registra y deja el faltante en el kardex; rechazar la anula).
  * error: falla inesperada del servidor. No se guarda nada; el dispositivo la conserva y la
    reintenta (RNF06).
- Observabilidad (RNF10): cada operación queda registrada (estado, motivo, intentos, fechas) y se
  loguea con el id del pedido, sin datos personales.

Las operaciones se procesan en el orden en que llegan: un cambio de una venta hecha sin conexión
tiene que viajar después de esa venta (en el mismo lote o en uno posterior).
"""
import hashlib
import json
import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional, Sequence
from uuid import UUID

from fastapi import HTTPException, status
from pydantic import BaseModel, ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.tenancy import CLAVE_TIENDA
from app.models.catalogo import Categoria, Color, Prenda, Talla, VariantePrenda
from app.models.enums import CanalVenta, EstadoPago, EstadoReserva, EstadoVenta, TipoMovimiento
from app.models.inventario import InventarioSucursal, MovimientoInventario
from app.models.reserva import DetalleReserva, Reserva
from app.models.seguridad import Rol, Usuario, UsuarioRol
from app.models.sincronizacion import CambioPrenda, DetalleCambio, OperacionSync
from app.models.sucursal import Ciudad, Sucursal
from app.models.tienda import Tienda
from app.models.venta import DetalleVenta, Pago, Venta
from app.schemas.sincronizacion import (
    CambioOfflineIn,
    ClientePaqueteOut,
    ColorPaqueteOut,
    DetalleVentaPaqueteOut,
    EstadoOperacionesOut,
    InventarioPaqueteOut,
    ItemNombreOut,
    LineaConPrecioIn,
    OperacionAdminOut,
    OperacionIn,
    PaqueteOut,
    PrendaPaqueteOut,
    ReservaOfflineIn,
    ResultadoOperacionOut,
    SucursalPaqueteOut,
    VariantePaqueteOut,
    VentaOfflineIn,
    VentaPaqueteOut,
)
from app.services.inventario_service import bloquear_inventario as _bloquear_inventario

logger = logging.getLogger("fashionstore.sync")

CONFIRMADA, RECHAZADA, CONFLICTO, ERROR = "confirmada", "rechazada", "conflicto", "error"
ROLES_PERSONAL = frozenset({"Cajero", "Encargado", "Administrador"})
# Quién puede registrar cada tipo. None: cualquier usuario de la tienda (un cliente reserva para sí)
ROLES_POR_TIPO: dict[str, Optional[frozenset[str]]] = {
    "venta": frozenset({"Cajero", "Administrador"}),  # los mismos que cobran en caja
    "cambio": ROLES_PERSONAL,
    "reserva": None,
}
TOLERANCIA_RELOJ = timedelta(minutes=5)  # relojes de dispositivo levemente adelantados
VIGENCIA_PAQUETE_HORAS = 12
MAX_VENTAS_EN_PAQUETE = 500


@dataclass(frozen=True)
class Actor:
    """Quién registró la operación en el dispositivo."""

    usuario: Usuario
    roles: frozenset[str]

    @property
    def es_personal(self) -> bool:
        return bool(self.roles & ROLES_PERSONAL)

    @property
    def es_admin(self) -> bool:
        return "Administrador" in self.roles

    @property
    def personal_id(self) -> Optional[int]:
        return self.usuario.personal.id if self.usuario.personal else None

    @property
    def sucursal_id(self) -> Optional[int]:
        return self.usuario.personal.sucursal_id if self.usuario.personal else None


class OperacionNoAplicable(Exception):
    def __init__(self, estado: str, codigo: str, mensaje: str):
        super().__init__(mensaje)
        self.estado, self.codigo, self.mensaje = estado, codigo, mensaje[:500]


def _rechazo(codigo: str, mensaje: str) -> OperacionNoAplicable:
    return OperacionNoAplicable(RECHAZADA, codigo, mensaje)


def _conflicto(codigo: str, mensaje: str) -> OperacionNoAplicable:
    return OperacionNoAplicable(CONFLICTO, codigo, mensaje)


@dataclass
class _Efecto:
    referencia_tipo: str
    referencia_id: int
    sucursal_id: int
    observacion: Optional[str] = None


@dataclass
class _Contexto:
    db: Session
    tienda: Tienda
    actor: Actor
    sucursal: Sucursal
    fecha: datetime  # cuándo ocurrió en la tienda (hora del dispositivo, nunca futura)
    ahora: datetime
    operacion_id: UUID
    forzar: bool  # conflicto aceptado por un encargado: se aplica aunque el stock no alcance


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


def _con_zona(fecha: datetime) -> datetime:
    return fecha if fecha.tzinfo else fecha.replace(tzinfo=timezone.utc)


def _tienda(db: Session) -> Tienda:
    return db.get(Tienda, db.info[CLAVE_TIENDA])


# ==============================================================================
# Recepción de operaciones
# ==============================================================================
def procesar_operacion(db: Session, actor: Actor, op: OperacionIn, request_id: Optional[str] = None) -> ResultadoOperacionOut:
    resultado = _procesar(db, actor, op)
    logger.info(
        "sync op=%s tipo=%s sucursal=%s estado=%s codigo=%s duplicada=%s [%s]",
        op.id, op.tipo, op.sucursal_id, resultado.estado, resultado.codigo, resultado.duplicada, request_id,
    )
    return resultado


def _procesar(db: Session, actor: Actor, op: OperacionIn) -> ResultadoOperacionOut:
    huella = _huella(op)
    previa = _buscar(db, op.id)
    if previa is not None:
        return _reenvio(db, previa, huella, op)

    ahora = _ahora()
    registro = _nuevo_registro(op, actor, huella, ahora)
    try:
        db.add(registro)
        db.flush()  # toma el id: un reenvío simultáneo espera acá y después ve el resultado guardado
        efecto = _aplicar(db, actor, op, ahora, forzar=False)
        _anotar_efecto(registro, efecto)
        db.commit()
        return resultado_de(registro)
    except OperacionNoAplicable as motivo:
        db.rollback()  # nada de lo que se alcanzó a aplicar queda
        registro = _nuevo_registro(op, actor, huella, ahora, motivo)
        sucursal = db.get(Sucursal, op.sucursal_id)
        registro.sucursal_id = sucursal.id if sucursal else None
        try:
            db.add(registro)
            db.commit()
        except IntegrityError:
            db.rollback()
            return _reenvio_simultaneo(db, op, huella)
        return resultado_de(registro)
    except IntegrityError:
        db.rollback()
        return _reenvio_simultaneo(db, op, huella)
    except Exception:
        db.rollback()
        logger.exception("sync op=%s tipo=%s: falla inesperada al procesarla", op.id, op.tipo)
        return _error(op)


def _error(op: OperacionIn) -> ResultadoOperacionOut:
    return ResultadoOperacionOut(
        id=op.id, tipo=op.tipo, estado=ERROR, codigo="error_interno",
        mensaje="No se pudo procesar ahora: queda pendiente y se volverá a enviar",
    )


def _huella(op: OperacionIn) -> str:
    contenido = op.model_dump(mode="json", exclude={"dispositivo"})
    return hashlib.sha256(json.dumps(contenido, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _buscar(db: Session, operacion_id: UUID) -> Optional[OperacionSync]:
    return db.scalars(select(OperacionSync).where(OperacionSync.uuid == operacion_id)).first()


def _nuevo_registro(
    op: OperacionIn, actor: Actor, huella: str, ahora: datetime, motivo: Optional[OperacionNoAplicable] = None
) -> OperacionSync:
    return OperacionSync(
        uuid=op.id,
        tipo=op.tipo,
        usuario_id=actor.usuario.id,
        dispositivo=op.dispositivo,
        registrada_en=_con_zona(op.registrada_en),
        recibida_en=ahora,
        ultimo_intento=ahora,
        intentos=1,
        estado=motivo.estado if motivo else CONFIRMADA,
        codigo=motivo.codigo if motivo else None,
        mensaje=motivo.mensaje if motivo else None,
        huella=huella,
        datos=op.model_dump(mode="json"),
    )


def _anotar_efecto(registro: OperacionSync, efecto: _Efecto) -> None:
    registro.estado = CONFIRMADA
    registro.sucursal_id = efecto.sucursal_id
    registro.referencia_tipo = efecto.referencia_tipo
    registro.referencia_id = efecto.referencia_id
    registro.mensaje = efecto.observacion[:500] if efecto.observacion else None


def _reenvio(db: Session, previa: OperacionSync, huella: str, op: OperacionIn) -> ResultadoOperacionOut:
    if previa.huella != huella:
        # Mismo id con otro contenido: error del dispositivo. Lo guardado no se toca
        return ResultadoOperacionOut(
            id=op.id, tipo=op.tipo, estado=RECHAZADA, codigo="id_repetido", duplicada=True,
            mensaje="Ya se recibió otra operación con este mismo identificador y distinto contenido",
        )
    previa.intentos += 1
    previa.ultimo_intento = _ahora()
    db.commit()
    return resultado_de(previa, duplicada=True)


def _reenvio_simultaneo(db: Session, op: OperacionIn, huella: str) -> ResultadoOperacionOut:
    """La misma operación llegó dos veces a la vez: la otra ganó el id y ya dejó su resultado."""
    previa = _buscar(db, op.id)
    if previa is None:  # la falla de integridad no era el id repetido
        logger.error("sync op=%s tipo=%s: falla de integridad al guardarla", op.id, op.tipo)
        return _error(op)
    return _reenvio(db, previa, huella, op)


def resultado_de(registro: OperacionSync, duplicada: bool = False) -> ResultadoOperacionOut:
    return ResultadoOperacionOut(
        id=registro.uuid,
        tipo=registro.tipo,
        estado=registro.estado,
        codigo=registro.codigo,
        mensaje=registro.mensaje,
        referencia_tipo=registro.referencia_tipo,
        referencia_id=registro.referencia_id,
        duplicada=duplicada,
        procesada_en=registro.resuelta_en or registro.recibida_en,
    )


# ==============================================================================
# Validaciones comunes y aplicación de cada tipo
# ==============================================================================
def _aplicar(db: Session, actor: Actor, op: OperacionIn, ahora: datetime, forzar: bool) -> _Efecto:
    tienda = _tienda(db)
    if op.tienda.strip().lower() != tienda.slug:
        raise _rechazo("otra_empresa", f"La operación se registró en la empresa '{op.tienda}', no en {tienda.nombre}")
    if op.tipo not in _APLICADORES:
        raise _rechazo("tipo_desconocido", f"Tipo de operación desconocido: '{op.tipo}' (venta, reserva o cambio)")
    permitidos = ROLES_POR_TIPO[op.tipo]
    if permitidos is not None and not actor.roles & permitidos:
        raise _rechazo("sin_permiso", f"Tu usuario no tiene permiso para registrar operaciones de tipo {op.tipo}")

    fecha = _con_zona(op.registrada_en)
    if fecha > ahora + TOLERANCIA_RELOJ:
        raise _rechazo("fecha_futura", "La fecha de registro es posterior a la hora del servidor: revisá el reloj del dispositivo")
    sucursal = _sucursal_autorizada(db, actor, op.sucursal_id)
    modelo, aplicador = _APLICADORES[op.tipo]
    datos = _validar(modelo, op.datos)
    contexto = _Contexto(db, tienda, actor, sucursal, min(fecha, ahora), ahora, op.id, forzar)
    return aplicador(contexto, datos)


def _validar(modelo: type[BaseModel], datos: dict) -> BaseModel:
    try:
        return modelo.model_validate(datos)
    except ValidationError as exc:
        campos = ", ".join(".".join(str(p) for p in error["loc"]) or "datos" for error in exc.errors()[:5])
        raise _rechazo("datos_invalidos", f"Datos incompletos o inválidos: {campos}")


def _sucursal_autorizada(db: Session, actor: Actor, sucursal_id: int) -> Sucursal:
    sucursal = db.get(Sucursal, sucursal_id)
    if not sucursal or not sucursal.estado or sucursal.fecha_eliminacion is not None:
        raise _rechazo("sucursal_invalida", f"La sucursal #{sucursal_id} no existe en esta empresa o está inactiva")
    # El personal opera en su sucursal; el administrador en cualquiera; un cliente reserva donde quiera
    if actor.es_personal and not actor.es_admin and actor.sucursal_id != sucursal.id:
        raise _rechazo("sucursal_no_autorizada", f"Tu usuario trabaja en otra sucursal: no puede registrar operaciones en {sucursal.nombre}")
    return sucursal


def _cliente(db: Session, cliente_id: int) -> Usuario:
    cliente = db.get(Usuario, cliente_id)
    if not cliente or not cliente.estado or cliente.fecha_eliminacion is not None:
        raise _rechazo("cliente_invalido", f"El cliente #{cliente_id} no existe en esta empresa o está dado de baja")
    return cliente


def _cantidades(lineas: Iterable) -> dict[int, int]:
    """Cantidad por variante (una misma variante puede venir en más de una línea)."""
    total: dict[int, int] = defaultdict(int)
    for linea in lineas:
        total[linea.variante_id] += linea.cantidad
    return dict(total)


def _variantes_activas(db: Session, ids: Iterable[int]) -> dict[int, tuple[VariantePrenda, Prenda]]:
    ids = set(ids)
    filas = db.execute(
        select(VariantePrenda, Prenda).join(Prenda, Prenda.id == VariantePrenda.prenda_id).where(VariantePrenda.id.in_(ids))
    ).all()
    activas = {variante.id: (variante, prenda) for variante, prenda in filas if variante.estado and prenda.estado}
    faltan = sorted(ids - activas.keys())
    if faltan:
        raise _rechazo("variante_invalida", f"Prendas inexistentes o dadas de baja: {', '.join(f'variante #{i}' for i in faltan)}")
    return activas


def _faltantes(
    inventario: dict[int, InventarioSucursal],
    pedidas: dict[int, int],
    variantes: dict[int, tuple[VariantePrenda, Prenda]],
    vuelven: Optional[dict[int, int]] = None,
) -> list[str]:
    vuelven = vuelven or {}
    faltantes = []
    for variante_id, cantidad in sorted(pedidas.items()):
        fila = inventario.get(variante_id)
        disponible = (fila.stock_disponible if fila else 0) + vuelven.get(variante_id, 0)
        if disponible < cantidad:
            nombre = variantes[variante_id][1].nombre
            faltantes.append(f"{nombre} (variante #{variante_id}): {cantidad} pedidas, {max(disponible, 0)} en el sistema")
    return faltantes


def _fila_inventario(ctx: _Contexto, inventario: dict[int, InventarioSucursal], variante_id: int) -> InventarioSucursal:
    fila = inventario.get(variante_id)
    if fila is None:
        fila = InventarioSucursal(
            variante_id=variante_id, sucursal_id=ctx.sucursal.id, stock_disponible=0, stock_reservado=0, stock_minimo=0
        )
        ctx.db.add(fila)
        inventario[variante_id] = fila
    return fila


def _kardex(
    ctx: _Contexto, variante_id: int, tipo: TipoMovimiento, cantidad: int, referencia_tipo: str, referencia_id: int,
    fecha: Optional[datetime] = None,
) -> None:
    ctx.db.add(
        MovimientoInventario(
            variante_id=variante_id,
            sucursal_id=ctx.sucursal.id,
            tipo_movimiento=tipo,
            cantidad=cantidad,
            referencia_id=referencia_id,
            referencia_tipo=referencia_tipo,
            usuario_id=ctx.actor.usuario.id,
            fecha=fecha or ctx.fecha,
        )
    )


def _descontar(ctx: _Contexto, inventario: dict[int, InventarioSucursal], pedidas: dict[int, int], referencia_tipo: str, referencia_id: int) -> None:
    """Saca del disponible lo que salió de la tienda. Si no alcanza (conflicto aceptado por un
    encargado), el faltante entra antes como ajuste: el stock no queda negativo y el kardex
    explica la diferencia."""
    for variante_id, cantidad in sorted(pedidas.items()):
        fila = _fila_inventario(ctx, inventario, variante_id)
        faltante = cantidad - fila.stock_disponible
        if faltante > 0:
            fila.stock_disponible += faltante
            _kardex(ctx, variante_id, TipoMovimiento.ajuste, faltante, "faltante_sync", referencia_id, fecha=ctx.ahora)
        fila.stock_disponible -= cantidad
        _kardex(ctx, variante_id, TipoMovimiento.venta, cantidad, referencia_tipo, referencia_id)


def _subtotal(linea: LineaConPrecioIn) -> float:
    return round(linea.precio_unitario * linea.cantidad, 2)


def _precios_distintos(lineas: Sequence[LineaConPrecioIn], variantes: dict[int, tuple[VariantePrenda, Prenda]]) -> list[str]:
    """Sin conexión se cobra con el precio que tenía el dispositivo; si cambió mientras tanto, la
    operación se acepta igual (el cliente ya pagó) y queda anotado."""
    distintos = []
    for linea in lineas:
        prenda = variantes[linea.variante_id][1]
        lista = float(prenda.precio_base)
        if abs(lista - linea.precio_unitario) > 0.005:
            distintos.append(f"{prenda.nombre} a Bs. {linea.precio_unitario:.2f} (lista actual Bs. {lista:.2f})")
    return [f"Precio distinto al de lista: {', '.join(distintos)}"] if distintos else []


def _aplicar_venta(ctx: _Contexto, datos: VentaOfflineIn) -> _Efecto:
    cliente_id = _cliente(ctx.db, datos.cliente_id).id if datos.cliente_id else None
    pedidas = _cantidades(datos.detalles)
    variantes = _variantes_activas(ctx.db, pedidas)
    total = round(sum(_subtotal(d) for d in datos.detalles), 2)
    if abs(total - datos.total) > 0.01:
        raise _rechazo("total_inconsistente", f"El total enviado (Bs. {datos.total:.2f}) no coincide con el detalle (Bs. {total:.2f})")
    if datos.monto_recibido is not None and datos.monto_recibido < total - 0.005:
        raise _rechazo("monto_insuficiente", f"El efectivo recibido (Bs. {datos.monto_recibido:.2f}) no cubre el total (Bs. {total:.2f})")

    inventario = _bloquear_inventario(ctx.db, ctx.sucursal.id, pedidas)
    faltantes = _faltantes(inventario, pedidas, variantes)
    if faltantes and not ctx.forzar:
        raise _conflicto("sin_stock", "La venta se hizo en la tienda pero el inventario del sistema no alcanza: " + "; ".join(faltantes))

    venta = Venta(
        usuario_id=cliente_id,
        personal_id=ctx.actor.personal_id,
        sucursal_id=ctx.sucursal.id,
        reserva_id=None,
        tipo_origen=CanalVenta.presencial,
        estado=EstadoVenta.pagada,
        total=total,
        fecha_venta=ctx.fecha,
    )
    ctx.db.add(venta)
    ctx.db.flush()
    for detalle in datos.detalles:
        ctx.db.add(
            DetalleVenta(
                venta_id=venta.id, variante_id=detalle.variante_id, cantidad=detalle.cantidad,
                precio_unitario=detalle.precio_unitario, subtotal=_subtotal(detalle),
            )
        )
    ctx.db.add(
        Pago(
            venta_id=venta.id, metodo_pago=datos.metodo_pago, pasarela=None, estado=EstadoPago.aprobado,
            monto=total, transaccion_id=f"OFFLINE-{ctx.operacion_id}", fecha_pago=ctx.fecha,
        )
    )
    _descontar(ctx, inventario, pedidas, "venta_offline", venta.id)

    observaciones = _precios_distintos(datos.detalles, variantes)
    if faltantes:
        observaciones.append("Aceptada con faltante de inventario: " + "; ".join(faltantes))
    return _Efecto("venta", venta.id, ctx.sucursal.id, " | ".join(observaciones) or None)


def _aplicar_reserva(ctx: _Contexto, datos: ReservaOfflineIn) -> _Efecto:
    if ctx.actor.es_personal:
        if not datos.cliente_id:
            raise _rechazo("falta_cliente", "Una reserva registrada por el personal debe indicar el cliente")
        cliente = _cliente(ctx.db, datos.cliente_id)
    else:
        if datos.cliente_id not in (None, ctx.actor.usuario.id):
            raise _rechazo("sin_permiso", "Un cliente solo puede reservar para sí mismo")
        cliente = ctx.actor.usuario

    pedidas = _cantidades(datos.detalles)
    variantes = _variantes_activas(ctx.db, pedidas)
    inventario = _bloquear_inventario(ctx.db, ctx.sucursal.id, pedidas)
    faltantes = _faltantes(inventario, pedidas, variantes)
    if faltantes:
        # Una reserva todavía no movió prendas ni dinero: sin stock se rechaza y el cliente elige otra cosa
        raise _rechazo("sin_stock", "Ya no hay stock para reservar: " + "; ".join(faltantes))

    reserva = Reserva(
        usuario_id=cliente.id,
        sucursal_id=ctx.sucursal.id,
        personal_id=ctx.actor.personal_id if ctx.actor.es_personal else None,
        fecha_reserva=ctx.fecha,
        horario_atencion=datos.horario_atencion,
        estado=EstadoReserva.pendiente,
    )
    ctx.db.add(reserva)
    ctx.db.flush()
    for variante_id, cantidad in sorted(pedidas.items()):
        ctx.db.add(DetalleReserva(reserva_id=reserva.id, variante_id=variante_id, cantidad=cantidad))
        fila = inventario[variante_id]
        fila.stock_disponible -= cantidad
        fila.stock_reservado += cantidad
        _kardex(ctx, variante_id, TipoMovimiento.reserva, cantidad, "reserva_offline", reserva.id)
    return _Efecto("reserva", reserva.id, ctx.sucursal.id)


def _venta_a_cambiar(db: Session, datos: CambioOfflineIn) -> Venta:
    """La venta original, bloqueada hasta el commit: dos cambios de la misma venta a la vez no
    pueden devolver dos veces la misma prenda."""
    venta_id = datos.venta_id
    if venta_id is None and datos.venta_operacion_id is not None:
        origen = _buscar(db, datos.venta_operacion_id)
        if origen is None or origen.estado == CONFLICTO:
            raise _conflicto("venta_no_confirmada", "La venta original todavía no está confirmada en el servidor: el cambio queda a la espera")
        if origen.tipo != "venta" or origen.estado != CONFIRMADA:
            raise _rechazo("venta_inexistente", "La venta original fue rechazada: no se puede cambiar")
        venta_id = origen.referencia_id
    if venta_id is None:
        raise _rechazo("falta_venta", "El cambio debe indicar la venta original")
    venta = db.scalars(select(Venta).where(Venta.id == venta_id).with_for_update()).first()
    if not venta:
        raise _rechazo("venta_inexistente", f"No existe la venta #{venta_id} en esta empresa")
    return venta


def _vendidas(db: Session, venta_ids: Sequence[int]) -> dict[int, dict[int, tuple[int, float]]]:
    """venta -> variante -> (cantidad vendida, precio unitario pagado)."""
    filas = db.execute(
        select(DetalleVenta.venta_id, DetalleVenta.variante_id, func.sum(DetalleVenta.cantidad), func.sum(DetalleVenta.subtotal))
        .where(DetalleVenta.venta_id.in_(venta_ids))
        .group_by(DetalleVenta.venta_id, DetalleVenta.variante_id)
    ).all()
    vendidas: dict[int, dict[int, tuple[int, float]]] = defaultdict(dict)
    for venta_id, variante_id, cantidad, subtotal in filas:
        vendidas[venta_id][variante_id] = (int(cantidad), round(float(subtotal) / int(cantidad), 2))
    return vendidas


def _devueltas(db: Session, venta_ids: Sequence[int]) -> dict[tuple[int, int], int]:
    """(venta, variante) -> cantidad ya devuelta en cambios anteriores."""
    filas = db.execute(
        select(CambioPrenda.venta_id, DetalleCambio.variante_id, func.sum(DetalleCambio.cantidad))
        .join(CambioPrenda, CambioPrenda.id == DetalleCambio.cambio_id)
        .where(CambioPrenda.venta_id.in_(venta_ids), DetalleCambio.tipo == "devuelve")
        .group_by(CambioPrenda.venta_id, DetalleCambio.variante_id)
    ).all()
    return {(venta_id, variante_id): int(cantidad) for venta_id, variante_id, cantidad in filas}


def _aplicar_cambio(ctx: _Contexto, datos: CambioOfflineIn) -> _Efecto:
    venta = _venta_a_cambiar(ctx.db, datos)
    if venta.estado != EstadoVenta.pagada:
        raise _rechazo("venta_no_pagada", f"La venta #{venta.id} no está pagada (estado: {venta.estado.value})")
    dias = ctx.tienda.dias_para_cambio
    limite = venta.fecha_venta + timedelta(days=dias)
    # El plazo se cuenta hasta el momento del cambio en la tienda, no hasta que se sincronizó
    if ctx.fecha > limite:
        raise _rechazo(
            "fuera_de_plazo",
            f"El plazo de cambio es de {dias} días: la venta #{venta.id} es del {venta.fecha_venta:%d/%m/%Y} "
            f"y se podía cambiar hasta el {limite:%d/%m/%Y}",
        )
    if ctx.fecha < venta.fecha_venta - TOLERANCIA_RELOJ:
        raise _rechazo("fecha_invalida", "El cambio figura antes que la venta: revisá el reloj del dispositivo")

    vendidas = _vendidas(ctx.db, [venta.id]).get(venta.id, {})
    devueltas_antes = _devueltas(ctx.db, [venta.id])
    devuelve = _cantidades(datos.devuelve)
    for variante_id, cantidad in sorted(devuelve.items()):
        if variante_id not in vendidas:
            raise _rechazo("no_estaba_en_la_venta", f"La variante #{variante_id} no forma parte de la venta #{venta.id}")
        vendida = vendidas[variante_id][0]
        quedan = vendida - devueltas_antes.get((venta.id, variante_id), 0)
        if cantidad > quedan:
            raise _rechazo(
                "cantidad_excede",
                f"De la variante #{variante_id} se vendieron {vendida} y quedan {quedan} sin cambiar; se quieren devolver {cantidad}",
            )

    entrega = _cantidades(datos.entrega)
    variantes = _variantes_activas(ctx.db, entrega)
    total_devuelto = round(sum(cantidad * vendidas[vid][1] for vid, cantidad in devuelve.items()), 2)
    total_entregado = round(sum(_subtotal(linea) for linea in datos.entrega), 2)
    diferencia = round(total_entregado - total_devuelto, 2)
    if diferencia < 0:
        raise _rechazo(
            "cambio_de_menor_valor",
            f"Lo que se entrega (Bs. {total_entregado:.2f}) vale menos que lo devuelto (Bs. {total_devuelto:.2f}): "
            "el cambio es por prendas de igual o mayor valor",
        )
    if abs(diferencia - datos.diferencia) > 0.01:
        raise _rechazo("diferencia_inconsistente", f"La diferencia enviada (Bs. {datos.diferencia:.2f}) no coincide con la calculada (Bs. {diferencia:.2f})")

    inventario = _bloquear_inventario(ctx.db, ctx.sucursal.id, devuelve.keys() | entrega.keys())
    # Lo devuelto vuelve al estante antes de entregar: se puede cambiar por la misma prenda (falla de fábrica)
    faltantes = _faltantes(inventario, entrega, variantes, vuelven=devuelve)
    if faltantes and not ctx.forzar:
        raise _conflicto("sin_stock", "El cambio se hizo en la tienda pero el inventario del sistema no alcanza: " + "; ".join(faltantes))

    cambio = CambioPrenda(
        venta_id=venta.id,
        sucursal_id=ctx.sucursal.id,
        usuario_id=ctx.actor.usuario.id,
        fecha=ctx.fecha,
        motivo=datos.motivo,
        total_devuelto=total_devuelto,
        total_entregado=total_entregado,
        diferencia=diferencia,
        metodo_pago=datos.metodo_pago,
    )
    ctx.db.add(cambio)
    ctx.db.flush()
    for variante_id, cantidad in sorted(devuelve.items()):
        ctx.db.add(DetalleCambio(cambio_id=cambio.id, variante_id=variante_id, tipo="devuelve", cantidad=cantidad, precio_unitario=vendidas[variante_id][1]))
        _fila_inventario(ctx, inventario, variante_id).stock_disponible += cantidad
        _kardex(ctx, variante_id, TipoMovimiento.devolucion, cantidad, "cambio", cambio.id)
    for linea in datos.entrega:
        ctx.db.add(DetalleCambio(cambio_id=cambio.id, variante_id=linea.variante_id, tipo="entrega", cantidad=linea.cantidad, precio_unitario=linea.precio_unitario))
    _descontar(ctx, inventario, entrega, "cambio", cambio.id)

    observaciones = _precios_distintos(datos.entrega, variantes)
    if faltantes:
        observaciones.append("Aceptado con faltante de inventario: " + "; ".join(faltantes))
    return _Efecto("cambio", cambio.id, ctx.sucursal.id, " | ".join(observaciones) or None)


_APLICADORES = {
    "venta": (VentaOfflineIn, _aplicar_venta),
    "reserva": (ReservaOfflineIn, _aplicar_reserva),
    "cambio": (CambioOfflineIn, _aplicar_cambio),
}


# ==============================================================================
# Consulta, supervisión y resolución de conflictos
# ==============================================================================
def estado_de(db: Session, ids: Sequence[UUID], solo_del_usuario: Optional[int] = None) -> EstadoOperacionesOut:
    consulta = select(OperacionSync).where(OperacionSync.uuid.in_(ids))
    if solo_del_usuario is not None:
        consulta = consulta.where(OperacionSync.usuario_id == solo_del_usuario)
    registros = db.scalars(consulta).all()
    recibidas = {r.uuid for r in registros}
    return EstadoOperacionesOut(
        resultados=[resultado_de(r) for r in registros],
        desconocidas=[i for i in dict.fromkeys(ids) if i not in recibidas],
    )


def listar(db: Session, estado: Optional[str], sucursal_id: Optional[int], limite: int) -> list[OperacionAdminOut]:
    consulta = select(OperacionSync).order_by(OperacionSync.recibida_en.desc(), OperacionSync.id.desc()).limit(limite)
    if estado:
        consulta = consulta.where(OperacionSync.estado == estado)
    if sucursal_id is not None:
        consulta = consulta.where(OperacionSync.sucursal_id == sucursal_id)
    return _para_supervision(db, db.scalars(consulta).all())


def para_supervision(db: Session, registro: OperacionSync) -> OperacionAdminOut:
    return _para_supervision(db, [registro])[0]


def _para_supervision(db: Session, registros: Sequence[OperacionSync]) -> list[OperacionAdminOut]:
    usuario_ids = {r.usuario_id for r in registros} | {r.resuelta_por for r in registros}
    usuario_ids.discard(None)
    sucursal_ids = {r.sucursal_id for r in registros if r.sucursal_id}
    correos = dict(db.execute(select(Usuario.id, Usuario.correo).where(Usuario.id.in_(usuario_ids))).all()) if usuario_ids else {}
    sucursales = dict(db.execute(select(Sucursal.id, Sucursal.nombre).where(Sucursal.id.in_(sucursal_ids))).all()) if sucursal_ids else {}
    return [
        OperacionAdminOut(
            **resultado_de(r).model_dump(),
            sucursal_id=r.sucursal_id,
            sucursal_nombre=sucursales.get(r.sucursal_id),
            usuario_correo=correos.get(r.usuario_id),
            dispositivo=r.dispositivo,
            registrada_en=r.registrada_en,
            recibida_en=r.recibida_en,
            intentos=r.intentos,
            datos=r.datos,
            resuelta_por_correo=correos.get(r.resuelta_por),
            resuelta_en=r.resuelta_en,
            nota_resolucion=r.nota_resolucion,
        )
        for r in registros
    ]


def bloquear_para_resolver(db: Session, operacion_id: UUID) -> Optional[OperacionSync]:
    """La operación bloqueada hasta el commit: dos encargados que resuelven el mismo conflicto a
    la vez no registran la venta dos veces (el segundo ya la ve resuelta)."""
    return db.scalars(
        select(OperacionSync).where(OperacionSync.uuid == operacion_id).with_for_update().execution_options(populate_existing=True)
    ).first()


def resolver_conflicto(
    db: Session, registro: OperacionSync, autor: Optional[Actor], resolutor_id: int, accion: str, nota: Optional[str]
) -> OperacionSync:
    """aceptar: se aplica como la registró su autor, aunque el stock no alcance (el faltante queda
    en el kardex). rechazar: no se aplica (la tienda devuelve el dinero o recupera la prenda)."""
    ahora = _ahora()
    if accion == "aceptar":
        if autor is None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="El usuario que registró la operación ya no existe: solo se puede rechazar")
        try:
            efecto = _aplicar(db, autor, OperacionIn.model_validate(registro.datos), ahora, forzar=True)
        except OperacionNoAplicable as motivo:
            db.rollback()
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Todavía no se puede aceptar: {motivo.mensaje}")
        _anotar_efecto(registro, efecto)
    else:
        registro.estado = RECHAZADA
    registro.resuelta_por = resolutor_id
    registro.resuelta_en = ahora
    registro.nota_resolucion = nota
    db.commit()
    logger.info("sync op=%s conflicto resuelto: %s por usuario=%s", registro.uuid, accion, resolutor_id)
    return registro


# ==============================================================================
# Paquete para trabajar sin conexión
# ==============================================================================
def sucursales_autorizadas(db: Session, actor: Actor) -> list[Sucursal]:
    consulta = select(Sucursal).where(Sucursal.estado.is_(True), Sucursal.fecha_eliminacion.is_(None)).order_by(Sucursal.nombre)
    if actor.es_personal and not actor.es_admin:
        if actor.sucursal_id is None:
            return []
        consulta = consulta.where(Sucursal.id == actor.sucursal_id)
    return list(db.scalars(consulta).all())


def armar_paquete(db: Session, actor: Actor, sucursal_id: Optional[int] = None) -> PaqueteOut:
    """Una consulta por tabla (sin N+1): el paquete se pide al iniciar el turno y cada vez que
    vuelve la conexión, así que tiene que ser barato aun con todo el catálogo."""
    tienda = _tienda(db)
    sucursales = sucursales_autorizadas(db, actor)
    if sucursal_id is not None:
        sucursales = [s for s in sucursales if s.id == sucursal_id]
        if not sucursales:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tenés acceso a esa sucursal")
    sucursal_ids = [s.id for s in sucursales]
    ciudades = dict(db.execute(select(Ciudad.id, Ciudad.nombre).where(Ciudad.id.in_({s.ciudad_id for s in sucursales}))).all()) if sucursales else {}

    prenda_activa = (Prenda.id == VariantePrenda.prenda_id) & Prenda.estado.is_(True)
    variantes = db.scalars(select(VariantePrenda).join(Prenda, prenda_activa).where(VariantePrenda.estado.is_(True)).order_by(VariantePrenda.id)).all()
    inventario = db.scalars(
        select(InventarioSucursal)
        .join(VariantePrenda, (VariantePrenda.id == InventarioSucursal.variante_id) & VariantePrenda.estado.is_(True))
        .join(Prenda, prenda_activa)
        .where(InventarioSucursal.sucursal_id.in_(sucursal_ids))
    ).all() if sucursal_ids else []

    clientes, ventas = [], []
    if actor.es_personal:
        clientes = [
            ClientePaqueteOut(id=uid, correo=correo)
            for uid, correo in db.execute(
                select(Usuario.id, Usuario.correo)
                .join(UsuarioRol, UsuarioRol.usuario_id == Usuario.id)
                .join(Rol, Rol.id == UsuarioRol.rol_id)
                .where(Rol.nombre == "Cliente", Usuario.estado.is_(True), Usuario.fecha_eliminacion.is_(None))
                .order_by(Usuario.correo)
            ).all()
        ]
        ventas = _ventas_cambiables(db, tienda.dias_para_cambio)

    return PaqueteOut(
        generado_en=_ahora(),
        vigencia_horas=VIGENCIA_PAQUETE_HORAS,
        tienda=tienda.slug,
        dias_para_cambio=tienda.dias_para_cambio,
        sucursales=[SucursalPaqueteOut(id=s.id, nombre=s.nombre, direccion=s.direccion, ciudad=ciudades.get(s.ciudad_id)) for s in sucursales],
        categorias=[ItemNombreOut(id=c.id, nombre=c.nombre) for c in db.scalars(select(Categoria).where(Categoria.estado.is_(True)).order_by(Categoria.nombre))],
        tallas=[ItemNombreOut(id=t.id, nombre=t.nombre) for t in db.scalars(select(Talla).order_by(Talla.id))],
        colores=[ColorPaqueteOut(id=c.id, nombre=c.nombre, hex=c.hex) for c in db.scalars(select(Color).order_by(Color.nombre))],
        prendas=[
            PrendaPaqueteOut(
                id=p.id, nombre=p.nombre, descripcion=p.descripcion, categoria_id=p.categoria_id,
                precio_base=float(p.precio_base), imagen_url=p.imagen_url,
            )
            for p in db.scalars(select(Prenda).where(Prenda.estado.is_(True)).order_by(Prenda.nombre))
        ],
        variantes=[
            VariantePaqueteOut(
                id=v.id, prenda_id=v.prenda_id, talla_id=v.talla_id, color_id=v.color_id,
                codigo_barras=v.codigo_barras, imagen_url=v.imagen_url,
            )
            for v in variantes
        ],
        inventario=[InventarioPaqueteOut(variante_id=i.variante_id, sucursal_id=i.sucursal_id, stock_disponible=i.stock_disponible) for i in inventario],
        clientes=clientes,
        ventas=ventas,
    )


def _ventas_cambiables(db: Session, dias_para_cambio: int) -> list[VentaPaqueteOut]:
    """Ventas pagadas dentro del plazo de cambio, de todas las sucursales: el cliente puede
    cambiar en cualquiera."""
    desde = _ahora() - timedelta(days=dias_para_cambio)
    ventas = db.scalars(
        select(Venta)
        .where(Venta.estado == EstadoVenta.pagada, Venta.fecha_venta >= desde)
        .order_by(Venta.fecha_venta.desc())
        .limit(MAX_VENTAS_EN_PAQUETE)
    ).all()
    if not ventas:
        return []
    ids = [v.id for v in ventas]
    vendidas = _vendidas(db, ids)
    devueltas = _devueltas(db, ids)
    return [
        VentaPaqueteOut(
            id=v.id,
            sucursal_id=v.sucursal_id,
            cliente_id=v.usuario_id,
            fecha_venta=v.fecha_venta,
            total=float(v.total),
            detalles=[
                DetalleVentaPaqueteOut(
                    variante_id=variante_id, cantidad=cantidad, precio_unitario=precio,
                    devuelto=devueltas.get((v.id, variante_id), 0),
                )
                for variante_id, (cantidad, precio) in sorted(vendidas.get(v.id, {}).items())
            ],
        )
        for v in ventas
    ]
