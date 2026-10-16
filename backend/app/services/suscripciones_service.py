"""Cobro de la suscripción mensual de cada tienda con Stripe Billing.

Flujo: el administrador elige un plan -> se crea un Checkout de Stripe en modo suscripción (el
precio va en línea con price_data: no hace falta crear productos en Stripe) -> Stripe devuelve a
la web con el session_id -> el backend lo verifica contra Stripe y aplica el plan. Las
renovaciones, impagos y cancelaciones llegan después por el webhook."""
from datetime import datetime, timezone
from typing import Optional

import stripe
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.tenancy import olvidar_tienda, url_web
from app.models.tienda import Plan, Suscripcion, Tienda

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


def _plan(db: Session, codigo: str) -> Plan:
    plan = db.scalars(select(Plan).where(Plan.codigo == codigo, Plan.estado.is_(True))).first()
    if not plan:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"No existe el plan '{codigo}'")
    return plan


def _suscripcion(db: Session, tienda_id: int) -> Suscripcion:
    return db.scalars(select(Suscripcion).where(Suscripcion.tienda_id == tienda_id)).one()


def _fin_de_periodo(suscripcion_stripe) -> Optional[datetime]:
    # Según la versión de la API de Stripe está en la suscripción o en su primer ítem
    fin = suscripcion_stripe.get("current_period_end")
    if fin is None:
        items = (suscripcion_stripe.get("items") or {}).get("data") or []
        fin = items[0].get("current_period_end") if items else None
    return datetime.fromtimestamp(fin, tz=timezone.utc) if fin else None


def aplicar_plan(db: Session, suscripcion: Suscripcion, plan: Plan, **cambios) -> None:
    suscripcion.plan_id = plan.id
    suscripcion.estado = cambios.pop("estado", "activa")
    for campo, valor in cambios.items():
        setattr(suscripcion, campo, valor)
    suscripcion.actualizado_en = datetime.now(timezone.utc)


def iniciar_cambio_de_plan(db: Session, tienda: Tienda, plan_codigo: str) -> Optional[str]:
    """Devuelve la URL de Stripe Checkout, o None si el cambio no requiere pago (plan Gratis)."""
    plan = _plan(db, plan_codigo)
    suscripcion = _suscripcion(db, tienda.id)

    if float(plan.precio_mensual) == 0:
        if suscripcion.stripe_subscription_id:
            try:
                stripe.Subscription.cancel(suscripcion.stripe_subscription_id)
            except stripe.error.StripeError as exc:
                raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Stripe: {exc.user_message or exc}")
        aplicar_plan(db, suscripcion, plan, stripe_subscription_id=None, periodo_fin=None)
        db.commit()
        return None

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
            success_url=url_web(tienda.slug, "/admin?suscripcion=ok&session_id={CHECKOUT_SESSION_ID}"),
            cancel_url=url_web(tienda.slug, "/admin?suscripcion=cancelada"),
        )
    except stripe.error.StripeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Stripe: {exc.user_message or exc}")
    return sesion.url


def confirmar_checkout(db: Session, tienda: Tienda, session_id: str) -> None:
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

    suscripcion_stripe = sesion.get("subscription") or {}
    aplicar_plan(
        db,
        _suscripcion(db, tienda.id),
        _plan(db, metadata["plan_codigo"]),
        estado=ESTADOS_STRIPE.get(suscripcion_stripe.get("status", "active"), "activa"),
        stripe_customer_id=sesion.get("customer"),
        stripe_subscription_id=suscripcion_stripe.get("id"),
        periodo_fin=_fin_de_periodo(suscripcion_stripe),
    )
    db.commit()


def aplicar_evento_stripe(db: Session, evento: dict) -> bool:
    """Webhook (sesión de la plataforma). Devuelve True si el evento cambió alguna suscripción."""
    if evento.get("type") not in ("customer.subscription.updated", "customer.subscription.deleted"):
        return False
    datos = evento["data"]["object"]
    suscripcion = db.scalars(select(Suscripcion).where(Suscripcion.stripe_subscription_id == datos.get("id"))).first()
    if not suscripcion:
        return False

    estado = "cancelada" if evento["type"] == "customer.subscription.deleted" else ESTADOS_STRIPE.get(datos.get("status"), "vencida")
    plan = db.get(Plan, suscripcion.plan_id)
    plan_nuevo = (datos.get("metadata") or {}).get("plan_codigo")
    if plan_nuevo:
        plan = _plan(db, plan_nuevo)
    aplicar_plan(db, suscripcion, plan, estado=estado, periodo_fin=_fin_de_periodo(datos))
    db.commit()
    tienda = db.get(Tienda, suscripcion.tienda_id)
    if tienda:
        olvidar_tienda(tienda.slug)
    return True
