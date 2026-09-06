from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.core.security import get_password_hash
from app.models.seguridad import Rol, Usuario, UsuarioRol
from app.models.sucursal import Personal, Sucursal
from app.schemas.personal import PersonalCreate, PersonalOut, PersonalUpdate

router = APIRouter()


@router.get("", response_model=List[PersonalOut])
def listar_personal(
    sucursal_id: Optional[int] = None,
    cargo: Optional[str] = None,
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_roles(["Administrador"])),
):
    """CU-05: Listar miembros del personal interno"""
    stmt = select(Personal).where(Personal.estado.is_(True), Personal.fecha_eliminacion.is_(None))
    if sucursal_id:
        stmt = stmt.where(Personal.sucursal_id == sucursal_id)
    if cargo:
        stmt = stmt.where(Personal.cargo == cargo)

    personal_list = db.scalars(stmt).all()
    resultado = []
    for p in personal_list:
        usuario = db.get(Usuario, p.usuario_id)
        sucursal = db.get(Sucursal, p.sucursal_id) if p.sucursal_id else None
        resultado.append(
            PersonalOut(
                id=p.id,
                usuario_id=p.usuario_id,
                sucursal_id=p.sucursal_id,
                nombres=p.nombres,
                apellidos=p.apellidos,
                cargo=p.cargo,
                estado=p.estado,
                correo=usuario.correo if usuario else None,
                celular=usuario.celular if usuario else None,
                sucursal_nombre=sucursal.nombre if sucursal else None,
            )
        )
    return resultado


@router.post("", response_model=PersonalOut, status_code=status.HTTP_201_CREATED)
def crear_personal(
    datos: PersonalCreate,
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_roles(["Administrador"])),
):
    """CU-05: Registrar miembro del personal (Encargado o Cajero)"""
    # Validar sucursal si viene especificada
    if datos.sucursal_id:
        sucursal = db.get(Sucursal, datos.sucursal_id)
        if not sucursal or not sucursal.estado:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La sucursal especificada no existe o no se encuentra activa",
            )

    # Validar cargo
    if datos.cargo not in ["Encargado", "Cajero", "Administrador"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El cargo debe ser 'Encargado', 'Cajero' o 'Administrador'",
        )

    # Excepción CU-05: Si el correo o celular ya existe, vincular la cuenta existente
    usuario = db.scalars(select(Usuario).where(Usuario.correo == datos.correo)).first()
    if usuario:
        # Verificar si ya tiene personal asignado
        personal_existente = db.scalars(select(Personal).where(Personal.usuario_id == usuario.id)).first()
        if personal_existente:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El usuario ya se encuentra registrado como personal",
            )
    else:
        # Crear usuario base
        usuario = Usuario(
            correo=datos.correo,
            password_hash=get_password_hash(datos.password),
            celular=datos.celular,
            estado=True,
            creado_en=datetime.now(timezone.utc),
        )
        db.add(usuario)
        db.commit()
        db.refresh(usuario)

    # Asignar rol correspondiente al cargo
    rol_cargo = db.scalars(select(Rol).where(Rol.nombre == datos.cargo)).first()
    if rol_cargo:
        existe_rol = db.scalars(
            select(UsuarioRol).where(
                UsuarioRol.usuario_id == usuario.id,
                UsuarioRol.rol_id == rol_cargo.id,
            )
        ).first()
        if not existe_rol:
            db.add(UsuarioRol(usuario_id=usuario.id, rol_id=rol_cargo.id))
            db.commit()

    nuevo_personal = Personal(
        usuario_id=usuario.id,
        sucursal_id=datos.sucursal_id,
        nombres=datos.nombres,
        apellidos=datos.apellidos,
        cargo=datos.cargo,
        estado=True,
    )
    db.add(nuevo_personal)
    db.commit()
    db.refresh(nuevo_personal)

    sucursal = db.get(Sucursal, nuevo_personal.sucursal_id) if nuevo_personal.sucursal_id else None

    return PersonalOut(
        id=nuevo_personal.id,
        usuario_id=nuevo_personal.usuario_id,
        sucursal_id=nuevo_personal.sucursal_id,
        nombres=nuevo_personal.nombres,
        apellidos=nuevo_personal.apellidos,
        cargo=nuevo_personal.cargo,
        estado=nuevo_personal.estado,
        correo=usuario.correo,
        celular=usuario.celular,
        sucursal_nombre=sucursal.nombre if sucursal else None,
    )


@router.put("/{personal_id}", response_model=PersonalOut)
def actualizar_personal(
    personal_id: int,
    datos: PersonalUpdate,
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_roles(["Administrador"])),
):
    """CU-05: Modificar datos de personal o reasignar sucursal/cargo"""
    personal = db.get(Personal, personal_id)
    if not personal or personal.fecha_eliminacion is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Personal no encontrado")

    if datos.nombres is not None:
        personal.nombres = datos.nombres
    if datos.apellidos is not None:
        personal.apellidos = datos.apellidos
    if datos.cargo is not None:
        personal.cargo = datos.cargo
    if datos.sucursal_id is not None:
        sucursal = db.get(Sucursal, datos.sucursal_id)
        if not sucursal or not sucursal.estado:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Sucursal no válida")
        personal.sucursal_id = datos.sucursal_id
    if datos.estado is not None:
        personal.estado = datos.estado

    usuario = db.get(Usuario, personal.usuario_id)
    if usuario and datos.celular is not None:
        usuario.celular = datos.celular

    db.commit()
    db.refresh(personal)

    sucursal = db.get(Sucursal, personal.sucursal_id) if personal.sucursal_id else None

    return PersonalOut(
        id=personal.id,
        usuario_id=personal.usuario_id,
        sucursal_id=personal.sucursal_id,
        nombres=personal.nombres,
        apellidos=personal.apellidos,
        cargo=personal.cargo,
        estado=personal.estado,
        correo=usuario.correo if usuario else None,
        celular=usuario.celular if usuario else None,
        sucursal_nombre=sucursal.nombre if sucursal else None,
    )


@router.delete("/{personal_id}")
def eliminar_personal(
    personal_id: int,
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_roles(["Administrador"])),
):
    """CU-05: Desactivar personal"""
    personal = db.get(Personal, personal_id)
    if not personal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Personal no encontrado")

    personal.estado = False
    personal.fecha_eliminacion = datetime.now(timezone.utc)
    db.commit()
    return {"message": f"Personal {personal.nombres} {personal.apellidos} desactivado correctamente"}

