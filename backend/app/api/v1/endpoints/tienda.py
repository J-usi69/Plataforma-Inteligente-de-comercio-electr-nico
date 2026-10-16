"""La tienda del pedido: su marca (para que la web y la app se vistan con ella), su plan y el
cambio de plan con Stripe."""
from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_client_ip, registrar_bitacora, require_roles
from app.db.session import get_db
from app.db.tenancy import CLAVE_TIENDA, olvidar_tienda
from app.models.seguridad import Usuario
from app.models.tienda import Plan, Suscripcion, Tienda
from app.schemas.tienda import (
    CambioPlanIn,
    CheckoutOut,
    ConfirmarSuscripcionIn,
    FuncionesOut,
    PlanOut,
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


def _publica(db: Session) -> TiendaPublicaOut:
    tienda = _tienda(db)
    plan = plan_de_la_tienda(db)
    return TiendaPublicaOut(
        slug=tienda.slug,
        nombre=tienda.nombre,
        logo_url=tienda.logo_url,
        color_primario=tienda.color_primario,
        color_acento=tienda.color_acento,
        plan=plan.codigo,
        funciones=FuncionesOut(ia=plan.ia, vestidor_ar=plan.vestidor_ar, pago_qr=plan.pago_qr),
    )


def _uso(db: Session) -> UsoPlanOut:
    suscripcion = db.scalars(select(Suscripcion).where(Suscripcion.tienda_id == db.info[CLAVE_TIENDA])).first()
    planes = db.scalars(select(Plan).where(Plan.estado.is_(True)).order_by(Plan.orden)).all()
    return UsoPlanOut(
        plan=PlanOut.model_validate(plan_de_la_tienda(db)),
        estado_suscripcion=suscripcion.estado if suscripcion else "activa",
        periodo_fin=suscripcion.periodo_fin if suscripcion else None,
        uso=uso_de_la_tienda(db),
        planes_disponibles=[PlanOut.model_validate(p) for p in planes],
    )


@router.get("", response_model=TiendaPublicaOut)
def ver_tienda(db: Session = Depends(get_db)):
    """Marca y funciones de la tienda (público: la web lo pide antes de que haya sesión)."""
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
    """Plan vigente, cuánto se está usando de cada límite y los planes a los que se puede pasar."""
    return _uso(db)


@router.post("/plan", response_model=CheckoutOut)
def cambiar_plan(
    datos: CambioPlanIn,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(solo_admin),
):
    """Planes pagos: devuelve la URL de Stripe Checkout. Plan Gratis: se aplica en el acto."""
    url = suscripciones_service.iniciar_cambio_de_plan(db, _tienda(db), datos.plan_codigo)
    registrar_bitacora(db, current_user.id, f"Cambio de plan solicitado: {datos.plan_codigo}", get_client_ip(request))
    return CheckoutOut(url=url, plan=datos.plan_codigo)


@router.post("/plan/confirmar", response_model=UsoPlanOut)
def confirmar_plan(
    datos: ConfirmarSuscripcionIn,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(solo_admin),
):
    """Al volver de Stripe Checkout: verifica el pago con Stripe y aplica el plan."""
    suscripciones_service.confirmar_checkout(db, _tienda(db), datos.session_id)
    registrar_bitacora(db, current_user.id, "Suscripción pagada y plan actualizado", get_client_ip(request))
    return _uso(db)
