import secrets
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.models.catalogo import Color, Prenda, Talla, VariantePrenda
from app.models.inventario import InventarioSucursal
from app.models.seguridad import Usuario
from app.schemas.catalogo import (
    VariantePrendaCreate,
    VariantePrendaOut,
    VariantePrendaUpdate,
)

router = APIRouter()


def _to_out(db: Session, variante: VariantePrenda) -> VariantePrendaOut:
    talla = db.get(Talla, variante.talla_id)
    color = db.get(Color, variante.color_id)
    return VariantePrendaOut(
        id=variante.id,
        prenda_id=variante.prenda_id,
        talla_id=variante.talla_id,
        color_id=variante.color_id,
        codigo_barras=variante.codigo_barras,
        estado=variante.estado,
        talla_nombre=talla.nombre if talla else None,
        color_nombre=color.nombre if color else None,
    )


def _generar_codigo_barras(prenda_id: int, talla_id: int, color_id: int) -> str:
    return f"{prenda_id:05d}{talla_id:03d}{color_id:03d}{secrets.token_hex(3).upper()}"


@router.get("/{prenda_id}/variantes", response_model=List[VariantePrendaOut])
def listar_variantes(prenda_id: int, db: Session = Depends(get_db)):
    """CU-11: Listar variantes (talla/color) de una prenda"""
    prenda = db.get(Prenda, prenda_id)
    if not prenda:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prenda no encontrada")

    stmt = select(VariantePrenda).where(VariantePrenda.prenda_id == prenda_id).order_by(VariantePrenda.id)
    return [_to_out(db, v) for v in db.scalars(stmt).all()]


@router.post("/{prenda_id}/variantes", response_model=VariantePrendaOut, status_code=status.HTTP_201_CREATED)
def crear_variante(
    prenda_id: int,
    datos: VariantePrendaCreate,
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_roles(["Administrador"])),
):
    """CU-11: Registrar una nueva variante talla/color para una prenda"""
    prenda = db.get(Prenda, prenda_id)
    if not prenda:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prenda no encontrada")

    talla = db.get(Talla, datos.talla_id)
    if not talla:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La talla especificada no existe")

    color = db.get(Color, datos.color_id)
    if not color:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El color especificado no existe")

    # 4. Validar que la combinación talla/color no esté ya registrada para esa prenda
    duplicado = db.scalars(
        select(VariantePrenda).where(
            VariantePrenda.prenda_id == prenda_id,
            VariantePrenda.talla_id == datos.talla_id,
            VariantePrenda.color_id == datos.color_id,
        )
    ).first()
    if duplicado:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe una variante con esa combinación de talla y color para esta prenda",
        )

    codigo_barras = datos.codigo_barras or _generar_codigo_barras(prenda_id, datos.talla_id, datos.color_id)
    if db.scalars(select(VariantePrenda).where(VariantePrenda.codigo_barras == codigo_barras)).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"El código de barras '{codigo_barras}' ya está en uso",
        )

    nueva = VariantePrenda(
        prenda_id=prenda_id,
        talla_id=datos.talla_id,
        color_id=datos.color_id,
        codigo_barras=codigo_barras,
        estado=True,
    )
    db.add(nueva)
    db.commit()
    db.refresh(nueva)
    return _to_out(db, nueva)


@router.put("/{prenda_id}/variantes/{variante_id}", response_model=VariantePrendaOut)
def actualizar_variante(
    prenda_id: int,
    variante_id: int,
    datos: VariantePrendaUpdate,
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_roles(["Administrador"])),
):
    """CU-11: Editar una variante de prenda existente"""
    variante = db.get(VariantePrenda, variante_id)
    if not variante or variante.prenda_id != prenda_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Variante no encontrada")

    nueva_talla = datos.talla_id if datos.talla_id is not None else variante.talla_id
    nuevo_color = datos.color_id if datos.color_id is not None else variante.color_id

    if datos.talla_id is not None and not db.get(Talla, datos.talla_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La talla especificada no existe")
    if datos.color_id is not None and not db.get(Color, datos.color_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El color especificado no existe")

    if nueva_talla != variante.talla_id or nuevo_color != variante.color_id:
        duplicado = db.scalars(
            select(VariantePrenda).where(
                VariantePrenda.prenda_id == prenda_id,
                VariantePrenda.talla_id == nueva_talla,
                VariantePrenda.color_id == nuevo_color,
                VariantePrenda.id != variante_id,
            )
        ).first()
        if duplicado:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ya existe una variante con esa combinación de talla y color para esta prenda",
            )

    if datos.codigo_barras is not None:
        en_uso = db.scalars(
            select(VariantePrenda).where(
                VariantePrenda.codigo_barras == datos.codigo_barras,
                VariantePrenda.id != variante_id,
            )
        ).first()
        if en_uso:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El código de barras ya está en uso")
        variante.codigo_barras = datos.codigo_barras

    variante.talla_id = nueva_talla
    variante.color_id = nuevo_color
    if datos.estado is not None:
        variante.estado = datos.estado

    db.commit()
    db.refresh(variante)
    return _to_out(db, variante)


@router.delete("/{prenda_id}/variantes/{variante_id}")
def eliminar_variante(
    prenda_id: int,
    variante_id: int,
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_roles(["Administrador"])),
):
    """CU-11: Desactivar una variante, validando que no tenga inventario con stock activo"""
    variante = db.get(VariantePrenda, variante_id)
    if not variante or variante.prenda_id != prenda_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Variante no encontrada")

    inventario_activo = db.scalars(
        select(InventarioSucursal).where(
            InventarioSucursal.variante_id == variante_id,
            InventarioSucursal.stock_disponible > 0,
        )
    ).first()
    if inventario_activo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se puede desactivar: la variante tiene stock disponible en alguna sucursal",
        )

    variante.estado = False
    db.commit()
    return {"message": f"Variante '{variante.codigo_barras}' desactivada correctamente"}
