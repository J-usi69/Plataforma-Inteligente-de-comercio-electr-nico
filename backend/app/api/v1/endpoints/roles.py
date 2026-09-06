from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.models.seguridad import Permiso, Rol, RolPermiso, Usuario, UsuarioRol
from app.schemas.seguridad import (
    AsignarRolesUsuario,
    PermisoOut,
    RolCreate,
    RolOut,
    RolUpdate,
)

router = APIRouter()


@router.get("/permisos", response_model=List[PermisoOut])
def listar_permisos(
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_roles(["Administrador"])),
):
    """Listar todos los permisos disponibles agrupados por módulo"""
    stmt = select(Permiso).where(Permiso.estado.is_(True)).order_by(Permiso.modulo, Permiso.id)
    return list(db.scalars(stmt).all())


@router.get("/roles", response_model=List[RolOut])
def listar_roles(
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_roles(["Administrador"])),
):
    """CU-04: Mostrar roles existentes con sus permisos por módulo"""
    roles = db.scalars(select(Rol).where(Rol.estado.is_(True)).order_by(Rol.id)).all()
    resultado = []
    for r in roles:
        # Obtener permisos asociados
        stmt_permisos = (
            select(Permiso)
            .join(RolPermiso, RolPermiso.permiso_id == Permiso.id)
            .where(RolPermiso.rol_id == r.id, Permiso.estado.is_(True))
        )
        permisos = list(db.scalars(stmt_permisos).all())
        resultado.append(
            RolOut(
                id=r.id,
                nombre=r.nombre,
                descripcion=r.descripcion,
                estado=r.estado,
                permisos=permisos,
            )
        )
    return resultado


@router.post("/roles", response_model=RolOut, status_code=status.HTTP_201_CREATED)
def crear_rol(
    datos: RolCreate,
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_roles(["Administrador"])),
):
    """CU-04: Crear un nuevo rol y asociarle permisos"""
    existente = db.scalars(select(Rol).where(Rol.nombre == datos.nombre)).first()
    if existente:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ya existe un rol con el nombre '{datos.nombre}'",
        )

    nuevo_rol = Rol(nombre=datos.nombre, descripcion=datos.descripcion, estado=True)
    db.add(nuevo_rol)
    db.commit()
    db.refresh(nuevo_rol)

    if datos.permiso_ids:
        for p_id in datos.permiso_ids:
            db.add(RolPermiso(rol_id=nuevo_rol.id, permiso_id=p_id))
        db.commit()

    stmt_permisos = (
        select(Permiso)
        .join(RolPermiso, RolPermiso.permiso_id == Permiso.id)
        .where(RolPermiso.rol_id == nuevo_rol.id)
    )
    permisos = list(db.scalars(stmt_permisos).all())

    return RolOut(
        id=nuevo_rol.id,
        nombre=nuevo_rol.nombre,
        descripcion=nuevo_rol.descripcion,
        estado=nuevo_rol.estado,
        permisos=permisos,
    )


@router.put("/roles/{rol_id}", response_model=RolOut)
def actualizar_rol(
    rol_id: int,
    datos: RolUpdate,
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_roles(["Administrador"])),
):
    """CU-04: Editar rol y actualizar sus permisos por módulo"""
    rol = db.get(Rol, rol_id)
    if not rol:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rol no encontrado")

    if datos.nombre is not None and datos.nombre != rol.nombre:
        existente = db.scalars(select(Rol).where(Rol.nombre == datos.nombre, Rol.id != rol_id)).first()
        if existente:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Ya existe otro rol con el nombre '{datos.nombre}'",
            )
        rol.nombre = datos.nombre

    if datos.descripcion is not None:
        rol.descripcion = datos.descripcion

    if datos.estado is not None:
        rol.estado = datos.estado

    if datos.permiso_ids is not None:
        # Reemplazar permisos
        db.execute(delete(RolPermiso).where(RolPermiso.rol_id == rol_id))
        for p_id in datos.permiso_ids:
            db.add(RolPermiso(rol_id=rol_id, permiso_id=p_id))

    db.commit()
    db.refresh(rol)

    stmt_permisos = (
        select(Permiso)
        .join(RolPermiso, RolPermiso.permiso_id == Permiso.id)
        .where(RolPermiso.rol_id == rol.id)
    )
    permisos = list(db.scalars(stmt_permisos).all())

    return RolOut(
        id=rol.id,
        nombre=rol.nombre,
        descripcion=rol.descripcion,
        estado=rol.estado,
        permisos=permisos,
    )


@router.delete("/roles/{rol_id}")
def eliminar_rol(
    rol_id: int,
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_roles(["Administrador"])),
):
    """CU-04: Eliminar rol (con validación de usuarios activos)"""
    rol = db.get(Rol, rol_id)
    if not rol:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rol no encontrado")

    # Excepción CU-04: Si se intenta eliminar un rol con usuarios activos asignados, impedir eliminación
    usuarios_activos = (
        db.scalars(
            select(Usuario)
            .join(UsuarioRol, UsuarioRol.usuario_id == Usuario.id)
            .where(
                UsuarioRol.rol_id == rol_id,
                Usuario.estado.is_(True),
                Usuario.fecha_eliminacion.is_(None),
            )
        ).all()
    )

    if usuarios_activos:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se puede eliminar el rol '{rol.nombre}' porque tiene {len(usuarios_activos)} usuario(s) activo(s) asignado(s). Reasigne primero los usuarios.",
        )

    rol.estado = False
    db.commit()
    return {"message": f"Rol '{rol.nombre}' desactivado correctamente"}


@router.post("/usuarios/{usuario_id}/roles")
def asignar_roles_usuario(
    usuario_id: int,
    datos: AsignarRolesUsuario,
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_roles(["Administrador"])),
):
    """CU-04: Asignar roles a un usuario"""
    usuario = db.get(Usuario, usuario_id)
    if not usuario:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")

    db.execute(delete(UsuarioRol).where(UsuarioRol.usuario_id == usuario_id))
    for r_id in datos.rol_ids:
        db.add(UsuarioRol(usuario_id=usuario_id, rol_id=r_id))
    db.commit()

    return {"message": f"Roles asignados correctamente al usuario {usuario.correo}"}

