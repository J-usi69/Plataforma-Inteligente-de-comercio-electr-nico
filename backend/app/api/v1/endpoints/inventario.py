from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.catalogo import VariantePrenda
from app.models.inventario import InventarioSucursal
from app.models.sucursal import Ciudad, Sucursal
from app.schemas.inventario import DisponibilidadSucursalOut

router = APIRouter()


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
