"""La plataforma SaaS: alta de tiendas (público), planes (público), webhook de Stripe y la
administración de todas las tiendas por el superadmin. Ninguna de estas rutas es de una tienda:
usan la sesión de la plataforma."""
from typing import List, Optional

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_client_ip
from app.core.config import settings
from app.core.limite_intentos import LimiteIntentos
from app.core.security import create_access_token, decode_access_token, verify_password
from app.db.session import get_db_plataforma
from app.db.tenancy import olvidar_tienda
from app.models.catalogo import Prenda
from app.models.seguridad import Usuario
from app.models.tienda import Plan, Suscripcion, Tienda
from app.models.venta import Venta
from app.schemas.tienda import (
    LoginPlataformaIn,
    PlanOut,
    RegistroTiendaIn,
    RegistroTiendaOut,
    TiendaAdminOut,
    TiendaAdminUpdate,
)
from app.services import suscripciones_service
from app.services.tiendas_service import crear_tienda, validar_slug

router = APIRouter()
oauth2 = OAuth2PasswordBearer(tokenUrl="/api/v1/plataforma/login", auto_error=False)

# Alta pública de tiendas: tope por IP para que nadie llene la base de tiendas basura
altas_por_ip = LimiteIntentos(maximo=5, ventana_segundos=60 * 60)
intentos_superadmin = LimiteIntentos(maximo=5, ventana_segundos=15 * 60)


def require_superadmin(token: Optional[str] = Depends(oauth2), db: Session = Depends(get_db_plataforma)) -> Usuario:
    payload = decode_access_token(token) if token else None
    if not payload or not payload.get("plataforma"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Requiere sesión de la plataforma")
    usuario = db.get(Usuario, int(payload["sub"]))
    if not usuario or usuario.tienda_id is not None or not usuario.es_superadmin or not usuario.estado:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo para administradores de la plataforma")
    return usuario


@router.get("/planes", response_model=List[PlanOut])
def listar_planes(db: Session = Depends(get_db_plataforma)):
    """Planes y precios (página de precios del SaaS)."""
    return db.scalars(select(Plan).where(Plan.estado.is_(True)).order_by(Plan.orden)).all()


@router.get("/disponible/{slug}")
def direccion_disponible(slug: str, db: Session = Depends(get_db_plataforma)):
    """Para el formulario de alta: avisa si la dirección de la tienda está libre."""
    try:
        slug = validar_slug(slug)
    except HTTPException as exc:
        return {"disponible": False, "motivo": exc.detail}
    tomada = db.scalars(select(Tienda.id).where(Tienda.slug == slug)).first() is not None
    return {"disponible": not tomada, "motivo": "Ya existe una tienda con esa dirección" if tomada else None}


@router.post("/registro", response_model=RegistroTiendaOut, status_code=status.HTTP_201_CREATED)
def registrar_tienda(datos: RegistroTiendaIn, request: Request, db: Session = Depends(get_db_plataforma)):
    """Alta de una tienda nueva con el plan Gratis. Devuelve la sesión de su administrador."""
    ip = get_client_ip(request) or "sin-ip"
    if altas_por_ip.segundos_bloqueado(ip):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Demasiadas tiendas creadas desde esta conexión. Probá más tarde.")
    altas_por_ip.registrar_fallo(ip)  # cuenta cada alta, no solo las fallidas

    tienda = crear_tienda(db, slug=datos.slug, nombre=datos.nombre_tienda, correo_admin=datos.correo, password_admin=datos.password)
    admin = db.scalars(select(Usuario).where(Usuario.tienda_id == tienda.id)).one()
    token = create_access_token({"sub": str(admin.id), "tid": tienda.id, "email": admin.correo, "roles": ["Administrador"]})
    return RegistroTiendaOut(slug=tienda.slug, nombre=tienda.nombre, access_token=token)


@router.post("/login")
def login_plataforma(datos: LoginPlataformaIn, request: Request, db: Session = Depends(get_db_plataforma)):
    """Inicio de sesión del superadmin (cuentas sin tienda)."""
    clave = f"{get_client_ip(request)}|{datos.correo.lower()}"
    if intentos_superadmin.segundos_bloqueado(clave):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Demasiados intentos fallidos. Probá más tarde.")
    usuario = db.scalars(select(Usuario).where(Usuario.tienda_id.is_(None), Usuario.correo == datos.correo.lower())).first()
    if not usuario or not usuario.es_superadmin or not usuario.estado or not verify_password(datos.password, usuario.password_hash):
        intentos_superadmin.registrar_fallo(clave)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales incorrectas")
    intentos_superadmin.limpiar(clave)
    return {"access_token": create_access_token({"sub": str(usuario.id), "plataforma": True}), "token_type": "bearer"}


@router.get("/tiendas", response_model=List[TiendaAdminOut])
def listar_tiendas(db: Session = Depends(get_db_plataforma), _: Usuario = Depends(require_superadmin)):
    """Todas las tiendas con su plan y su actividad."""
    def contar(modelo, tienda_id: int) -> int:
        return db.scalar(select(func.count()).select_from(modelo).where(modelo.tienda_id == tienda_id)) or 0

    resultado = []
    for tienda in db.scalars(select(Tienda).order_by(Tienda.creado_en.desc())).all():
        suscripcion = db.scalars(select(Suscripcion).where(Suscripcion.tienda_id == tienda.id)).first()
        plan = db.get(Plan, suscripcion.plan_id) if suscripcion else None
        resultado.append(TiendaAdminOut(
            id=tienda.id, slug=tienda.slug, nombre=tienda.nombre, estado=tienda.estado,
            plan=plan.nombre if plan else "-", estado_suscripcion=suscripcion.estado if suscripcion else "-",
            creado_en=tienda.creado_en, usuarios=contar(Usuario, tienda.id), prendas=contar(Prenda, tienda.id),
            ventas=contar(Venta, tienda.id),
        ))
    return resultado


@router.patch("/tiendas/{tienda_id}", response_model=TiendaAdminOut)
def actualizar_tienda(
    tienda_id: int,
    datos: TiendaAdminUpdate,
    db: Session = Depends(get_db_plataforma),
    superadmin: Usuario = Depends(require_superadmin),
):
    """Suspender o reactivar una tienda, o cambiarle el plan sin pasar por Stripe (cortesías)."""
    tienda = db.get(Tienda, tienda_id)
    if not tienda:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tienda no encontrada")
    if datos.estado:
        tienda.estado = datos.estado
    if datos.plan_codigo:
        suscripcion = db.scalars(select(Suscripcion).where(Suscripcion.tienda_id == tienda.id)).one()
        suscripciones_service.aplicar_plan(db, suscripcion, suscripciones_service._plan(db, datos.plan_codigo))
    db.commit()
    olvidar_tienda(tienda.slug)
    return next(t for t in listar_tiendas(db, superadmin) if t.id == tienda.id)


@router.post("/stripe/webhook")
async def webhook_stripe(request: Request, db: Session = Depends(get_db_plataforma)):
    """Renovaciones, impagos y cancelaciones de suscripciones. Registrar esta URL en Stripe con
    los eventos customer.subscription.updated y customer.subscription.deleted."""
    if not settings.stripe_webhook_secret:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Webhook de Stripe no configurado")
    try:
        evento = stripe.Webhook.construct_event(
            await request.body(), request.headers.get("stripe-signature", ""), settings.stripe_webhook_secret
        )
    except (ValueError, stripe.error.SignatureVerificationError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Firma de Stripe inválida")
    return {"procesado": suscripciones_service.aplicar_evento_stripe(db, evento)}
