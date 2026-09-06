from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.models.catalogo import Categoria, Color, Prenda, Talla, VariantePrenda
from app.models.seguridad import Usuario
from app.schemas.catalogo import (
    CategoriaCreate,
    CategoriaOut,
    CategoriaUpdate,
    ColorCreate,
    ColorOut,
    ColorUpdate,
    TallaCreate,
    TallaOut,
    TallaUpdate,
)

router = APIRouter()


# --- Categorías ---
@router.get("/categorias", response_model=List[CategoriaOut])
def listar_categorias(db: Session = Depends(get_db)):
    """CU-09: Listar categorías registradas"""
    stmt = select(Categoria).order_by(Categoria.nombre)
    return list(db.scalars(stmt).all())


@router.post("/categorias", response_model=CategoriaOut, status_code=status.HTTP_201_CREATED)
def crear_categoria(
    datos: CategoriaCreate,
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_roles(["Administrador"])),
):
    """CU-09: Registrar una nueva categoría"""
    existente = db.scalars(select(Categoria).where(Categoria.nombre == datos.nombre)).first()
    if existente:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"La categoría '{datos.nombre}' ya existe")
    nueva = Categoria(nombre=datos.nombre, descripcion=datos.descripcion, estado=True)
    db.add(nueva)
    db.commit()
    db.refresh(nueva)
    return nueva


@router.put("/categorias/{categoria_id}", response_model=CategoriaOut)
def actualizar_categoria(
    categoria_id: int,
    datos: CategoriaUpdate,
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_roles(["Administrador"])),
):
    """CU-09: Editar una categoría existente"""
    categoria = db.get(Categoria, categoria_id)
    if not categoria:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Categoría no encontrada")

    if datos.estado is False:
        en_uso = db.scalars(
            select(Prenda).where(Prenda.categoria_id == categoria_id, Prenda.estado.is_(True))
        ).first()
        if en_uso:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se puede desactivar: existen prendas activas asociadas a esta categoría",
            )

    if datos.nombre is not None:
        categoria.nombre = datos.nombre
    if datos.descripcion is not None:
        categoria.descripcion = datos.descripcion
    if datos.estado is not None:
        categoria.estado = datos.estado

    db.commit()
    db.refresh(categoria)
    return categoria


# --- Tallas ---
@router.get("/tallas", response_model=List[TallaOut])
def listar_tallas(db: Session = Depends(get_db)):
    """CU-09: Listar tallas registradas"""
    stmt = select(Talla).order_by(Talla.id)
    return list(db.scalars(stmt).all())


@router.post("/tallas", response_model=TallaOut, status_code=status.HTTP_201_CREATED)
def crear_talla(
    datos: TallaCreate,
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_roles(["Administrador"])),
):
    """CU-09: Registrar una nueva talla"""
    existente = db.scalars(select(Talla).where(Talla.nombre == datos.nombre)).first()
    if existente:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"La talla '{datos.nombre}' ya existe")
    nueva = Talla(nombre=datos.nombre)
    db.add(nueva)
    db.commit()
    db.refresh(nueva)
    return nueva


@router.put("/tallas/{talla_id}", response_model=TallaOut)
def actualizar_talla(
    talla_id: int,
    datos: TallaUpdate,
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_roles(["Administrador"])),
):
    """CU-09: Editar una talla existente"""
    talla = db.get(Talla, talla_id)
    if not talla:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Talla no encontrada")
    if datos.nombre is not None:
        talla.nombre = datos.nombre
    db.commit()
    db.refresh(talla)
    return talla


@router.delete("/tallas/{talla_id}")
def eliminar_talla(
    talla_id: int,
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_roles(["Administrador"])),
):
    """CU-09: Eliminar una talla, validando que no esté en uso por variantes activas"""
    talla = db.get(Talla, talla_id)
    if not talla:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Talla no encontrada")

    en_uso = db.scalars(
        select(VariantePrenda).where(VariantePrenda.talla_id == talla_id, VariantePrenda.estado.is_(True))
    ).first()
    if en_uso:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se puede eliminar: existen variantes de prenda activas con esta talla",
        )

    db.delete(talla)
    db.commit()
    return {"message": f"Talla '{talla.nombre}' eliminada correctamente"}


# --- Colores ---
@router.get("/colores", response_model=List[ColorOut])
def listar_colores(db: Session = Depends(get_db)):
    """CU-09: Listar colores registrados"""
    stmt = select(Color).order_by(Color.nombre)
    return list(db.scalars(stmt).all())


@router.post("/colores", response_model=ColorOut, status_code=status.HTTP_201_CREATED)
def crear_color(
    datos: ColorCreate,
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_roles(["Administrador"])),
):
    """CU-09: Registrar un nuevo color"""
    existente = db.scalars(select(Color).where(Color.nombre == datos.nombre)).first()
    if existente:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"El color '{datos.nombre}' ya existe")
    nuevo = Color(nombre=datos.nombre, hex=datos.hex)
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)
    return nuevo


@router.put("/colores/{color_id}", response_model=ColorOut)
def actualizar_color(
    color_id: int,
    datos: ColorUpdate,
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_roles(["Administrador"])),
):
    """CU-09: Editar un color existente"""
    color = db.get(Color, color_id)
    if not color:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Color no encontrado")
    if datos.nombre is not None:
        color.nombre = datos.nombre
    if datos.hex is not None:
        color.hex = datos.hex
    db.commit()
    db.refresh(color)
    return color


@router.delete("/colores/{color_id}")
def eliminar_color(
    color_id: int,
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_roles(["Administrador"])),
):
    """CU-09: Eliminar un color, validando que no esté en uso por variantes activas"""
    color = db.get(Color, color_id)
    if not color:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Color no encontrado")

    en_uso = db.scalars(
        select(VariantePrenda).where(VariantePrenda.color_id == color_id, VariantePrenda.estado.is_(True))
    ).first()
    if en_uso:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se puede eliminar: existen variantes de prenda activas con este color",
        )

    db.delete(color)
    db.commit()
    return {"message": f"Color '{color.nombre}' eliminado correctamente"}
