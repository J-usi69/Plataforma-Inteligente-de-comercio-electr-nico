from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.deps import (
    get_client_ip,
    get_current_active_user,
    get_user_permisos,
    get_user_roles,
    registrar_bitacora,
    require_roles,
)
from app.core.security import create_access_token, get_password_hash, verify_password
from app.db.session import get_db
from app.models.seguridad import Bitacora, Rol, Usuario, UsuarioRol
from app.models.sucursal import Sucursal
from app.schemas.auth import (
    BitacoraOut,
    PersonalBriefOut,
    ProveedorBriefOut,
    TokenResponse,
    UsuarioLogin,
    UsuarioOut,
    UsuarioRegister,
    UsuarioUpdate,
)

router = APIRouter()


def _construir_usuario_out(db: Session, usuario: Usuario) -> UsuarioOut:
    roles = get_user_roles(usuario.id, db)
    permisos = get_user_permisos(usuario.id, db)
    personal_out = None
    if usuario.personal:
        sucursal = db.get(Sucursal, usuario.personal.sucursal_id) if usuario.personal.sucursal_id else None
        personal_out = PersonalBriefOut(
            id=usuario.personal.id,
            nombres=usuario.personal.nombres,
            apellidos=usuario.personal.apellidos,
            cargo=usuario.personal.cargo,
            sucursal_id=usuario.personal.sucursal_id,
            sucursal_nombre=sucursal.nombre if sucursal else None,
        )
    proveedor_out = None
    if usuario.proveedor:
        proveedor_out = ProveedorBriefOut(
            id=usuario.proveedor.id,
            nombre_empresa=usuario.proveedor.nombre_empresa,
            contacto=usuario.proveedor.contacto,
        )
    return UsuarioOut(
        id=usuario.id,
        correo=usuario.correo,
        celular=usuario.celular,
        estado=usuario.estado,
        roles=roles,
        permisos=permisos,
        creado_en=usuario.creado_en,
        personal=personal_out,
        proveedor=proveedor_out,
    )


@router.post("/register", response_model=UsuarioOut, status_code=status.HTTP_201_CREATED)
def register(
    datos: UsuarioRegister,
    request: Request,
    db: Session = Depends(get_db),
):
    """CU-01: Registrar una nueva cuenta de cliente"""
    # 4. Validar que el correo no esté registrado previamente
    if db.scalars(select(Usuario).where(Usuario.correo == datos.correo)).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El correo electrónico ya se encuentra registrado",
        )

    # Validar celular único si fue proporcionado
    if datos.celular and db.scalars(select(Usuario).where(Usuario.celular == datos.celular)).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El número de celular ya se encuentra registrado",
        )

    # 5. Crear el registro Usuario
    nuevo_usuario = Usuario(
        correo=datos.correo,
        password_hash=get_password_hash(datos.password),
        celular=datos.celular,
        estado=True,
        creado_en=datetime.now(timezone.utc),
    )
    db.add(nuevo_usuario)
    db.commit()
    db.refresh(nuevo_usuario)

    # Asignar rol Cliente por defecto
    rol_cliente = db.scalars(select(Rol).where(Rol.nombre == "Cliente")).first()
    if rol_cliente:
        db.add(UsuarioRol(usuario_id=nuevo_usuario.id, rol_id=rol_cliente.id))
        db.commit()

    # Registrar en bitácora
    client_ip = get_client_ip(request)
    registrar_bitacora(db, nuevo_usuario.id, "Registro de cuenta", client_ip)

    return _construir_usuario_out(db, nuevo_usuario)


@router.post("/login", response_model=TokenResponse)
def login(
    credenciales: UsuarioLogin,
    request: Request,
    db: Session = Depends(get_db),
):
    """CU-02: Iniciar sesión con correo o celular"""
    client_ip = get_client_ip(request)

    # 2. Buscar usuario por correo o celular
    usuario = db.scalars(
        select(Usuario).where(
            or_(
                Usuario.correo == credenciales.login,
                Usuario.celular == credenciales.login,
            )
        )
    ).first()

    if not usuario or not verify_password(credenciales.password, usuario.password_hash):
        if usuario:
            registrar_bitacora(db, usuario.id, "Intento fallido de inicio de sesión", client_ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas (correo/celular o contraseña no válidos)",
        )

    # 3. Validar estado de la cuenta
    if not usuario.estado or usuario.fecha_eliminacion is not None:
        registrar_bitacora(db, usuario.id, "Intento de inicio de sesión en cuenta inactiva", client_ip)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="La cuenta de usuario se encuentra inactiva",
        )

    # 4. Obtener roles y permisos
    roles = get_user_roles(usuario.id, db)
    permisos = get_user_permisos(usuario.id, db)

    # 5. Generar token de sesión y registrar en bitácora
    token_data = {
        "sub": str(usuario.id),
        "email": usuario.correo,
        "roles": roles,
        "permisos": permisos,
    }
    access_token = create_access_token(token_data)
    registrar_bitacora(db, usuario.id, "Inicio de sesión", client_ip)

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        usuario=_construir_usuario_out(db, usuario),
    )


@router.post("/logout")
def logout(
    request: Request,
    current_user: Usuario = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """CU-03: Cerrar sesión e invalidar acceso"""
    client_ip = get_client_ip(request)
    registrar_bitacora(db, current_user.id, "Cierre de sesión", client_ip)
    return {"message": "Sesión cerrada correctamente"}


@router.get("/me", response_model=UsuarioOut)
def obtener_perfil(
    current_user: Usuario = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """CU-01: Consultar perfil del usuario autenticado"""
    return _construir_usuario_out(db, current_user)


@router.put("/me", response_model=UsuarioOut)
def actualizar_perfil(
    datos: UsuarioUpdate,
    request: Request,
    current_user: Usuario = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """CU-01: Actualizar datos de cuenta o desactivar cuenta"""
    if datos.celular is not None:
        # Validar celular único
        existente = db.scalars(
            select(Usuario).where(
                Usuario.celular == datos.celular,
                Usuario.id != current_user.id,
            )
        ).first()
        if existente:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El número de celular ya pertenece a otro usuario",
            )
        current_user.celular = datos.celular

    if datos.estado is not None:
        current_user.estado = datos.estado
        if not datos.estado:
            current_user.fecha_eliminacion = datetime.now(timezone.utc)

    db.commit()
    db.refresh(current_user)

    client_ip = get_client_ip(request)
    accion = "Actualización de perfil" if current_user.estado else "Desactivación de cuenta"
    registrar_bitacora(db, current_user.id, accion, client_ip)

    return _construir_usuario_out(db, current_user)


@router.get("/bitacora", response_model=List[BitacoraOut])
def listar_bitacora(
    limit: int = 50,
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_roles(["Administrador"])),
):
    """Consultar registros de auditoría de la Bitácora"""
    stmt = select(Bitacora).order_by(Bitacora.fecha.desc()).limit(limit)
    return list(db.scalars(stmt).all())

