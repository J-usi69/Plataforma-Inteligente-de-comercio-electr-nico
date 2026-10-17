"""La tienda del pedido: su marca (para que la web y la app se vistan con ella) y su suscripción:
plan, uso de los límites, cambio de plan, renovación e historial."""
import math
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_client_ip, registrar_bitacora, require_roles
from app.core.config import settings
from app.db.session import get_db
from app.db.tenancy import CLAVE_TIENDA, olvidar_tienda
from app.models.seguridad import Usuario
from app.models.tienda import MovimientoSuscripcion, Plan, Suscripcion, Tienda
from app.schemas.tienda import (
    CambioPlanIn,
    CambioPlanOut,
    ConfirmarSuscripcionIn,
    FuncionesOut,
    MovimientoOut,
    PlanOut,
    RenovarIn,
    SuscripcionOut,
    TiendaPublicaOut,
    TiendaUpdate,
    UsoPlanOut,
)
from app.services import suscripciones_service
from app.services.planes_service import plan_de_la_tienda, uso_de_la_tienda

router = APIRouter()
solo_admin = require_roles(["Administrador"])


def _tienda(db: Session) -> Tienda:
    return db.get(Tienda, db.info[CLAVE_TIENDA])


def suscripcion_out(suscripcion: Suscripcion) -> SuscripcionOut:
    vence = suscripcion.fecha_vencimiento
    dias = None
    if vence:
        dias = max(0, math.ceil((vence - datetime.now(timezone.utc)).total_seconds() / 86400))
    return SuscripcionOut(
        estado=suscripcion.estado_actual,
        fecha_inicio=suscripcion.fecha_inicio,
        fecha_vencimiento=vence,
        dias_restantes=dias,
        cobro=settings.cobro_suscripciones,
    )


def _publica(db: Session) -> TiendaPublicaOut:
    tienda = _tienda(db)
    plan = plan_de_la_tienda(db)
    suscripcion = suscripciones_service.suscripcion_de(db, tienda.id)
    return TiendaPublicaOut(
        slug=tienda.slug,
        nombre=tienda.nombre,
        logo_url=tienda.logo_url,
        color_primario=tienda.color_primario,
        color_acento=tienda.color_acento,
        plan=plan.codigo,
        plan_nombre=plan.nombre,
        funciones=FuncionesOut.model_validate(plan),
        suscripcion_vigente=suscripcion.estado_actual == "activa",
    )


def _uso(db: Session) -> UsoPlanOut:
    tienda_id = db.info[CLAVE_TIENDA]
    planes = db.scalars(select(Plan).where(Plan.estado.is_(True)).order_by(Plan.orden)).all()
    movimientos = db.scalars(
        select(MovimientoSuscripcion)
        .where(MovimientoSuscripcion.tienda_id == tienda_id)
        .order_by(MovimientoSuscripcion.fecha.desc(), MovimientoSuscripcion.id.desc())
        .limit(20)
    ).all()
    return UsoPlanOut(
        plan=PlanOut.model_validate(plan_de_la_tienda(db)),
        suscripcion=suscripcion_out(suscripciones_service.suscripcion_de(db, tienda_id)),
        uso=uso_de_la_tienda(db),
        planes_disponibles=[PlanOut.model_validate(p) for p in planes],
        movimientos=[
            MovimientoOut(fecha=m.fecha, tipo=m.tipo, plan=m.plan.nombre, monto=float(m.monto), origen=m.origen, detalle=m.detalle)
            for m in movimientos
        ],
    )


@router.get("", response_model=TiendaPublicaOut)
def ver_tienda(db: Session = Depends(get_db)):
    """Marca, funciones del plan y si la suscripción está vigente (público: la web lo pide antes
    de que haya sesión)."""
    return _publica(db)


@router.put("", response_model=TiendaPublicaOut)
def actualizar_tienda(
    datos: TiendaUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(solo_admin),
):
    """El administrador cambia el nombre, el logo y los colores de su tienda."""
    tienda = _tienda(db)
    for campo, valor in datos.model_dump(exclude_unset=True).items():
        setattr(tienda, campo, valor)
    db.commit()
    olvidar_tienda(tienda.slug)
    registrar_bitacora(db, current_user.id, "Actualización de la marca de la tienda", get_client_ip(request))
    return _publica(db)


@router.get("/plan", response_model=UsoPlanOut)
def ver_plan(db: Session = Depends(get_db), _: Usuario = Depends(solo_admin)):
    """Plan y estado de la suscripción (inicio, vencimiento), cuánto se usa de cada límite, los
    planes a los que se puede pasar y el historial de la suscripción."""
    return _uso(db)


@router.post("/plan", response_model=CambioPlanOut)
def cambiar_plan(
    datos: CambioPlanIn,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(solo_admin),
):
    """Cambio de plan. Con cobro simulado se aplica en el acto (pago simulado del primer mes del
    plan nuevo); con Stripe devuelve la URL de Checkout. No se puede bajar a un plan cuyos límites
    la tienda ya supera (409)."""
    tienda = _tienda(db)
    url = suscripciones_service.solicitar_cambio_de_plan(db, tienda, datos.plan_codigo, current_user.id)
    # La bitácora hace el commit: el cambio de plan y su registro quedan juntos
    registrar_bitacora(db, current_user.id, f"Cambio de plan: {datos.plan_codigo}", get_client_ip(request))
    if url:
        return CambioPlanOut(url=url, estado=None)
    olvidar_tienda(tienda.slug)
    return CambioPlanOut(url=None, estado=_uso(db))


@router.post("/plan/renovar", response_model=UsoPlanOut)
def renovar_plan(
    datos: RenovarIn,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(solo_admin),
):
    """Renovación simulada: paga `meses` más del plan actual. También reactiva una suscripción
    vencida (la tienda sale del modo consulta)."""
    if settings.cobro_suscripciones == "stripe":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Con Stripe la suscripción se renueva sola cada mes")
    tienda = _tienda(db)
    suscripciones_service.renovar(db, tienda.id, datos.meses, origen="simulado", usuario_id=current_user.id)
    registrar_bitacora(db, current_user.id, f"Renovación del plan por {datos.meses} mes(es)", get_client_ip(request))
    olvidar_tienda(tienda.slug)
    return _uso(db)


@router.post("/plan/confirmar", response_model=UsoPlanOut)
def confirmar_plan(
    datos: ConfirmarSuscripcionIn,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(solo_admin),
):
    """Al volver de Stripe Checkout: verifica el pago con Stripe y aplica el plan."""
    tienda = _tienda(db)
    suscripciones_service.confirmar_checkout(db, tienda, datos.session_id, current_user.id)
    registrar_bitacora(db, current_user.id, "Suscripción pagada con Stripe y plan actualizado", get_client_ip(request))
    olvidar_tienda(tienda.slug)
    return _uso(db)
