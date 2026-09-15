from datetime import datetime, timezone
from typing import Callable, List, Optional
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.seguridad import Bitacora, Permiso, Rol, RolPermiso, Usuario, UsuarioRol

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def get_client_ip(request: Request) -> Optional[str]:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


def registrar_bitacora(db: Session, usuario_id: int, accion: str, ip: Optional[str] = None) -> Bitacora:
    registro = Bitacora(
        usuario_id=usuario_id,
        accion=accion,
        ip=ip,
        fecha=datetime.now(timezone.utc),
    )
    db.add(registro)
    db.commit()
    db.refresh(registro)
    return registro


def get_user_roles(usuario_id: int, db: Session) -> List[str]:
    stmt = (
        select(Rol.nombre)
        .join(UsuarioRol, UsuarioRol.rol_id == Rol.id)
        .where(UsuarioRol.usuario_id == usuario_id, Rol.estado.is_(True))
    )
    return list(db.scalars(stmt).all())


def get_user_permisos(usuario_id: int, db: Session) -> List[str]:
    stmt = (
        select(Permiso.codigo)
        .join(RolPermiso, RolPermiso.permiso_id == Permiso.id)
        .join(Rol, Rol.id == RolPermiso.rol_id)
        .join(UsuarioRol, UsuarioRol.rol_id == Rol.id)
        .where(
            UsuarioRol.usuario_id == usuario_id,
            Rol.estado.is_(True),
            Permiso.estado.is_(True),
        )
        .distinct()
    )
    return list(db.scalars(stmt).all())


def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Usuario:
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No se proporcionó token de autenticación",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token no contiene identificador de usuario",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = db.get(Usuario, int(user_id))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado",
        )
    if not user.estado or user.fecha_eliminacion is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cuenta de usuario inactiva o deshabilitada",
        )
    return user


def get_current_active_user(
    current_user: Usuario = Depends(get_current_user),
) -> Usuario:
    return current_user


def get_optional_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Optional[Usuario]:
    """Como get_current_user, pero sin exigir sesión: usado en endpoints que también
    deben funcionar para visitantes anónimos (ej. el chatbot, CU-29)."""
    if not token:
        return None
    payload = decode_access_token(token)
    if not payload:
        return None
    user_id = payload.get("sub")
    if not user_id:
        return None
    user = db.get(Usuario, int(user_id))
    if not user or not user.estado or user.fecha_eliminacion is not None:
        return None
    return user


def require_roles(allowed_roles: List[str]) -> Callable:
    def role_checker(
        current_user: Usuario = Depends(get_current_active_user),
        db: Session = Depends(get_db),
    ) -> Usuario:
        roles = get_user_roles(current_user.id, db)
        if not any(role in allowed_roles for role in roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No cuenta con los roles necesarios para esta operación",
            )
        return current_user

    return role_checker


def require_permission(permission_code: str) -> Callable:
    def permission_checker(
        current_user: Usuario = Depends(get_current_active_user),
        db: Session = Depends(get_db),
    ) -> Usuario:
        roles = get_user_roles(current_user.id, db)
        if "Administrador" in roles:
            return current_user
        permisos = get_user_permisos(current_user.id, db)
        if permission_code not in permisos:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permiso insuficiente: requiere '{permission_code}'",
            )
        return current_user

    return permission_checker

