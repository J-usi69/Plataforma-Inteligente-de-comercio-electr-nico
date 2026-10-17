"""Planes del SaaS: qué funciones incluye y cuántos recursos permite el plan de cada tienda, y
qué pasa cuando la suscripción vence (la tienda queda en modo consulta).

Se responde 402 (Payment Required) cuando algo no está en el plan o la suscripción no está
vigente: la web y la app lo usan para ofrecer mejorar o renovar el plan en vez de mostrar un
error genérico."""
from typing import Callable, Optional

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.tenancy import CLAVE_TIENDA, tienda_de_la_peticion
from app.models.catalogo import Prenda
from app.models.sucursal import Personal, Sucursal
from app.models.tienda import Plan, Suscripcion

# Funciones que un plan puede incluir o no: columna booleana de Plan -> nombre para el mensaje.
# Productos, ventas y reservas no figuran: están en todos los planes.
FUNCIONES = {
    "operacion_offline": "la operación sin conexión",
    "reportes": "los reportes",
    "reportes_ia": "los reportes generados con IA",
    "asistente_ia": "el asistente con IA",
    "vestidor_ar": "el vestidor virtual",
    "pago_qr": "el pago con QR",
}
# recurso -> (modelo a contar, columna de límite en Plan, nombre para el mensaje)
CUPOS = {
    "sucursales": (Sucursal, "max_sucursales", "sucursales"),
    "prendas": (Prenda, "max_prendas", "prendas"),
    "personal": (Personal, "max_personal", "empleados"),
}
METODOS_DE_LECTURA = {"GET", "HEAD", "OPTIONS"}
# Avisos de pago de ventas ya registradas: se aceptan aunque la suscripción haya vencido después
RUTAS_SIN_SUSCRIPCION = ("/libelula/callback",)


def _tienda_id(db: Session, tienda_id: Optional[int]) -> int:
    return tienda_id if tienda_id is not None else db.info[CLAVE_TIENDA]


def plan_de_la_tienda(db: Session, tienda_id: Optional[int] = None) -> Plan:
    tienda_id = _tienda_id(db, tienda_id)
    suscripcion = db.scalars(select(Suscripcion).where(Suscripcion.tienda_id == tienda_id)).first()
    if suscripcion:
        return db.get(Plan, suscripcion.plan_id)
    # Sin suscripción (no debería pasar: el alta de la tienda la crea): el plan más básico
    return db.scalars(select(Plan).where(Plan.estado.is_(True)).order_by(Plan.orden)).first()


def usados(db: Session, recurso: str, tienda_id: Optional[int] = None) -> int:
    """Ocupa cupo lo que está activo. El filtro por tienda es explícito porque en la sesión de la
    plataforma (superadmin) el ORM no filtra solo."""
    modelo = CUPOS[recurso][0]
    return db.scalar(
        select(func.count()).select_from(modelo)
        .where(modelo.tienda_id == _tienda_id(db, tienda_id), modelo.estado.is_(True))
    ) or 0


def uso_de_la_tienda(db: Session, tienda_id: Optional[int] = None) -> dict[str, int]:
    return {recurso: usados(db, recurso, tienda_id) for recurso in CUPOS}


def excesos_para(db: Session, plan: Plan, tienda_id: Optional[int] = None) -> list[str]:
    """Lo que la tienda tiene activo por encima de los límites de un plan. Si hay algo, no puede
    pasar a ese plan hasta dar de baja lo que sobra."""
    excesos = []
    for recurso, (_, columna, nombre) in CUPOS.items():
        maximo = getattr(plan, columna)
        en_uso = usados(db, recurso, tienda_id)
        if maximo is not None and en_uso > maximo:
            excesos.append(f"{en_uso} {nombre} activas y el plan {plan.nombre} permite {maximo}")
    return excesos


def exigir_cupo(db: Session, recurso: str) -> None:
    """Llamar antes de crear un recurso que el plan limita."""
    _, columna, nombre = CUPOS[recurso]
    plan = plan_de_la_tienda(db)
    maximo = getattr(plan, columna)
    if maximo is not None and usados(db, recurso) >= maximo:
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


def exigir_suscripcion_vigente(request: Request) -> None:
    """Dependencia de los routers de operaciones: con la suscripción vencida o cancelada la tienda
    queda en modo consulta (se puede entrar y ver todo, pero no registrar nada) hasta renovar."""
    if request.method in METODOS_DE_LECTURA or any(r in request.url.path for r in RUTAS_SIN_SUSCRIPCION):
        return
    tienda = tienda_de_la_peticion(request)
    if tienda.suscripcion_vigente:
        return
    if tienda.suscripcion_estado == "cancelada":
        motivo = "está cancelada"
    elif tienda.suscripcion_vence:
        motivo = f"venció el {tienda.suscripcion_vence:%d/%m/%Y}"
    else:
        motivo = "venció"
    raise HTTPException(
        status_code=status.HTTP_402_PAYMENT_REQUIRED,
        detail=f"La suscripción de {tienda.nombre} {motivo}: la tienda queda en modo consulta hasta que se renueve el plan.",
    )
