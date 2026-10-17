"""Suscripción de cada tienda a un plan: alta, cambio de plan, renovación y estado, con su
historial (movimiento_suscripcion).

El cobro es simulado por defecto (el enunciado no exige cobro real): cambiar de plan o renovar se
aplica en el acto y queda registrado como el pago simulado del período. Con
COBRO_SUSCRIPCIONES=stripe, el cambio a un plan pago pasa por Stripe Checkout en modo
suscripción y las renovaciones, impagos y cancelaciones llegan después por el webhook.

Estas funciones no hacen commit: lo hace el endpoint, junto con olvidar_tienda()."""
import calendar
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

import stripe
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.tenancy import url_web
from app.models.tienda import MovimientoSuscripcion, Plan, Suscripcion, Tienda
from app.services.planes_service import excesos_para

stripe.api_key = settings.stripe_secret_key

# Estados de Stripe -> estado de la suscripción en la plataforma
ESTADOS_STRIPE = {
    "active": "activa",
    "trialing": "activa",
    "past_due": "vencida",
    "unpaid": "vencida",
    "incomplete_expired": "cancelada",
    "canceled": "cancelada",
}


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


def sumar_meses(fecha: datetime, meses: int) -> datetime:
    """El mismo día, `meses` después (o el último día del mes si es más corto: 31/01 -> 28/02)."""
    total = fecha.month - 1 + meses
    anio, mes = fecha.year + total // 12, total % 12 + 1
    return fecha.replace(year=anio, month=mes, day=min(fecha.day, calendar.monthrange(anio, mes)[1]))


def buscar_plan(db: Session, codigo: str) -> Plan:
    plan = db.scalars(select(Plan).where(Plan.codigo == codigo, Plan.estado.is_(True))).first()
    if not plan:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"No existe el plan '{codigo}'")
    return plan


def suscripcion_de(db: Session, tienda_id: int) -> Suscripcion:
    return db.scalars(select(Suscripcion).where(Suscripcion.tienda_id == tienda_id)).one()


def registrar_movimiento(
    db: Session,
    tienda_id: int,
    tipo: str,
    plan: Plan,
    *,
    origen: str,
    monto: Decimal | int = 0,
    detalle: Optional[str] = None,
    usuario_id: Optional[int] = None,
) -> None:
    db.add(MovimientoSuscripcion(
        tienda_id=tienda_id, fecha=_ahora(), tipo=tipo, plan_id=plan.id, monto=monto,
        origen=origen, detalle=detalle, usuario_id=usuario_id,
    ))


def nueva_suscripcion(db: Session, tienda_id: int, plan: Plan, *, origen: str, usuario_id: Optional[int] = None) -> Suscripcion:
    """Alta de una tienda: queda contratado (pagado) el primer mes del plan elegido."""
    inicio = _ahora()
    suscripcion = Suscripcion(
        tienda_id=tienda_id, plan_id=plan.id, estado="activa",
        fecha_inicio=inicio, fecha_vencimiento=sumar_meses(inicio, 1), actualizado_en=inicio,
    )
    db.add(suscripcion)
    registrar_movimiento(
        db, tienda_id, "alta", plan, origen=origen, monto=plan.precio_mensual, usuario_id=usuario_id,
        detalle=f"Alta con el plan {plan.nombre}",
    )
    return suscripcion


def _validar_cambio(db: Session, suscripcion: Suscripcion, plan: Plan) -> None:
    if plan.id == suscripcion.plan_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"La tienda ya tiene el plan {plan.nombre}")
    excesos = excesos_para(db, plan, suscripcion.tienda_id)
    if excesos:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"No se puede pasar al plan {plan.nombre}: hay {'; '.join(excesos)}. Desactivá lo que sobra y volvé a intentar.",
        )


def cambiar_plan(
    db: Session,
    tienda_id: int,
    plan_codigo: str,
    *,
    origen: str,
    usuario_id: Optional[int] = None,
    contratar_periodo: bool = True,
) -> Suscripcion:
    """Pasa la tienda a otro plan. Con contratar_periodo (cambio pedido por la tienda) empieza un
    período nuevo de un mes pagado con el precio del plan nuevo; sin él (asignación de la
    plataforma) se conservan las fechas y no hay cobro."""
    plan = buscar_plan(db, plan_codigo)
    suscripcion = suscripcion_de(db, tienda_id)
    _validar_cambio(db, suscripcion, plan)
    anterior = db.get(Plan, suscripcion.plan_id)

    suscripcion.plan_id = plan.id
    suscripcion.estado = "activa"
    suscripcion.actualizado_en = _ahora()
    monto: Decimal | int = 0
    if contratar_periodo:
        suscripcion.fecha_inicio = suscripcion.actualizado_en
        suscripcion.fecha_vencimiento = sumar_meses(suscripcion.fecha_inicio, 1)
        monto = plan.precio_mensual
    registrar_movimiento(
        db, tienda_id, "cambio_plan", plan, origen=origen, monto=monto, usuario_id=usuario_id,
        detalle=f"De {anterior.nombre} a {plan.nombre}",
    )
    return suscripcion


def renovar(db: Session, tienda_id: int, meses: int, *, origen: str, usuario_id: Optional[int] = None) -> Suscripcion:
    """Paga `meses` más del plan actual. Si todavía no venció, se suman al vencimiento (no se
    pierden los días que quedaban); si ya venció, se cuentan desde hoy."""
    suscripcion = suscripcion_de(db, tienda_id)
    plan = db.get(Plan, suscripcion.plan_id)
    ahora = _ahora()
    desde = max(ahora, suscripcion.fecha_vencimiento) if suscripcion.fecha_vencimiento else ahora
    suscripcion.fecha_vencimiento = sumar_meses(desde, meses)
    suscripcion.estado = "activa"
    suscripcion.actualizado_en = ahora
    registrar_movimiento(
        db, tienda_id, "renovacion", plan, origen=origen, monto=plan.precio_mensual * meses, usuario_id=usuario_id,
        detalle=f"{meses} {'mes' if meses == 1 else 'meses'}: vence el {suscripcion.fecha_vencimiento:%d/%m/%Y}",
    )
    return suscripcion


def solicitar_cambio_de_plan(db: Session, tienda: Tienda, plan_codigo: str, usuario_id: int) -> Optional[str]:
    """Cambio de plan pedido por el administrador de la tienda. Devuelve la URL de Stripe
    Checkout si hay que pagar con Stripe, o None si el cambio ya quedó aplicado (cobro simulado)."""
    plan = buscar_plan(db, plan_codigo)
    if settings.cobro_suscripciones != "stripe" or float(plan.precio_mensual) == 0:
        cambiar_plan(db, tienda.id, plan_codigo, origen="simulado", usuario_id=usuario_id)
        return None

    suscripcion = suscripcion_de(db, tienda.id)
    _validar_cambio(db, suscripcion, plan)
    if not settings.stripe_secret_key:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Los pagos con Stripe no están configurados")
    metadata = {"tienda_id": str(tienda.id), "plan_codigo": plan.codigo}
    try:
        sesion = stripe.checkout.Session.create(
            mode="subscription",
            line_items=[{
                "quantity": 1,
                "price_data": {
                    "currency": plan.moneda.lower(),
                    "unit_amount": int(round(float(plan.precio_mensual) * 100)),
                    "recurring": {"interval": "month"},
                    "product_data": {"name": f"Plan {plan.nombre} - {tienda.nombre}"},
                },
            }],
            customer=suscripcion.stripe_customer_id or None,
            customer_email=None if suscripcion.stripe_customer_id else tienda.correo_contacto,
            client_reference_id=str(tienda.id),
            metadata=metadata,
            subscription_data={"metadata": metadata},
            success_url=url_web(tienda.slug, "/admin/plan?suscripcion=ok&session_id={CHECKOUT_SESSION_ID}"),
            cancel_url=url_web(tienda.slug, "/admin/plan?suscripcion=cancelada"),
        )
    except stripe.error.StripeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Stripe: {exc.user_message or exc}")
    return sesion.url


def _fin_de_periodo(suscripcion_stripe) -> Optional[datetime]:
    # Según la versión de la API de Stripe está en la suscripción o en su primer ítem
    fin = suscripcion_stripe.get("current_period_end")
    if fin is None:
        items = (suscripcion_stripe.get("items") or {}).get("data") or []
        fin = items[0].get("current_period_end") if items else None
    return datetime.fromtimestamp(fin, tz=timezone.utc) if fin else None


def confirmar_checkout(db: Session, tienda: Tienda, session_id: str, usuario_id: Optional[int] = None) -> None:
    """Se llama al volver de Stripe. No se le cree a la web: se consulta la sesión en Stripe."""
    try:
        sesion = stripe.checkout.Session.retrieve(session_id, expand=["subscription"])
    except stripe.error.StripeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Stripe: {exc.user_message or exc}")
    metadata = sesion.get("metadata") or {}
    if metadata.get("tienda_id") != str(tienda.id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ese pago no corresponde a esta tienda")
    if sesion.get("status") != "complete":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El pago de la suscripción no se completó")

    plan = buscar_plan(db, metadata["plan_codigo"])
    suscripcion_stripe = sesion.get("subscription") or {}
    suscripcion = suscripcion_de(db, tienda.id)
    suscripcion.plan_id = plan.id
    suscripcion.estado = ESTADOS_STRIPE.get(suscripcion_stripe.get("status", "active"), "activa")
    suscripcion.stripe_customer_id = sesion.get("customer")
    suscripcion.stripe_subscription_id = suscripcion_stripe.get("id")
    suscripcion.fecha_inicio = suscripcion.actualizado_en = _ahora()
    suscripcion.fecha_vencimiento = _fin_de_periodo(suscripcion_stripe)
    registrar_movimiento(
        db, tienda.id, "cambio_plan", plan, origen="stripe", monto=plan.precio_mensual, usuario_id=usuario_id,
        detalle=f"Pago con Stripe del plan {plan.nombre}",
    )


def aplicar_evento_stripe(db: Session, evento: dict) -> Optional[Tienda]:
    """Webhook (sesión de la plataforma). Devuelve la tienda cuya suscripción cambió, o None."""
    if evento.get("type") not in ("customer.subscription.updated", "customer.subscription.deleted"):
        return None
    datos = evento["data"]["object"]
    suscripcion = db.scalars(select(Suscripcion).where(Suscripcion.stripe_subscription_id == datos.get("id"))).first()
    if not suscripcion:
        return None

    plan = db.get(Plan, suscripcion.plan_id)
    plan_nuevo = (datos.get("metadata") or {}).get("plan_codigo")
    if plan_nuevo:
        plan = buscar_plan(db, plan_nuevo)
    fin = _fin_de_periodo(datos)
    if evento["type"] == "customer.subscription.deleted":
        tipo, estado = "cancelacion", "cancelada"
    else:
        estado = ESTADOS_STRIPE.get(datos.get("status"), "vencida")
        renovo = estado == "activa" and fin and (not suscripcion.fecha_vencimiento or fin > suscripcion.fecha_vencimiento)
        tipo = "renovacion" if renovo else "ajuste"

    suscripcion.plan_id = plan.id
    suscripcion.estado = estado
    suscripcion.fecha_vencimiento = fin or suscripcion.fecha_vencimiento
    suscripcion.actualizado_en = _ahora()
    registrar_movimiento(
        db, suscripcion.tienda_id, tipo, plan, origen="stripe",
        monto=plan.precio_mensual if tipo == "renovacion" else 0, detalle=evento["type"],
    )
    return db.get(Tienda, suscripcion.tienda_id)
