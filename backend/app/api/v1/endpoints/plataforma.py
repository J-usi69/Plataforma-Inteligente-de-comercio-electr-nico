"""La plataforma SaaS: alta de tiendas (público), planes (público), webhook de Stripe y la
administración de todas las tiendas y de los planes por el superadmin. Ninguna de estas rutas es
de una tienda: usan la sesión de la plataforma."""
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
from app.models.sucursal import Sucursal
from app.models.tienda import Plan, Suscripcion, Tienda
from app.models.venta import Venta
from app.schemas.tienda import (
    LoginPlataformaIn,
    PlanOut,
    PlanUpdate,
    RegistroTiendaIn,
    RegistroTiendaOut,
    RenovarIn,
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


def _tienda_o_404(db: Session, tienda_id: int) -> Tienda:
    tienda = db.get(Tienda, tienda_id)
    if not tienda:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tienda no encontrada")
    return tienda


def _tienda_admin_out(db: Session, tienda: Tienda) -> TiendaAdminOut:
    def contar(modelo, *condiciones) -> int:
        return db.scalar(select(func.count()).select_from(modelo).where(modelo.tienda_id == tienda.id, *condiciones)) or 0

    suscripcion = db.scalars(select(Suscripcion).where(Suscripcion.tienda_id == tienda.id)).first()
    plan = db.get(Plan, suscripcion.plan_id) if suscripcion else None
    return TiendaAdminOut(
        id=tienda.id, slug=tienda.slug, nombre=tienda.nombre, estado=tienda.estado,
        plan=plan.nombre if plan else "-", plan_codigo=plan.codigo if plan else "-",
        estado_suscripcion=suscripcion.estado_actual if suscripcion else "-",
        fecha_inicio=suscripcion.fecha_inicio if suscripcion else None,
        fecha_vencimiento=suscripcion.fecha_vencimiento if suscripcion else None,
        creado_en=tienda.creado_en,
        sucursales=contar(Sucursal, Sucursal.estado.is_(True)),
        usuarios=contar(Usuario), prendas=contar(Prenda), ventas=contar(Venta),
    )


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
    """Alta de una empresa con el plan elegido (primer mes con pago simulado). Devuelve la sesión
    de su administrador."""
    ip = get_client_ip(request) or "sin-ip"
    if altas_por_ip.segundos_bloqueado(ip):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Demasiadas tiendas creadas desde esta conexión. Probá más tarde.")
    altas_por_ip.registrar_fallo(ip)  # cuenta cada alta, no solo las fallidas

    tienda = crear_tienda(
        db, slug=datos.slug, nombre=datos.nombre_tienda, correo_admin=datos.correo,
        password_admin=datos.password, plan_codigo=datos.plan_codigo,
    )
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
    """Todas las empresas con su plan, su suscripción y su actividad."""
    return [_tienda_admin_out(db, t) for t in db.scalars(select(Tienda).order_by(Tienda.creado_en.desc())).all()]


@router.post("/tiendas", response_model=TiendaAdminOut, status_code=status.HTTP_201_CREATED)
def alta_de_tienda(
    datos: RegistroTiendaIn,
    db: Session = Depends(get_db_plataforma),
    superadmin: Usuario = Depends(require_superadmin),
):
    """El superadmin registra una empresa contratante con su administrador y su plan."""
    tienda = crear_tienda(
        db, slug=datos.slug, nombre=datos.nombre_tienda, correo_admin=datos.correo,
        password_admin=datos.password, plan_codigo=datos.plan_codigo, origen="plataforma", usuario_id=superadmin.id,
    )
    return _tienda_admin_out(db, tienda)


@router.patch("/tiendas/{tienda_id}", response_model=TiendaAdminOut)
def actualizar_tienda(
    tienda_id: int,
    datos: TiendaAdminUpdate,
    db: Session = Depends(get_db_plataforma),
    superadmin: Usuario = Depends(require_superadmin),
):
    """Suspender o reactivar la tienda, asignarle otro plan (sin cobro, conserva las fechas),
    cancelar o reactivar la suscripción y corregir su vencimiento. Todo queda en el historial."""
    tienda = _tienda_o_404(db, tienda_id)
    suscripcion = suscripciones_service.suscripcion_de(db, tienda.id)

    def registrar(tipo: str, detalle: str) -> None:
        suscripciones_service.registrar_movimiento(
            db, tienda.id, tipo, db.get(Plan, suscripcion.plan_id), origen="plataforma", detalle=detalle, usuario_id=superadmin.id,
        )

    if datos.estado and datos.estado != tienda.estado:
        tienda.estado = datos.estado
        registrar("suspension" if datos.estado == "suspendida" else "reactivacion", f"Tienda {datos.estado}")
    if datos.plan_codigo:
        suscripciones_service.cambiar_plan(
            db, tienda.id, datos.plan_codigo, origen="plataforma", usuario_id=superadmin.id, contratar_periodo=False,
        )
    if datos.estado_suscripcion and datos.estado_suscripcion != suscripcion.estado:
        suscripcion.estado = datos.estado_suscripcion
        registrar("cancelacion" if datos.estado_suscripcion == "cancelada" else "reactivacion", f"Suscripción {datos.estado_suscripcion}")
    if datos.fecha_vencimiento:
        suscripcion.fecha_vencimiento = datos.fecha_vencimiento
        registrar("ajuste", f"Vencimiento corregido al {datos.fecha_vencimiento:%d/%m/%Y}")
    db.commit()
    olvidar_tienda(tienda.slug)
    return _tienda_admin_out(db, tienda)


@router.post("/tiendas/{tienda_id}/renovar", response_model=TiendaAdminOut)
def renovar_tienda(
    tienda_id: int,
    datos: RenovarIn,
    db: Session = Depends(get_db_plataforma),
    superadmin: Usuario = Depends(require_superadmin),
):
    """Renovación registrada por la plataforma (por ejemplo, la empresa pagó por transferencia)."""
    tienda = _tienda_o_404(db, tienda_id)
    suscripciones_service.renovar(db, tienda.id, datos.meses, origen="plataforma", usuario_id=superadmin.id)
    db.commit()
    olvidar_tienda(tienda.slug)
    return _tienda_admin_out(db, tienda)


@router.put("/planes/{codigo}", response_model=PlanOut)
def configurar_plan(
    codigo: str,
    datos: PlanUpdate,
    db: Session = Depends(get_db_plataforma),
    _: Usuario = Depends(require_superadmin),
):
    """Límites, precio y funciones de un plan (los valores del enunciado son los iniciales). Rige
    desde ya para todas las tiendas con ese plan; lo que ya tienen creado no se borra."""
    plan = db.scalars(select(Plan).where(Plan.codigo == codigo)).first()
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No existe el plan '{codigo}'")
    for campo, valor in datos.model_dump(exclude_unset=True).items():
        setattr(plan, campo, valor)
    db.commit()
    db.refresh(plan)
    return plan


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
    tienda = suscripciones_service.aplicar_evento_stripe(db, evento)
    if tienda:
        db.commit()
        olvidar_tienda(tienda.slug)
    return {"procesado": tienda is not None}
