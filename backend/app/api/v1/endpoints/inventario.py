from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_client_ip, get_db, registrar_bitacora, require_roles
from app.models.catalogo import Color, Prenda, Talla, VariantePrenda
from app.models.enums import TipoMovimiento
from app.models.inventario import InventarioSucursal, MovimientoInventario
from app.models.seguridad import Usuario
from app.models.sucursal import Ciudad, Sucursal
from app.schemas.inventario import (
    DisponibilidadSucursalOut,
    InventarioVarianteOut,
    MovimientoManualCreate,
    MovimientoManualOut,
)

router = APIRouter()

_ROLES_ENCARGADO_INVENTARIO = ["Encargado", "Administrador"]
_TIPOS_VALIDOS = {"ingreso", "devolucion", "merma", "ajuste"}
_TIPOS_INCREMENTO = {"ingreso", "devolucion"}
_TIPO_A_ENUM = {
    "ingreso": TipoMovimiento.entrada,
    "devolucion": TipoMovimiento.devolucion,
    "merma": TipoMovimiento.ajuste,
    "ajuste": TipoMovimiento.ajuste,
}


def _sucursal_del_encargado(current_user: Usuario) -> int:
    if not current_user.personal or not current_user.personal.sucursal_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tu usuario no está vinculado a una sucursal como personal",
        )
    return current_user.personal.sucursal_id


@router.get("/disponibilidad/{variante_id}", response_model=List[DisponibilidadSucursalOut])
def consultar_disponibilidad(variante_id: int, db: Session = Depends(get_db)):
    """CU-13: Consultar en qué sucursales hay stock disponible de una variante de prenda"""
    variante = db.get(VariantePrenda, variante_id)
    if not variante or not variante.estado:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Variante de prenda no encontrada")

    stmt = (
        select(InventarioSucursal, Sucursal, Ciudad)
        .join(Sucursal, Sucursal.id == InventarioSucursal.sucursal_id)
        .join(Ciudad, Ciudad.id == Sucursal.ciudad_id)
        .where(
            InventarioSucursal.variante_id == variante_id,
            InventarioSucursal.stock_disponible > 0,
            Sucursal.estado.is_(True),
            Sucursal.fecha_eliminacion.is_(None),
        )
        .order_by(Ciudad.nombre, Sucursal.nombre)
    )

    resultado = []
    for inventario, sucursal, ciudad in db.execute(stmt).all():
        resultado.append(
            DisponibilidadSucursalOut(
                sucursal_id=sucursal.id,
                sucursal_nombre=sucursal.nombre,
                ciudad_id=ciudad.id,
                ciudad_nombre=ciudad.nombre,
                direccion=sucursal.direccion,
                stock_disponible=inventario.stock_disponible,
            )
        )
    return resultado


@router.get("/encargado/variantes", response_model=List[InventarioVarianteOut])
def listar_variantes_sucursal_encargado(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_roles(_ROLES_ENCARGADO_INVENTARIO)),
):
    """CU-26: variantes con inventario asignado a la sucursal del propio encargado"""
    sucursal_id = _sucursal_del_encargado(current_user)
    stmt = (
        select(InventarioSucursal, VariantePrenda, Prenda, Talla, Color)
        .join(VariantePrenda, VariantePrenda.id == InventarioSucursal.variante_id)
        .join(Prenda, Prenda.id == VariantePrenda.prenda_id)
        .outerjoin(Talla, Talla.id == VariantePrenda.talla_id)
        .outerjoin(Color, Color.id == VariantePrenda.color_id)
        .where(InventarioSucursal.sucursal_id == sucursal_id)
        .order_by(Prenda.nombre)
    )
    resultado = []
    for inv, variante, prenda, talla, color in db.execute(stmt).all():
        resultado.append(
            InventarioVarianteOut(
                variante_id=variante.id,
                prenda_nombre=prenda.nombre,
                talla_nombre=talla.nombre if talla else None,
                color_nombre=color.nombre if color else None,
                codigo_barras=variante.codigo_barras,
                stock_disponible=inv.stock_disponible,
                stock_reservado=inv.stock_reservado,
            )
        )
    return resultado


@router.post("/encargado/movimientos", response_model=MovimientoManualOut)
def registrar_movimiento_manual(
    datos: MovimientoManualCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_roles(_ROLES_ENCARGADO_INVENTARIO)),
):
    """CU-26: registrar ingreso, devolución, merma o ajuste manual sobre el inventario
    de la propia sucursal del encargado."""
    sucursal_id = _sucursal_del_encargado(current_user)
    tipo = datos.tipo.strip().lower()
    if tipo not in _TIPOS_VALIDOS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tipo de movimiento inválido. Debe ser uno de: {', '.join(sorted(_TIPOS_VALIDOS))}",
        )
    if datos.cantidad == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La cantidad debe ser distinta de cero")

    inventario = db.scalars(
        select(InventarioSucursal).where(
            InventarioSucursal.variante_id == datos.variante_id,
            InventarioSucursal.sucursal_id == sucursal_id,
        )
    ).first()
    if not inventario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Esa variante no tiene inventario registrado en tu sucursal",
        )

    if tipo in _TIPOS_INCREMENTO:
        delta = abs(datos.cantidad)
    elif tipo == "merma":
        delta = -abs(datos.cantidad)
    else:  # ajuste: el signo lo define quien lo registra (correccion por conteo fisico)
        delta = datos.cantidad

    nuevo_stock = inventario.stock_disponible + delta
    if nuevo_stock < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Stock insuficiente para esa salida. Disponible actual: {inventario.stock_disponible}",
        )

    inventario.stock_disponible = nuevo_stock

    movimiento = MovimientoInventario(
        variante_id=datos.variante_id,
        sucursal_id=sucursal_id,
        tipo_movimiento=_TIPO_A_ENUM[tipo],
        cantidad=delta,
        referencia_tipo=f"{tipo}_manual",
        usuario_id=current_user.id,
        fecha=datetime.now(timezone.utc),
    )
    db.add(movimiento)
    db.commit()
    db.refresh(movimiento)
    db.refresh(inventario)

    registrar_bitacora(
        db, current_user.id,
        f"Inventario: {tipo} de {delta:+d} en variante #{datos.variante_id}, sucursal #{sucursal_id}",
        get_client_ip(request),
    )

    return MovimientoManualOut(
        id=movimiento.id,
        variante_id=movimiento.variante_id,
        tipo=tipo,
        cantidad=movimiento.cantidad,
        stock_disponible=inventario.stock_disponible,
        fecha=movimiento.fecha,
    )
