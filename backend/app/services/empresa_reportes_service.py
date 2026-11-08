"""Reportes personalizables de una empresa (característica 5): ventas, prendas vendidas, existencias,
reservas, desempeño del personal, movimientos de inventario y bitácora.

Se usan con la sesión de la empresa: el ORM (y la base, con Row Level Security) dejan solo sus
filas, así que ninguna consulta necesita filtrar por tienda. El motor (columnas, criterios, orden,
exportación y pedido con IA) es el mismo del superadmin: ver reportes_personalizados.py.
"""
from collections import defaultdict
from datetime import date
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.catalogo import Categoria, Color, Prenda, Talla, VariantePrenda
from app.models.enums import EstadoPago, EstadoReserva, EstadoVenta
from app.models.inventario import InventarioSucursal, MovimientoInventario
from app.models.reserva import DetalleReserva, Reserva
from app.models.seguridad import Usuario
from app.models.sucursal import Personal, Sucursal
from app.models.venta import DetalleVenta, Pago, Venta
from app.services import bitacora_service
from app.services import reportes_personalizados as motor
from app.services.reportes_personalizados import (
    Catalogo,
    Definicion,
    Fila,
    Reporte,
    contar_por,
    en_rango,
    fecha_hora_local,
    monto,
)

CANALES = {"web": "Web", "movil": "App móvil", "presencial": "Caja (presencial)"}
MOVIMIENTOS = {"entrada": "Entrada", "venta": "Venta", "reserva": "Reserva", "devolucion": "Devolución", "ajuste": "Ajuste"}
METODOS = {"efectivo": "Efectivo", "tarjeta": "Tarjeta", "qr": "QR", "transferencia": "Transferencia", "stripe": "Tarjeta (Stripe)"}
LIMITE_MOVIMIENTOS = 5000
ROLES_REPORTES = ["Administrador", "Encargado"]
SOLO_ADMINISTRADOR = {"bitacora"}  # el encargado no ve la auditoría
ESTADOS_STOCK = ["Normal", "Bajo el mínimo", "Sin stock"]


def _valor(enum_o_texto) -> str:
    return getattr(enum_o_texto, "value", enum_o_texto)


def _persona(nombres: Optional[str], apellidos: Optional[str]) -> Optional[str]:
    return f"{nombres} {apellidos}".strip() if nombres else None


# --------------------------------------------------------------------------- ventas

def _filas_ventas(db: Session, desde: Optional[date], hasta: Optional[date]) -> list[Fila]:
    ventas = db.execute(
        select(Venta, Sucursal.nombre, Usuario.correo, Personal.nombres, Personal.apellidos)
        .join(Sucursal, Sucursal.id == Venta.sucursal_id)
        .outerjoin(Usuario, Usuario.id == Venta.usuario_id)
        .outerjoin(Personal, Personal.id == Venta.personal_id)
        .where(*en_rango(Venta.fecha_venta, desde, hasta))
    ).all()
    ids = [v.id for v, *_ in ventas]
    metodos: dict[int, set[str]] = defaultdict(set)
    unidades: dict[int, int] = {}
    if ids:
        for venta_id, metodo in db.execute(
            select(Pago.venta_id, Pago.metodo_pago).where(Pago.venta_id.in_(ids), Pago.estado == EstadoPago.aprobado)
        ).all():
            metodos[venta_id].add(METODOS.get(metodo.lower(), metodo.capitalize()))
        unidades = dict(db.execute(
            select(DetalleVenta.venta_id, func.sum(DetalleVenta.cantidad)).where(DetalleVenta.venta_id.in_(ids)).group_by(DetalleVenta.venta_id)
        ).all())
    return [
        {
            "Fecha": fecha_hora_local(v.fecha_venta), "N° venta": v.id, "Sucursal": sucursal,
            "Cliente": correo or "Cliente en caja", "Vendedor": _persona(nombres, apellidos) or "-",
            "Canal": CANALES.get(_valor(v.tipo_origen), _valor(v.tipo_origen)), "Estado": _valor(v.estado).capitalize(),
            "Método de pago": ", ".join(sorted(metodos[v.id])) or "-", "Prendas": int(unidades.get(v.id) or 0),
            "Total (Bs.)": monto(v.total), "_orden_fecha": v.fecha_venta,
        }
        for v, sucursal, correo, nombres, apellidos in ventas
    ]


def _resumen_ventas(filas: list[Fila], periodo: str) -> str:
    pagadas = [f for f in filas if f["Estado"] == "Pagada"]
    total = sum(f["Total (Bs.)"] for f in pagadas)
    texto = f"{len(filas)} ventas {periodo}"
    if not filas:
        return texto + "."
    texto += f" ({contar_por(filas, 'Estado')}). Las pagadas suman Bs. {total:,.2f}"
    if pagadas:
        texto += f", con un ticket promedio de Bs. {total / len(pagadas):,.2f}. Por canal: {contar_por(pagadas, 'Canal')}"
    return texto + "."


# --------------------------------------------------------------------------- prendas vendidas

def _filas_prendas(db: Session, desde: Optional[date], hasta: Optional[date]) -> list[Fila]:
    vendidas = db.execute(
        select(
            Prenda.nombre, Categoria.nombre, Talla.nombre, Color.nombre,
            func.sum(DetalleVenta.cantidad), func.coalesce(func.sum(DetalleVenta.subtotal), 0),
        )
        .select_from(DetalleVenta)
        .join(Venta, Venta.id == DetalleVenta.venta_id)
        .join(VariantePrenda, VariantePrenda.id == DetalleVenta.variante_id)
        .join(Prenda, Prenda.id == VariantePrenda.prenda_id)
        .join(Categoria, Categoria.id == Prenda.categoria_id)
        .join(Talla, Talla.id == VariantePrenda.talla_id)
        .join(Color, Color.id == VariantePrenda.color_id)
        .where(Venta.estado == EstadoVenta.pagada, *en_rango(Venta.fecha_venta, desde, hasta))
        .group_by(VariantePrenda.id, Prenda.nombre, Categoria.nombre, Talla.nombre, Color.nombre)
    ).all()
    return [
        {
            "Prenda": prenda, "Categoría": categoria, "Talla": talla, "Color": color, "Unidades": int(cantidad),
            "Total vendido (Bs.)": monto(total), "Precio promedio (Bs.)": round(monto(total) / cantidad, 2) if cantidad else 0.0,
        }
        for prenda, categoria, talla, color, cantidad, total in vendidas
    ]


def _resumen_prendas(filas: list[Fila], periodo: str) -> str:
    if not filas:
        return f"No hubo prendas vendidas {periodo}."
    unidades, total = sum(f["Unidades"] for f in filas), sum(f["Total vendido (Bs.)"] for f in filas)
    lider = max(filas, key=lambda f: f["Unidades"])
    return (
        f"Se vendieron {unidades} prendas por Bs. {total:,.2f} {periodo}. La más vendida fue "
        f"{lider['Prenda']} (talla {lider['Talla']}, {lider['Color']}) con {lider['Unidades']} unidades."
    )


# --------------------------------------------------------------------------- existencias

def _estado_stock(disponible: int, minimo: int) -> str:
    normal, bajo, sin_stock = ESTADOS_STOCK
    if disponible <= 0:
        return sin_stock
    return bajo if disponible < minimo else normal


def _filas_inventario(db: Session, desde: Optional[date] = None, hasta: Optional[date] = None) -> list[Fila]:
    existencias = db.execute(
        select(InventarioSucursal, Prenda.nombre, Categoria.nombre, Talla.nombre, Color.nombre, VariantePrenda.codigo_barras, Sucursal.nombre)
        .join(VariantePrenda, VariantePrenda.id == InventarioSucursal.variante_id)
        .join(Prenda, Prenda.id == VariantePrenda.prenda_id)
        .join(Categoria, Categoria.id == Prenda.categoria_id)
        .join(Talla, Talla.id == VariantePrenda.talla_id)
        .join(Color, Color.id == VariantePrenda.color_id)
        .join(Sucursal, Sucursal.id == InventarioSucursal.sucursal_id)
        .where(VariantePrenda.estado.is_(True), Prenda.estado.is_(True), Sucursal.estado.is_(True))
    ).all()
    return [
        {
            "Prenda": prenda, "Categoría": categoria, "Talla": talla, "Color": color, "Código": codigo, "Sucursal": sucursal,
            "Disponible": inv.stock_disponible, "Reservado": inv.stock_reservado, "Mínimo": inv.stock_minimo,
            "Estado": _estado_stock(inv.stock_disponible, inv.stock_minimo),
        }
        for inv, prenda, categoria, talla, color, codigo, sucursal in existencias
    ]


def _resumen_inventario(filas: list[Fila], periodo: str) -> str:
    sin_stock = sum(f["Estado"] == "Sin stock" for f in filas)
    bajo = sum(f["Estado"] == "Bajo el mínimo" for f in filas)
    texto = f"{len(filas)} existencias (prenda, talla y color por sucursal) con {sum(f['Disponible'] for f in filas)} unidades disponibles hoy."
    if sin_stock or bajo:
        texto += f" Hay que reponer: {sin_stock} sin stock y {bajo} por debajo del mínimo."
    return texto


# --------------------------------------------------------------------------- reservas

def _filas_reservas(db: Session, desde: Optional[date], hasta: Optional[date]) -> list[Fila]:
    reservas = db.execute(
        select(Reserva, Sucursal.nombre, Usuario.correo, Personal.nombres, Personal.apellidos)
        .join(Sucursal, Sucursal.id == Reserva.sucursal_id)
        .outerjoin(Usuario, Usuario.id == Reserva.usuario_id)
        .outerjoin(Personal, Personal.id == Reserva.personal_id)
        .where(*en_rango(Reserva.fecha_reserva, desde, hasta))
    ).all()
    ids = [r.id for r, *_ in reservas]
    unidades = dict(db.execute(
        select(DetalleReserva.reserva_id, func.sum(DetalleReserva.cantidad)).where(DetalleReserva.reserva_id.in_(ids)).group_by(DetalleReserva.reserva_id)
    ).all()) if ids else {}
    return [
        {
            "Fecha": fecha_hora_local(r.fecha_reserva), "N° reserva": r.id, "Cliente": correo or "-", "Sucursal": sucursal,
            "Horario": r.horario_atencion.strftime("%H:%M") if r.horario_atencion else "-", "Estado": _valor(r.estado).capitalize(),
            "Prendas": int(unidades.get(r.id) or 0), "Atendió": _persona(nombres, apellidos) or "-", "_orden_fecha": r.fecha_reserva,
        }
        for r, sucursal, correo, nombres, apellidos in reservas
    ]


def _resumen_reservas(filas: list[Fila], periodo: str) -> str:
    if not filas:
        return f"No hubo reservas {periodo}."
    atendidas = sum(f["Estado"] == "Atendida" for f in filas)
    return (
        f"{len(filas)} reservas {periodo} ({contar_por(filas, 'Estado')}). "
        f"Se atendió el {atendidas / len(filas) * 100:.0f} % de las reservas."
    )


# --------------------------------------------------------------------------- personal

def _filas_personal(db: Session, desde: Optional[date], hasta: Optional[date]) -> list[Fila]:
    ventas = {
        personal_id: (cantidad, monto(total))
        for personal_id, cantidad, total in db.execute(
            select(Venta.personal_id, func.count(), func.coalesce(func.sum(Venta.total), 0))
            .where(Venta.personal_id.is_not(None), Venta.estado == EstadoVenta.pagada, *en_rango(Venta.fecha_venta, desde, hasta))
            .group_by(Venta.personal_id)
        ).all()
    }
    empleados = db.execute(
        select(Personal, Usuario.correo, Sucursal.nombre)
        .join(Usuario, Usuario.id == Personal.usuario_id)
        .outerjoin(Sucursal, Sucursal.id == Personal.sucursal_id)
    ).all()
    filas = []
    for p, correo, sucursal in empleados:
        cantidad, total = ventas.get(p.id, (0, 0.0))
        filas.append({
            "Empleado": _persona(p.nombres, p.apellidos), "Cargo": p.cargo, "Sucursal": sucursal or "-", "Correo": correo,
            "Estado": "Activo" if p.estado and not p.fecha_eliminacion else "Inactivo", "Ventas": cantidad,
            "Total vendido (Bs.)": total, "Ticket promedio (Bs.)": round(total / cantidad, 2) if cantidad else 0.0,
        })
    return filas


def _resumen_personal(filas: list[Fila], periodo: str) -> str:
    activos = sum(f["Estado"] == "Activo" for f in filas)
    texto = f"{len(filas)} empleados ({activos} activos). Ventas en caja {periodo}: {sum(f['Ventas'] for f in filas)}"
    lider = max(filas, key=lambda f: f["Total vendido (Bs.)"], default=None)
    if lider and lider["Total vendido (Bs.)"]:
        texto += f"; lidera {lider['Empleado']} con Bs. {lider['Total vendido (Bs.)']:,.2f}"
    return texto + "."


# --------------------------------------------------------------------------- movimientos de inventario

def _filas_movimientos(db: Session, desde: Optional[date], hasta: Optional[date]) -> list[Fila]:
    movimientos = db.execute(
        select(MovimientoInventario, Prenda.nombre, Talla.nombre, Color.nombre, Sucursal.nombre, Usuario.correo)
        .join(VariantePrenda, VariantePrenda.id == MovimientoInventario.variante_id)
        .join(Prenda, Prenda.id == VariantePrenda.prenda_id)
        .join(Talla, Talla.id == VariantePrenda.talla_id)
        .join(Color, Color.id == VariantePrenda.color_id)
        .join(Sucursal, Sucursal.id == MovimientoInventario.sucursal_id)
        .outerjoin(Usuario, Usuario.id == MovimientoInventario.usuario_id)
        .where(*en_rango(MovimientoInventario.fecha, desde, hasta))
        .order_by(MovimientoInventario.fecha.desc())
        .limit(LIMITE_MOVIMIENTOS)
    ).all()
    return [
        {
            "Fecha": fecha_hora_local(m.fecha), "Prenda": prenda, "Talla": talla, "Color": color, "Sucursal": sucursal,
            "Tipo": MOVIMIENTOS.get(_valor(m.tipo_movimiento), _valor(m.tipo_movimiento)), "Cantidad": m.cantidad,
            "Usuario": correo or "-",
            "Referencia": f"{m.referencia_tipo} #{m.referencia_id}" if m.referencia_tipo and m.referencia_id else (m.referencia_tipo or "-"),
            "_orden_fecha": m.fecha,
        }
        for m, prenda, talla, color, sucursal, correo in movimientos
    ]


def _resumen_movimientos(filas: list[Fila], periodo: str) -> str:
    if not filas:
        return f"No hubo movimientos de inventario {periodo}."
    return f"{len(filas)} movimientos de inventario {periodo}: {contar_por(filas, 'Tipo')}."


# --------------------------------------------------------------------------- catálogo

REPORTES: Catalogo = {
    "ventas": Definicion(
        titulo="Ventas",
        descripcion="Cada venta con su sucursal, cliente, vendedor, canal, estado, método de pago y total. Las fechas filtran por fecha de venta.",
        columnas=["Fecha", "N° venta", "Sucursal", "Cliente", "Vendedor", "Canal", "Estado", "Método de pago", "Prendas", "Total (Bs.)"],
        obtener=_filas_ventas, resumir=_resumen_ventas, orden=("Fecha", True),
        sumables=["Prendas", "Total (Bs.)"], columnas_monto=["Total (Bs.)"],
        valores={
            "Canal": list(CANALES.values()),
            "Estado": [e.value.capitalize() for e in EstadoVenta],
            "Método de pago": sorted(set(METODOS.values())),
        },
    ),
    "prendas": Definicion(
        titulo="Prendas vendidas",
        descripcion="Unidades vendidas y facturación de cada prenda por talla y color (ventas pagadas). Las fechas filtran por fecha de venta.",
        columnas=["Prenda", "Categoría", "Talla", "Color", "Unidades", "Total vendido (Bs.)", "Precio promedio (Bs.)"],
        obtener=_filas_prendas, resumir=_resumen_prendas, orden=("Unidades", True),
        sumables=["Unidades", "Total vendido (Bs.)"], columnas_monto=["Total vendido (Bs.)", "Precio promedio (Bs.)"],
    ),
    "inventario": Definicion(
        titulo="Existencias por sucursal",
        descripcion="Stock de hoy de cada prenda, talla y color en cada sucursal, con su mínimo y si hay que reponer. Las fechas no se aplican.",
        columnas=["Prenda", "Categoría", "Talla", "Color", "Código", "Sucursal", "Disponible", "Reservado", "Mínimo", "Estado"],
        obtener=_filas_inventario, resumir=_resumen_inventario, orden=("Disponible", False),
        sumables=["Disponible", "Reservado"], valores={"Estado": ESTADOS_STOCK},
    ),
    "reservas": Definicion(
        titulo="Reservas",
        descripcion="Cada reserva con su cliente, sucursal, horario, estado, prendas y quién la atendió. Las fechas filtran por fecha de reserva.",
        columnas=["Fecha", "N° reserva", "Cliente", "Sucursal", "Horario", "Estado", "Prendas", "Atendió"],
        obtener=_filas_reservas, resumir=_resumen_reservas, orden=("Fecha", True), sumables=["Prendas"],
        valores={"Estado": [e.value.capitalize() for e in EstadoReserva]},
    ),
    "personal": Definicion(
        titulo="Desempeño del personal",
        descripcion="Cada empleado con su cargo y sucursal, y las ventas que cobró en caja. Las fechas filtran las ventas.",
        columnas=["Empleado", "Cargo", "Sucursal", "Correo", "Estado", "Ventas", "Total vendido (Bs.)", "Ticket promedio (Bs.)"],
        obtener=_filas_personal, resumir=_resumen_personal, orden=("Total vendido (Bs.)", True),
        sumables=["Ventas", "Total vendido (Bs.)"], columnas_monto=["Total vendido (Bs.)", "Ticket promedio (Bs.)"],
        valores={"Estado": ["Activo", "Inactivo"]},
    ),
    "movimientos": Definicion(
        titulo="Movimientos de inventario",
        descripcion="Entradas, ventas, reservas, devoluciones y ajustes de stock, con quién los hizo. Las fechas filtran por fecha del movimiento.",
        columnas=["Fecha", "Prenda", "Talla", "Color", "Sucursal", "Tipo", "Cantidad", "Usuario", "Referencia"],
        obtener=_filas_movimientos, resumir=_resumen_movimientos, orden=("Fecha", True),
        valores={"Tipo": list(MOVIMIENTOS.values())},
    ),
    "bitacora": Definicion(
        titulo="Bitácora de la empresa",
        descripcion="Cada acción de cada usuario de la empresa: fecha y hora (Bolivia), usuario, rol, IP y acción. Las fechas filtran por fecha de la acción.",
        columnas=["Fecha", "Usuario", "Rol", "IP", "Acción"],
        obtener=bitacora_service.filas, resumir=bitacora_service.resumir, orden=("Fecha", True),
    ),
}

QUIEN = "del administrador de una tienda de ropa (una sola empresa, con varias sucursales)"
EJEMPLOS = (
    "«ventas de este mes por sucursal», «prendas más vendidas en octubre», «prendas sin stock» "
    "o «reservas canceladas de la semana»"
)


def reportes_para(roles: list[str]) -> Catalogo:
    """Los reportes que puede ver alguien con estos roles (la bitácora, solo el administrador)."""
    if "Administrador" in roles:
        return REPORTES
    return {tipo: d for tipo, d in REPORTES.items() if tipo not in SOLO_ADMINISTRADOR}


def catalogo(roles: list[str]) -> list[dict]:
    return motor.catalogo(reportes_para(roles))


def generar(db: Session, roles: list[str], tipo: str, **opciones) -> Reporte:
    return motor.generar(reportes_para(roles), db, tipo, **opciones)


def interpretar(roles: list[str], pedido: str) -> dict:
    return motor.interpretar(reportes_para(roles), pedido, QUIEN, EJEMPLOS)


def opciones_desde_ia(roles: list[str], datos: Any) -> dict:
    return motor.opciones_desde_ia(reportes_para(roles), datos)
