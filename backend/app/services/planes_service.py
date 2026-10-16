"""Planes del SaaS: qué funciones incluye y cuántos recursos permite el plan de cada tienda.

Se responde 402 (Payment Required) cuando algo no está en el plan: la web y la app lo usan para
ofrecer mejorar el plan en vez de mostrar un error genérico."""
from typing import Callable

from fastapi import Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.tenancy import CLAVE_TIENDA
from app.models.catalogo import Prenda
from app.models.sucursal import Personal, Sucursal
from app.models.tienda import Plan, Suscripcion

FUNCIONES = {"ia": "el asistente con IA", "vestidor_ar": "el vestidor virtual", "pago_qr": "el pago con QR"}
# recurso -> (modelo a contar, columna de límite en Plan, nombre para el mensaje)
CUPOS = {
    "sucursales": (Sucursal, "max_sucursales", "sucursales"),
    "prendas": (Prenda, "max_prendas", "prendas"),
    "personal": (Personal, "max_personal", "empleados"),
}


def plan_de_la_tienda(db: Session) -> Plan:
    """El plan vigente; una suscripción vencida o cancelada vuelve al plan Gratis."""
    tienda_id = db.info.get(CLAVE_TIENDA)
    suscripcion = db.scalars(select(Suscripcion).where(Suscripcion.tienda_id == tienda_id)).first()
    if suscripcion and suscripcion.estado == "activa":
        return db.get(Plan, suscripcion.plan_id)
    return db.scalars(select(Plan).where(Plan.codigo == "gratis")).one()


def _usados(db: Session, recurso: str) -> int:
    # La consulta del ORM ya cuenta solo lo de esta tienda; ocupa cupo lo que está activo
    modelo = CUPOS[recurso][0]
    return db.scalar(select(func.count()).select_from(modelo).where(modelo.estado.is_(True))) or 0


def uso_de_la_tienda(db: Session) -> dict[str, int]:
    return {recurso: _usados(db, recurso) for recurso in CUPOS}


def exigir_cupo(db: Session, recurso: str) -> None:
    """Llamar antes de crear un recurso que el plan limita."""
    _, columna, nombre = CUPOS[recurso]
    plan = plan_de_la_tienda(db)
    maximo = getattr(plan, columna)
    if maximo is not None and _usados(db, recurso) >= maximo:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Tu plan {plan.nombre} permite hasta {maximo} {nombre}. Mejorá tu plan para agregar más.",
        )


def exigir_funcion(funcion: str) -> Callable:
    """Dependencia para endpoints de funciones que no están en todos los planes."""
    if funcion not in FUNCIONES:
        raise ValueError(f"Función de plan desconocida: {funcion}")

    def verificar(db: Session = Depends(get_db)) -> None:
        plan = plan_de_la_tienda(db)
        if not getattr(plan, funcion):
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=f"Tu plan {plan.nombre} no incluye {FUNCIONES[funcion]}. Mejorá tu plan para usarlo.",
            )

    return verificar
