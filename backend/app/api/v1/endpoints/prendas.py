from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.models.catalogo import Categoria, Coleccion, Prenda, Proveedor, VariantePrenda
from app.models.seguridad import Usuario
from app.schemas.catalogo import (
    CategoriaOut,
    ColeccionOut,
    PrendaCreate,
    PrendaOut,
    PrendaUpdate,
)

router = APIRouter()


# --- Catálogos auxiliares (Categorías y Colecciones) ---
@router.get("/categorias", response_model=List[CategoriaOut])
def listar_categorias(db: Session = Depends(get_db)):
    """Listar categorías de prendas disponibles"""
    stmt = select(Categoria).where(Categoria.estado.is_(True)).order_by(Categoria.nombre)
    return list(db.scalars(stmt).all())


@router.get("/colecciones", response_model=List[ColeccionOut])
def listar_colecciones(db: Session = Depends(get_db)):
    """Listar colecciones disponibles"""
    stmt = select(Coleccion).where(Coleccion.estado.is_(True)).order_by(Coleccion.nombre)
    return list(db.scalars(stmt).all())


# --- Prendas del Catálogo ---
@router.get("", response_model=List[PrendaOut])
def listar_prendas(
    categoria_id: Optional[int] = None,
    coleccion_id: Optional[int] = None,
    temporada_id: Optional[int] = None,
    talla_id: Optional[int] = None,
    color_id: Optional[int] = None,
    buscar: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """CU-08 / CU-12: Consultar y filtrar el catálogo de prendas (público / cliente / admin)"""
    stmt = select(Prenda).where(Prenda.estado.is_(True))
    if categoria_id:
        stmt = stmt.where(Prenda.categoria_id == categoria_id)
    if coleccion_id:
        stmt = stmt.where(Prenda.coleccion_id == coleccion_id)
    if temporada_id:
        stmt = stmt.join(Coleccion, Coleccion.id == Prenda.coleccion_id).where(Coleccion.temporada_id == temporada_id)
    if buscar:
        stmt = stmt.where(Prenda.nombre.ilike(f"%{buscar}%"))
    if talla_id or color_id:
        variante_filtro = select(VariantePrenda.prenda_id).where(VariantePrenda.estado.is_(True))
        if talla_id:
            variante_filtro = variante_filtro.where(VariantePrenda.talla_id == talla_id)
        if color_id:
            variante_filtro = variante_filtro.where(VariantePrenda.color_id == color_id)
        stmt = stmt.where(Prenda.id.in_(variante_filtro))

    prendas = db.scalars(stmt.order_by(Prenda.id.desc())).all()
    resultado = []
    for p in prendas:
        cat = db.get(Categoria, p.categoria_id) if p.categoria_id else None
        col = db.get(Coleccion, p.coleccion_id) if p.coleccion_id else None
        prov = db.get(Proveedor, p.proveedor_id) if p.proveedor_id else None
        resultado.append(
            PrendaOut(
                id=p.id,
                nombre=p.nombre,
                descripcion=p.descripcion,
                categoria_id=p.categoria_id,
                coleccion_id=p.coleccion_id,
                proveedor_id=p.proveedor_id,
                precio_base=float(p.precio_base),
                modelo_3d_url=p.modelo_3d_url,
                imagen_url=p.imagen_url,
                estado=p.estado,
                categoria_nombre=cat.nombre if cat else None,
                coleccion_nombre=col.nombre if col else None,
                proveedor_nombre=prov.nombre_empresa if prov else None,
            )
        )
    return resultado


@router.get("/{prenda_id}", response_model=PrendaOut)
def obtener_prenda(prenda_id: int, db: Session = Depends(get_db)):
    """CU-08: Obtener detalle de una prenda específica"""
    prenda = db.get(Prenda, prenda_id)
    if not prenda or not prenda.estado:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prenda no encontrada")

    cat = db.get(Categoria, prenda.categoria_id) if prenda.categoria_id else None
    col = db.get(Coleccion, prenda.coleccion_id) if prenda.coleccion_id else None
    prov = db.get(Proveedor, prenda.proveedor_id) if prenda.proveedor_id else None

    return PrendaOut(
        id=prenda.id,
        nombre=prenda.nombre,
        descripcion=prenda.descripcion,
        categoria_id=prenda.categoria_id,
        coleccion_id=prenda.coleccion_id,
        proveedor_id=prenda.proveedor_id,
        precio_base=float(prenda.precio_base),
        modelo_3d_url=prenda.modelo_3d_url,
        imagen_url=prenda.imagen_url,
        estado=prenda.estado,
        categoria_nombre=cat.nombre if cat else None,
        coleccion_nombre=col.nombre if col else None,
        proveedor_nombre=prov.nombre_empresa if prov else None,
    )


@router.post("", response_model=PrendaOut, status_code=status.HTTP_201_CREATED)
def crear_prenda(
    datos: PrendaCreate,
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_roles(["Administrador"])),
):
    """CU-08: Registrar nueva prenda en el catálogo con modelo 3D para vestidor virtual"""
    # 3. Validar existencia de categoría referenciada
    categoria = db.get(Categoria, datos.categoria_id)
    if not categoria or not categoria.estado:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"La categoría ID {datos.categoria_id} no existe o no se encuentra activa",
        )

    # Validar colección si se proporciona
    if datos.coleccion_id:
        coleccion = db.get(Coleccion, datos.coleccion_id)
        if not coleccion or not coleccion.estado:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"La colección ID {datos.coleccion_id} no existe o no se encuentra activa",
            )

    # Validar proveedor si se proporciona
    if datos.proveedor_id:
        proveedor = db.get(Proveedor, datos.proveedor_id)
        if not proveedor or not proveedor.estado:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"El proveedor ID {datos.proveedor_id} no existe o no se encuentra activo",
            )

    # 4. Guardar prenda con estado activo
    nueva_prenda = Prenda(
        nombre=datos.nombre,
        descripcion=datos.descripcion,
        categoria_id=datos.categoria_id,
        coleccion_id=datos.coleccion_id,
        proveedor_id=datos.proveedor_id,
        precio_base=datos.precio_base,
        modelo_3d_url=datos.modelo_3d_url,
        imagen_url=datos.imagen_url,
        estado=True,
    )
    db.add(nueva_prenda)
    db.commit()
    db.refresh(nueva_prenda)

    col = db.get(Coleccion, nueva_prenda.coleccion_id) if nueva_prenda.coleccion_id else None
    prov = db.get(Proveedor, nueva_prenda.proveedor_id) if nueva_prenda.proveedor_id else None

    return PrendaOut(
        id=nueva_prenda.id,
        nombre=nueva_prenda.nombre,
        descripcion=nueva_prenda.descripcion,
        categoria_id=nueva_prenda.categoria_id,
        coleccion_id=nueva_prenda.coleccion_id,
        proveedor_id=nueva_prenda.proveedor_id,
        precio_base=float(nueva_prenda.precio_base),
        modelo_3d_url=nueva_prenda.modelo_3d_url,
        imagen_url=nueva_prenda.imagen_url,
        estado=nueva_prenda.estado,
        categoria_nombre=categoria.nombre,
        coleccion_nombre=col.nombre if col else None,
        proveedor_nombre=prov.nombre_empresa if prov else None,
    )


@router.put("/{prenda_id}", response_model=PrendaOut)
def actualizar_prenda(
    prenda_id: int,
    datos: PrendaUpdate,
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_roles(["Administrador"])),
):
    """CU-08: Modificar datos de una prenda"""
    prenda = db.get(Prenda, prenda_id)
    if not prenda:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prenda no encontrada")

    if datos.categoria_id is not None:
        cat = db.get(Categoria, datos.categoria_id)
        if not cat or not cat.estado:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Categoría no válida")
        prenda.categoria_id = datos.categoria_id

    if datos.coleccion_id is not None:
        col = db.get(Coleccion, datos.coleccion_id)
        if not col or not col.estado:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Colección no válida")
        prenda.coleccion_id = datos.coleccion_id

    if datos.proveedor_id is not None:
        prov = db.get(Proveedor, datos.proveedor_id)
        if not prov or not prov.estado:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Proveedor no válido")
        prenda.proveedor_id = datos.proveedor_id

    if datos.nombre is not None:
        prenda.nombre = datos.nombre
    if datos.descripcion is not None:
        prenda.descripcion = datos.descripcion
    if datos.precio_base is not None:
        prenda.precio_base = datos.precio_base
    if datos.modelo_3d_url is not None:
        prenda.modelo_3d_url = datos.modelo_3d_url
    if datos.imagen_url is not None:
        prenda.imagen_url = datos.imagen_url
    if datos.estado is not None:
        prenda.estado = datos.estado

    db.commit()
    db.refresh(prenda)

    cat = db.get(Categoria, prenda.categoria_id) if prenda.categoria_id else None
    col = db.get(Coleccion, prenda.coleccion_id) if prenda.coleccion_id else None
    prov = db.get(Proveedor, prenda.proveedor_id) if prenda.proveedor_id else None

    return PrendaOut(
        id=prenda.id,
        nombre=prenda.nombre,
        descripcion=prenda.descripcion,
        categoria_id=prenda.categoria_id,
        coleccion_id=prenda.coleccion_id,
        proveedor_id=prenda.proveedor_id,
        precio_base=float(prenda.precio_base),
        modelo_3d_url=prenda.modelo_3d_url,
        imagen_url=prenda.imagen_url,
        estado=prenda.estado,
        categoria_nombre=cat.nombre if cat else None,
        coleccion_nombre=col.nombre if col else None,
        proveedor_nombre=prov.nombre_empresa if prov else None,
    )


@router.delete("/{prenda_id}")
def eliminar_prenda(
    prenda_id: int,
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_roles(["Administrador"])),
):
    """CU-08: Desactivar prenda del catálogo"""
    prenda = db.get(Prenda, prenda_id)
    if not prenda:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prenda no encontrada")

    prenda.estado = False
    db.commit()
    return {"message": f"Prenda '{prenda.nombre}' desactivada correctamente"}

