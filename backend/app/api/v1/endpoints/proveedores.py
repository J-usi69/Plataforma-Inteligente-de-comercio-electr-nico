from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.core.security import get_password_hash
from app.models.catalogo import DisponibilidadProveedor, Prenda, Proveedor
from app.models.seguridad import Rol, Usuario, UsuarioRol
from app.schemas.proveedor import (
    DisponibilidadOut,
    ProveedorCreate,
    ProveedorOut,
    ProveedorUpdate,
)

router = APIRouter()


def _proveedor_a_out(db: Session, proveedor: Proveedor) -> ProveedorOut:
    usuario = db.get(Usuario, proveedor.usuario_id) if proveedor.usuario_id else None
    return ProveedorOut(
        id=proveedor.id,
        nombre_empresa=proveedor.nombre_empresa,
        contacto=proveedor.contacto,
        estado=proveedor.estado,
        correo=usuario.correo if usuario else None,
        celular=usuario.celular if usuario else None,
    )


@router.get("", response_model=List[ProveedorOut])
def listar_proveedores(
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_roles(["Administrador"])),
):
    """CU-07: Listar proveedores existentes"""
    stmt = select(Proveedor).where(Proveedor.estado.is_(True)).order_by(Proveedor.id)
    return [_proveedor_a_out(db, p) for p in db.scalars(stmt).all()]


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
    return _proveedor_a_out(db, proveedor)


@router.post("", response_model=ProveedorOut, status_code=status.HTTP_201_CREATED)
def crear_proveedor(
    datos: ProveedorCreate,
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_roles(["Administrador"])),
):
    """CU-07: Registrar nuevo proveedor. Si se indica correo/password, se le crea
    acceso propio (rol Proveedor) para que pueda registrar productos y disponibilidad (CU-33, CU-34)."""
    existente = db.scalars(
        select(Proveedor).where(Proveedor.nombre_empresa == datos.nombre_empresa)
    ).first()
    if existente:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ya existe un proveedor con la razón social '{datos.nombre_empresa}'",
        )

    usuario_id = None
    if datos.correo:
        if not datos.password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Debe indicar una contraseña para dar acceso al proveedor",
            )
        usuario = db.scalars(select(Usuario).where(Usuario.correo == datos.correo)).first()
        if usuario:
            proveedor_existente = db.scalars(select(Proveedor).where(Proveedor.usuario_id == usuario.id)).first()
            if proveedor_existente:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="El usuario ya se encuentra registrado como proveedor",
                )
        else:
            usuario = Usuario(
                correo=datos.correo,
                password_hash=get_password_hash(datos.password),
                estado=True,
                creado_en=datetime.now(timezone.utc),
            )
            db.add(usuario)
            db.commit()
            db.refresh(usuario)

        rol_proveedor = db.scalars(select(Rol).where(Rol.nombre == "Proveedor")).first()
        if rol_proveedor:
            existe_rol = db.scalars(
                select(UsuarioRol).where(
                    UsuarioRol.usuario_id == usuario.id,
                    UsuarioRol.rol_id == rol_proveedor.id,
                )
            ).first()
            if not existe_rol:
                db.add(UsuarioRol(usuario_id=usuario.id, rol_id=rol_proveedor.id))
                db.commit()

        usuario_id = usuario.id

    nuevo = Proveedor(
        usuario_id=usuario_id,
        nombre_empresa=datos.nombre_empresa,
        contacto=datos.contacto,
        estado=True,
    )
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)
    return _proveedor_a_out(db, nuevo)


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
    return _proveedor_a_out(db, proveedor)


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


@router.get("/{proveedor_id}/disponibilidad", response_model=List[DisponibilidadOut])
def obtener_disponibilidad_proveedor(
    proveedor_id: int,
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_roles(["Administrador"])),
):
    """CU-34 (postcondición): el administrador consulta la disponibilidad informada
    por un proveedor al planificar la reposición de inventario."""
    proveedor = db.get(Proveedor, proveedor_id)
    if not proveedor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proveedor no encontrado")

    stmt = (
        select(DisponibilidadProveedor)
        .where(DisponibilidadProveedor.proveedor_id == proveedor_id)
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
