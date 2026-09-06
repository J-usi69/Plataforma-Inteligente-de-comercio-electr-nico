from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.models.catalogo import Coleccion, Prenda, Temporada
from app.models.seguridad import Usuario
from app.schemas.catalogo import (
    ColeccionCreate,
    ColeccionOut,
    ColeccionUpdate,
    TemporadaCreate,
    TemporadaOut,
    TemporadaUpdate,
)

router = APIRouter()


# --- Temporadas ---
@router.get("/temporadas", response_model=List[TemporadaOut])
def listar_temporadas(db: Session = Depends(get_db)):
    """CU-10: Listar temporadas registradas"""
    stmt = select(Temporada).order_by(Temporada.fecha_inicio.desc().nullslast())
    return list(db.scalars(stmt).all())


@router.post("/temporadas", response_model=TemporadaOut, status_code=status.HTTP_201_CREATED)
def crear_temporada(
    datos: TemporadaCreate,
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_roles(["Administrador"])),
):
    """CU-10: Registrar una nueva temporada, validando coherencia de fechas"""
    if datos.fecha_inicio and datos.fecha_fin and datos.fecha_inicio > datos.fecha_fin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La fecha de inicio debe ser anterior a la fecha de fin",
        )

    nueva = Temporada(
        nombre=datos.nombre,
        tipo=datos.tipo,
        fecha_inicio=datos.fecha_inicio,
        fecha_fin=datos.fecha_fin,
        estado=True,
    )
    db.add(nueva)
    db.commit()
    db.refresh(nueva)
    return nueva


@router.put("/temporadas/{temporada_id}", response_model=TemporadaOut)
def actualizar_temporada(
    temporada_id: int,
    datos: TemporadaUpdate,
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_roles(["Administrador"])),
):
    """CU-10: Editar una temporada existente"""
    temporada = db.get(Temporada, temporada_id)
    if not temporada:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Temporada no encontrada")

    nueva_inicio = datos.fecha_inicio if datos.fecha_inicio is not None else temporada.fecha_inicio
    nueva_fin = datos.fecha_fin if datos.fecha_fin is not None else temporada.fecha_fin
    if nueva_inicio and nueva_fin and nueva_inicio > nueva_fin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La fecha de inicio debe ser anterior a la fecha de fin",
        )

    if datos.nombre is not None:
        temporada.nombre = datos.nombre
    if datos.tipo is not None:
        temporada.tipo = datos.tipo
    if datos.fecha_inicio is not None:
        temporada.fecha_inicio = datos.fecha_inicio
    if datos.fecha_fin is not None:
        temporada.fecha_fin = datos.fecha_fin
    if datos.estado is not None:
        temporada.estado = datos.estado

    db.commit()
    db.refresh(temporada)
    return temporada


# --- Colecciones ---
@router.get("/colecciones", response_model=List[ColeccionOut])
def listar_colecciones(
    temporada_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """CU-10: Listar colecciones registradas, opcionalmente filtradas por temporada"""
    stmt = select(Coleccion)
    if temporada_id:
        stmt = stmt.where(Coleccion.temporada_id == temporada_id)
    colecciones = db.scalars(stmt.order_by(Coleccion.nombre)).all()

    resultado = []
    for c in colecciones:
        temporada = db.get(Temporada, c.temporada_id)
        resultado.append(
            ColeccionOut(
                id=c.id,
                nombre=c.nombre,
                descripcion=c.descripcion,
                temporada_id=c.temporada_id,
                estado=c.estado,
                temporada_nombre=temporada.nombre if temporada else None,
            )
        )
    return resultado


@router.post("/colecciones", response_model=ColeccionOut, status_code=status.HTTP_201_CREATED)
def crear_coleccion(
    datos: ColeccionCreate,
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_roles(["Administrador"])),
):
    """CU-10: Registrar una nueva colección asociada a una temporada"""
    temporada = db.get(Temporada, datos.temporada_id)
    if not temporada or not temporada.estado:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La temporada especificada no es válida")

    nueva = Coleccion(
        nombre=datos.nombre,
        descripcion=datos.descripcion,
        temporada_id=datos.temporada_id,
        estado=True,
    )
    db.add(nueva)
    db.commit()
    db.refresh(nueva)

    return ColeccionOut(
        id=nueva.id,
        nombre=nueva.nombre,
        descripcion=nueva.descripcion,
        temporada_id=nueva.temporada_id,
        estado=nueva.estado,
        temporada_nombre=temporada.nombre,
    )


@router.put("/colecciones/{coleccion_id}", response_model=ColeccionOut)
def actualizar_coleccion(
    coleccion_id: int,
    datos: ColeccionUpdate,
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_roles(["Administrador"])),
):
    """CU-10: Editar una colección existente"""
    coleccion = db.get(Coleccion, coleccion_id)
    if not coleccion:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Colección no encontrada")

    if datos.estado is False:
        en_uso = db.scalars(
            select(Prenda).where(Prenda.coleccion_id == coleccion_id, Prenda.estado.is_(True))
        ).first()
        if en_uso:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se puede desactivar: existen prendas activas asociadas a esta colección",
            )

    if datos.temporada_id is not None:
        temporada = db.get(Temporada, datos.temporada_id)
        if not temporada or not temporada.estado:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Temporada inválida")
        coleccion.temporada_id = datos.temporada_id

    if datos.nombre is not None:
        coleccion.nombre = datos.nombre
    if datos.descripcion is not None:
        coleccion.descripcion = datos.descripcion
    if datos.estado is not None:
        coleccion.estado = datos.estado

    db.commit()
    db.refresh(coleccion)

    temporada = db.get(Temporada, coleccion.temporada_id)
    return ColeccionOut(
        id=coleccion.id,
        nombre=coleccion.nombre,
        descripcion=coleccion.descripcion,
        temporada_id=coleccion.temporada_id,
        estado=coleccion.estado,
        temporada_nombre=temporada.nombre if temporada else None,
    )
