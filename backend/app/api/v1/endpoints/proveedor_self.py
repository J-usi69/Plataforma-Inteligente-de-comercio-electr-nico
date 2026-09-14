from datetime import date, datetime, timezone
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.models.catalogo import Categoria, Coleccion, DisponibilidadProveedor, Prenda, Proveedor
from app.models.seguridad import Usuario
from app.schemas.catalogo import PrendaOut
from app.schemas.proveedor import DisponibilidadCreate, DisponibilidadOut, PrendaProveedorCreate

router = APIRouter()


def _proveedor_propio(current_user: Usuario, db: Session) -> Proveedor:
    proveedor = db.scalars(select(Proveedor).where(Proveedor.usuario_id == current_user.id)).first()
    if not proveedor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No se encontró un proveedor asociado a esta cuenta")
    return proveedor


def _prenda_a_out(db: Session, prenda: Prenda) -> PrendaOut:
    cat = db.get(Categoria, prenda.categoria_id) if prenda.categoria_id else None
    col = db.get(Coleccion, prenda.coleccion_id) if prenda.coleccion_id else None
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
        proveedor_nombre=None,
    )


@router.get("/prendas", response_model=List[PrendaOut])
def listar_mis_prendas(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_roles(["Proveedor"])),
):
    """CU-33: el proveedor consulta los productos que ha registrado."""
    proveedor = _proveedor_propio(current_user, db)
    stmt = select(Prenda).where(Prenda.proveedor_id == proveedor.id).order_by(Prenda.id.desc())
    return [_prenda_a_out(db, p) for p in db.scalars(stmt).all()]


@router.post("/prendas", response_model=PrendaOut, status_code=status.HTTP_201_CREATED)
def registrar_producto(
    datos: PrendaProveedorCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_roles(["Proveedor"])),
):
    """CU-33: el proveedor registra la información de un producto que ofrece a la
    cadena. Queda en estado pendiente (inactivo) hasta que el administrador lo valide
    e incorpore al catálogo (CU-08)."""
    proveedor = _proveedor_propio(current_user, db)

    categoria = db.get(Categoria, datos.categoria_id)
    if not categoria or not categoria.estado:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La categoría indicada no existe o no se encuentra activa")

    # Excepción CU-33: advertir sobre un posible duplicado por nombre para el mismo proveedor
    duplicado = db.scalars(
        select(Prenda).where(
            Prenda.proveedor_id == proveedor.id,
            Prenda.nombre.ilike(datos.nombre),
        )
    ).first()
    if duplicado and not datos.forzar:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ya registraste un producto con el nombre '{datos.nombre}'. Vuelve a enviarlo confirmando el duplicado si de todas formas quieres continuar.",
        )

    nueva_prenda = Prenda(
        nombre=datos.nombre,
        descripcion=datos.descripcion,
        categoria_id=datos.categoria_id,
        proveedor_id=proveedor.id,
        precio_base=datos.precio_base,
        modelo_3d_url=datos.modelo_3d_url,
        estado=False,
    )
    db.add(nueva_prenda)
    db.commit()
    db.refresh(nueva_prenda)
    return _prenda_a_out(db, nueva_prenda)


@router.post("/prendas/{prenda_id}/disponibilidad", response_model=DisponibilidadOut, status_code=status.HTTP_201_CREATED)
def informar_disponibilidad(
    prenda_id: int,
    datos: DisponibilidadCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_roles(["Proveedor"])),
):
    """CU-34: el proveedor comunica la disponibilidad y fecha de entrega prevista de un producto propio."""
    proveedor = _proveedor_propio(current_user, db)
    prenda = db.get(Prenda, prenda_id)
    if not prenda or prenda.proveedor_id != proveedor.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado")

    # Excepción CU-34: la prenda debe estar activa para informar disponibilidad
    if not prenda.estado:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Este producto fue dado de baja del catálogo; solicita al administrador que lo reactive antes de informar disponibilidad",
        )

    if datos.fecha_estimada <= date.today():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La fecha estimada de entrega debe ser posterior a hoy")

    nueva = DisponibilidadProveedor(
        prenda_id=prenda.id,
        proveedor_id=proveedor.id,
        cantidad=datos.cantidad,
        fecha_estimada=datos.fecha_estimada,
        fecha_registro=datetime.now(timezone.utc),
    )
    db.add(nueva)
    db.commit()
    db.refresh(nueva)
    return DisponibilidadOut(
        id=nueva.id,
        prenda_id=nueva.prenda_id,
        prenda_nombre=prenda.nombre,
        cantidad=nueva.cantidad,
        fecha_estimada=nueva.fecha_estimada,
        fecha_registro=nueva.fecha_registro,
    )


@router.get("/disponibilidad", response_model=List[DisponibilidadOut])
def listar_mi_disponibilidad(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_roles(["Proveedor"])),
):
    """CU-34: historial de disponibilidad informada por el proveedor autenticado."""
    proveedor = _proveedor_propio(current_user, db)
    stmt = (
        select(DisponibilidadProveedor)
        .where(DisponibilidadProveedor.proveedor_id == proveedor.id)
        .order_by(DisponibilidadProveedor.fecha_registro.desc())
    )
    resultado = []
    for d in db.scalars(stmt).all():
        prenda = db.get(Prenda, d.prenda_id)
        resultado.append(DisponibilidadOut(
            id=d.id,
            prenda_id=d.prenda_id,
            prenda_nombre=prenda.nombre if prenda else "Prenda eliminada",
            cantidad=d.cantidad,
            fecha_estimada=d.fecha_estimada,
            fecha_registro=d.fecha_registro,
        ))
    return resultado
