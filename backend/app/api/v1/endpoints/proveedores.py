from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.models.catalogo import Prenda, Proveedor
from app.models.seguridad import Usuario
from app.schemas.proveedor import ProveedorCreate, ProveedorOut, ProveedorUpdate

router = APIRouter()


@router.get("", response_model=List[ProveedorOut])
def listar_proveedores(
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_roles(["Administrador"])),
):
    """CU-07: Listar proveedores existentes"""
    stmt = select(Proveedor).where(Proveedor.estado.is_(True)).order_by(Proveedor.id)
    return list(db.scalars(stmt).all())


@router.get("/{proveedor_id}", response_model=ProveedorOut)
def obtener_proveedor(
    proveedor_id: int,
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_roles(["Administrador"])),
):
    """Obtener detalle de un proveedor"""
    proveedor = db.get(Proveedor, proveedor_id)
    if not proveedor or not proveedor.estado:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proveedor no encontrado")
    return proveedor


@router.post("", response_model=ProveedorOut, status_code=status.HTTP_201_CREATED)
def crear_proveedor(
    datos: ProveedorCreate,
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_roles(["Administrador"])),
):
    """CU-07: Registrar nuevo proveedor"""
    existente = db.scalars(
        select(Proveedor).where(Proveedor.nombre_empresa == datos.nombre_empresa)
    ).first()
    if existente:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ya existe un proveedor con la razón social '{datos.nombre_empresa}'",
        )

    nuevo = Proveedor(
        nombre_empresa=datos.nombre_empresa,
        contacto=datos.contacto,
        estado=True,
    )
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)
    return nuevo


@router.put("/{proveedor_id}", response_model=ProveedorOut)
def actualizar_proveedor(
    proveedor_id: int,
    datos: ProveedorUpdate,
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_roles(["Administrador"])),
):
    """CU-07: Modificar información de un proveedor"""
    proveedor = db.get(Proveedor, proveedor_id)
    if not proveedor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proveedor no encontrado")

    if datos.nombre_empresa is not None:
        existente = db.scalars(
            select(Proveedor).where(
                Proveedor.nombre_empresa == datos.nombre_empresa,
                Proveedor.id != proveedor_id,
            )
        ).first()
        if existente:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Ya existe otro proveedor con el nombre '{datos.nombre_empresa}'",
            )
        proveedor.nombre_empresa = datos.nombre_empresa

    if datos.contacto is not None:
        proveedor.contacto = datos.contacto
    if datos.estado is not None:
        proveedor.estado = datos.estado

    db.commit()
    db.refresh(proveedor)
    return proveedor


@router.delete("/{proveedor_id}")
def eliminar_proveedor(
    proveedor_id: int,
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_roles(["Administrador"])),
):
    """CU-07: Desactivar proveedor con validación de prendas activas asociadas"""
    proveedor = db.get(Proveedor, proveedor_id)
    if not proveedor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proveedor no encontrado")

    # Excepción CU-07: Si tiene prendas activas asociadas, advertir / validar
    prendas_activas = db.scalars(
        select(Prenda).where(
            Prenda.proveedor_id == proveedor_id,
            Prenda.estado.is_(True),
        )
    ).all()
    if prendas_activas:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se puede desactivar el proveedor porque tiene {len(prendas_activas)} prenda(s) activa(s) asociada(s)",
        )

    proveedor.estado = False
    db.commit()
    return {"message": f"Proveedor '{proveedor.nombre_empresa}' desactivado correctamente"}

