"""Alta de tiendas (onboarding del SaaS): crea la tienda con su suscripción, sus roles con la
matriz de permisos y la cuenta de su administrador, todo en una transacción."""
import re
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import get_password_hash
from app.db.tenancy import CLAVE_TIENDA
from app.models.seguridad import Rol, RolPermiso, Usuario, UsuarioRol
from app.models.tienda import Plan, Suscripcion, Tienda

# Roles con los que nace cada tienda; sus permisos se copian de la tienda por defecto, que hace
# de plantilla (su administrador ya afinó esa matriz, CU-04)
ROLES_BASE = ["Administrador", "Cliente", "Encargado", "Cajero", "Proveedor"]
SLUG_VALIDO = re.compile(r"^[a-z0-9](?:[a-z0-9-]{1,38}[a-z0-9])$")
SLUGS_RESERVADOS = {"plataforma", "api", "www", "admin", "app", "t", "static", "assets", "login"}


def validar_slug(slug: str) -> str:
    slug = slug.strip().lower()
    if not SLUG_VALIDO.match(slug) or "--" in slug:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="La dirección de la tienda debe tener de 3 a 40 letras minúsculas, números o guiones",
        )
    if slug in SLUGS_RESERVADOS:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Esa dirección está reservada, elegí otra")
    return slug


def crear_tienda(
    db: Session,
    *,
    slug: str,
    nombre: str,
    correo_admin: str,
    password_admin: str,
    plan_codigo: str = "gratis",
) -> Tienda:
    """db: sesión de la plataforma (sin tienda). Hace commit al final."""
    if db.info.get(CLAVE_TIENDA) is not None:
        raise RuntimeError("crear_tienda necesita una sesión de la plataforma, no la de una tienda")
    slug = validar_slug(slug)
    if db.scalars(select(Tienda).where(Tienda.slug == slug)).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ya existe una tienda con esa dirección")
    plan = db.scalars(select(Plan).where(Plan.codigo == plan_codigo, Plan.estado.is_(True))).first()
    if not plan:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"No existe el plan '{plan_codigo}'")
    plantilla = db.scalars(select(Tienda).where(Tienda.slug == settings.tienda_por_defecto)).first()

    ahora = datetime.now(timezone.utc)
    tienda = Tienda(slug=slug, nombre=nombre.strip(), estado="activa", correo_contacto=correo_admin, creado_en=ahora)
    db.add(tienda)
    db.flush()
    db.add(Suscripcion(tienda_id=tienda.id, plan_id=plan.id, estado="activa", actualizado_en=ahora))

    roles_nuevos: dict[str, Rol] = {}
    for nombre_rol in ROLES_BASE:
        base = (
            db.scalars(select(Rol).where(Rol.tienda_id == plantilla.id, Rol.nombre == nombre_rol)).first()
            if plantilla else None
        )
        rol = Rol(tienda_id=tienda.id, nombre=nombre_rol, descripcion=base.descripcion if base else None, estado=True)
        db.add(rol)
        db.flush()
        roles_nuevos[nombre_rol] = rol
        if base:
            for rp in db.scalars(select(RolPermiso).where(RolPermiso.rol_id == base.id)).all():
                db.add(RolPermiso(tienda_id=tienda.id, rol_id=rol.id, permiso_id=rp.permiso_id))

    admin = Usuario(
        tienda_id=tienda.id,
        correo=correo_admin.strip().lower(),
        password_hash=get_password_hash(password_admin),
        estado=True,
        creado_en=ahora,
    )
    db.add(admin)
    db.flush()
    db.add(UsuarioRol(tienda_id=tienda.id, usuario_id=admin.id, rol_id=roles_nuevos["Administrador"].id))
    db.commit()
    db.refresh(tienda)
    return tienda
