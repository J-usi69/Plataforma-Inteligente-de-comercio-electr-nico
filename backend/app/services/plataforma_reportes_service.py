"""Reportes personalizables e indicadores de la plataforma SaaS (superadmin).

A diferencia de los reportes de una empresa, estos miran todas las empresas a la vez: empresas y
suscripciones, ingresos por suscripciones, uso frente a los límites del plan, ventas de cada
empresa, historial de la plataforma y la bitácora de todas las empresas.

Cada reporte es personalizable: el usuario elige qué columnas ver y en qué orden, filtra por
fechas y agrega criterios de selección (columna, operador y valor); el orden se puede hacer por
cualquier columna. Se usan con la sesión de la plataforma, donde el ORM no filtra por tienda:
cada consulta agrupa o filtra por tienda de forma explícita.
"""
from collections import defaultdict
from datetime import date
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.enums import EstadoVenta
from app.models.seguridad import Usuario
from app.models.tienda import MovimientoSuscripcion, Plan, Suscripcion, Tienda
from app.models.venta import Venta
from app.services import bitacora_service
from app.services import reportes_personalizados as motor
from app.services.planes_service import CUPOS, uso_de_la_tienda
from app.services.reportes_personalizados import (  # noqa: F401 (se reexportan para los endpoints y los tests)
    OPERADORES,
    Criterio,
    Definicion,
    Fila,
    Reporte,
    a_html,
    celda_texto,
    en_rango as _en_rango,
    fecha_texto as _fecha,
    hoy as _hoy,
    monto as _monto,
)
from app.services.reportes_service import _inicio_dia

DIAS_POR_VENCER = 15
MESES_EN_EL_GRAFICO = 6
MOVIMIENTOS = {
    "alta": "Alta",
    "cambio_plan": "Cambio de plan",
    "renovacion": "Renovación",
    "suspension": "Suspensión",
    "reactivacion": "Reactivación",
    "cancelacion": "Cancelación",
    "ajuste": "Ajuste",
}
ORIGENES = {"simulado": "Pago simulado", "stripe": "Stripe", "plataforma": "Plataforma"}
MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


# --------------------------------------------------------------------------- utilidades

def _suscripciones(db: Session) -> dict[int, Suscripcion]:
    return {s.tienda_id: s for s in db.scalars(select(Suscripcion)).all()}


def _planes(db: Session) -> dict[int, Plan]:
    return {p.id: p for p in db.scalars(select(Plan)).all()}


def _vigente(tienda: Tienda, suscripcion: Optional[Suscripcion]) -> bool:
    return tienda.estado == "activa" and suscripcion is not None and suscripcion.estado_actual == "activa"


def _dias_restantes(suscripcion: Optional[Suscripcion], hoy: date) -> Optional[int]:
    if not suscripcion or not suscripcion.fecha_vencimiento:
        return None
    return (suscripcion.fecha_vencimiento.date() - hoy).days


# --------------------------------------------------------------------------- datos de cada reporte

def _filas_empresas(db: Session, desde: Optional[date], hasta: Optional[date]) -> list[Fila]:
    hoy = _hoy()
    suscripciones, planes = _suscripciones(db), _planes(db)
    filas = []
    for t in db.scalars(select(Tienda).where(*_en_rango(Tienda.creado_en, desde, hasta))).all():
        s = suscripciones.get(t.id)
        plan = planes.get(s.plan_id) if s else None
        dias = _dias_restantes(s, hoy)
        filas.append({
            "Empresa": t.nombre, "Dirección": f"/t/{t.slug}", "Plan": plan.nombre if plan else "-",
            "Estado": t.estado, "Suscripción": s.estado_actual if s else "-",
            "Alta": _fecha(t.creado_en), "Inicio": _fecha(s.fecha_inicio if s else None),
            "Vence": _fecha(s.fecha_vencimiento if s else None),
            "Días restantes": dias if dias is not None else "Sin vencimiento",
            "Precio mensual (USD)": _monto(plan.precio_mensual) if plan else 0.0,
            "_vigente": _vigente(t, s), "_dias": dias,
        })
    return filas


def _resumen_empresas(filas: list[Fila], periodo: str) -> str:
    vigentes = sum(f["_vigente"] for f in filas)
    por_vencer = sum(f["_vigente"] and f["_dias"] is not None and f["_dias"] <= DIAS_POR_VENCER for f in filas)
    suspendidas = sum(f["Estado"] == "suspendida" for f in filas)
    return (
        f"{len(filas)} empresas (altas {periodo}): {vigentes} con suscripción vigente, {por_vencer} vencen "
        f"en los próximos {DIAS_POR_VENCER} días y {suspendidas} están suspendidas."
    )


def _filas_ingresos(db: Session, desde: Optional[date], hasta: Optional[date]) -> list[Fila]:
    movimientos = db.execute(
        select(MovimientoSuscripcion, Tienda.nombre, Plan.nombre)
        .join(Tienda, Tienda.id == MovimientoSuscripcion.tienda_id)
        .join(Plan, Plan.id == MovimientoSuscripcion.plan_id)
        .where(MovimientoSuscripcion.monto > 0, *_en_rango(MovimientoSuscripcion.fecha, desde, hasta))
    ).all()
    return [
        {
            "Fecha": _fecha(m.fecha), "Empresa": empresa, "Movimiento": MOVIMIENTOS.get(m.tipo, m.tipo),
            "Plan": plan, "Origen": ORIGENES.get(m.origen, m.origen), "Monto (USD)": _monto(m.monto),
            "_orden_fecha": m.fecha,
        }
        for m, empresa, plan in movimientos
    ]


def _resumen_ingresos(filas: list[Fila], periodo: str) -> str:
    por_plan = defaultdict(float)
    for f in filas:
        por_plan[f["Plan"]] += f["Monto (USD)"]
    total = sum(por_plan.values())
    detalle = ", ".join(f"{plan} USD {monto:,.2f}" for plan, monto in sorted(por_plan.items(), key=lambda x: -x[1]))
    return f"Ingresos por suscripciones {periodo}: USD {total:,.2f} en {len(filas)} cobros" + (f" ({detalle})." if detalle else ".")


def _ocupacion(en_uso: int, maximo: Optional[int]) -> tuple[str, Optional[float]]:
    if maximo is None:
        return f"{en_uso} / sin límite", None
    return f"{en_uso} / {maximo}", (en_uso / maximo * 100 if maximo else 100.0)


def _filas_uso(db: Session, desde: Optional[date] = None, hasta: Optional[date] = None) -> list[Fila]:
    suscripciones, planes = _suscripciones(db), _planes(db)
    ventas = dict(db.execute(
        select(Venta.tienda_id, func.count())
        .where(Venta.estado == EstadoVenta.pagada, *_en_rango(Venta.fecha_venta, desde, hasta))
        .group_by(Venta.tienda_id)
    ).all())
    filas = []
    for t in db.scalars(select(Tienda)).all():
        s = suscripciones.get(t.id)
        plan = planes.get(s.plan_id) if s else None
        uso = uso_de_la_tienda(db, t.id)
        fila: Fila = {"Empresa": t.nombre, "Plan": plan.nombre if plan else "-"}
        mayor: tuple[Optional[float], str] = (None, "")
        for recurso, (_, columna, nombre) in CUPOS.items():
            texto, porcentaje = _ocupacion(uso[recurso], getattr(plan, columna) if plan else None)
            fila[nombre.capitalize()] = texto
            if porcentaje is not None and (mayor[0] is None or porcentaje > mayor[0]):
                mayor = (porcentaje, nombre)
        fila["Ventas"] = ventas.get(t.id, 0)
        fila["Uso más alto (%)"] = round(mayor[0]) if mayor[0] is not None else 0
        fila["Recurso más usado"] = "Sin límites" if mayor[0] is None else (mayor[1] if mayor[0] > 0 else "—")
        filas.append(fila)
    return filas


def _resumen_uso(filas: list[Fila], periodo: str) -> str:
    cerca = [f["Empresa"] for f in filas if f["Uso más alto (%)"] >= 80]
    return (
        f"{len(cerca)} de {len(filas)} empresas usan el 80 % o más de algún límite de su plan"
        + (f": {', '.join(cerca)}. Son candidatas a mejorar el plan." if cerca else ".")
        + f" Las ventas cuentan {periodo}."
    )


def _filas_ventas(db: Session, desde: Optional[date], hasta: Optional[date]) -> list[Fila]:
    planes, suscripciones = _planes(db), _suscripciones(db)
    por_tienda = {
        tienda_id: (cantidad, _monto(total))
        for tienda_id, cantidad, total in db.execute(
            select(Venta.tienda_id, func.count(), func.coalesce(func.sum(Venta.total), 0))
            .where(Venta.estado == EstadoVenta.pagada, *_en_rango(Venta.fecha_venta, desde, hasta))
            .group_by(Venta.tienda_id)
        ).all()
    }
    filas = []
    for t in db.scalars(select(Tienda)).all():
        cantidad, total = por_tienda.get(t.id, (0, 0.0))
        s = suscripciones.get(t.id)
        filas.append({
            "Empresa": t.nombre, "Plan": planes[s.plan_id].nombre if s else "-", "Ventas": cantidad,
            "Total vendido (Bs.)": total, "Ticket promedio (Bs.)": round(total / cantidad, 2) if cantidad else 0.0,
        })
    return filas


def _resumen_ventas(filas: list[Fila], periodo: str) -> str:
    cantidad, total = sum(f["Ventas"] for f in filas), sum(f["Total vendido (Bs.)"] for f in filas)
    lider = max(filas, key=lambda f: f["Total vendido (Bs.)"], default=None)
    texto = f"Las empresas registraron {cantidad} ventas pagadas por Bs. {total:,.2f} {periodo}."
    if lider and lider["Total vendido (Bs.)"]:
        texto += f" Lidera {lider['Empresa']} con Bs. {lider['Total vendido (Bs.)']:,.2f}."
    return texto


def _filas_historial(db: Session, desde: Optional[date], hasta: Optional[date]) -> list[Fila]:
    movimientos = db.execute(
        select(MovimientoSuscripcion, Tienda.nombre, Plan.nombre, Usuario.correo)
        .join(Tienda, Tienda.id == MovimientoSuscripcion.tienda_id)
        .join(Plan, Plan.id == MovimientoSuscripcion.plan_id)
        .outerjoin(Usuario, Usuario.id == MovimientoSuscripcion.usuario_id)
        .where(*_en_rango(MovimientoSuscripcion.fecha, desde, hasta))
    ).all()
    return [
        {
            "Fecha": m.fecha.strftime("%d/%m/%Y %H:%M"), "Empresa": empresa, "Movimiento": MOVIMIENTOS.get(m.tipo, m.tipo),
            "Plan": plan, "Monto (USD)": _monto(m.monto), "Origen": ORIGENES.get(m.origen, m.origen),
            "Responsable": correo or ("La empresa (autoservicio)" if m.origen in ("simulado", "stripe") else "Plataforma"),
            "Detalle": m.detalle or "", "_orden_fecha": m.fecha,
        }
        for m, empresa, plan, correo in movimientos
    ]


def _resumen_historial(filas: list[Fila], periodo: str) -> str:
    por_tipo = defaultdict(int)
    for f in filas:
        por_tipo[f["Movimiento"]] += 1
    resumen = ", ".join(f"{cantidad} {tipo.lower()}" for tipo, cantidad in sorted(por_tipo.items(), key=lambda x: -x[1]))
    return f"{len(filas)} movimientos {periodo}" + (f": {resumen}." if resumen else ".")


REPORTES: dict[str, Definicion] = {
    "empresas": Definicion(
        titulo="Empresas y suscripciones",
        descripcion="Cada empresa con su plan, el estado de su suscripción y cuándo vence. Las fechas filtran por fecha de alta.",
        columnas=["Empresa", "Dirección", "Plan", "Estado", "Suscripción", "Alta", "Inicio", "Vence", "Días restantes", "Precio mensual (USD)"],
        obtener=_filas_empresas, resumir=_resumen_empresas, orden=("Días restantes", False),
        sumables=["Precio mensual (USD)"], columnas_monto=["Precio mensual (USD)"],
        valores={"Estado": ["activa", "suspendida"], "Suscripción": ["activa", "vencida", "cancelada"]},
    ),
    "ingresos": Definicion(
        titulo="Ingresos por suscripciones",
        descripcion="Cobros de altas, cambios de plan y renovaciones. Las fechas filtran por fecha del cobro.",
        columnas=["Fecha", "Empresa", "Movimiento", "Plan", "Origen", "Monto (USD)"],
        obtener=_filas_ingresos, resumir=_resumen_ingresos, orden=("Fecha", True),
        sumables=["Monto (USD)"], columnas_monto=["Monto (USD)"],
        valores={"Movimiento": list(MOVIMIENTOS.values()), "Origen": list(ORIGENES.values())},
    ),
    "uso": Definicion(
        titulo="Uso de cada empresa frente a su plan",
        descripcion="Sucursales, prendas y empleados activos frente a los límites del plan. Las fechas filtran las ventas.",
        columnas=["Empresa", "Plan", "Sucursales", "Prendas", "Empleados", "Ventas", "Uso más alto (%)", "Recurso más usado"],
        obtener=_filas_uso, resumir=_resumen_uso, orden=("Uso más alto (%)", True), sumables=["Ventas"],
    ),
    "ventas": Definicion(
        titulo="Ventas por empresa",
        descripcion="Ventas pagadas de cada empresa, con total y ticket promedio. Las fechas filtran por fecha de venta.",
        columnas=["Empresa", "Plan", "Ventas", "Total vendido (Bs.)", "Ticket promedio (Bs.)"],
        obtener=_filas_ventas, resumir=_resumen_ventas, orden=("Total vendido (Bs.)", True),
        sumables=["Ventas", "Total vendido (Bs.)"], columnas_monto=["Total vendido (Bs.)", "Ticket promedio (Bs.)"],
        etiqueta_total="TOTAL PLATAFORMA",
    ),
    "historial": Definicion(
        titulo="Historial de la plataforma",
        descripcion="Cada alta, cambio de plan, renovación, suspensión o ajuste de una suscripción, con quién lo hizo.",
        columnas=["Fecha", "Empresa", "Movimiento", "Plan", "Monto (USD)", "Origen", "Responsable", "Detalle"],
        obtener=_filas_historial, resumir=_resumen_historial, orden=("Fecha", True),
        sumables=["Monto (USD)"], columnas_monto=["Monto (USD)"],
        valores={"Movimiento": list(MOVIMIENTOS.values()), "Origen": list(ORIGENES.values())},
    ),
    "bitacora": Definicion(
        titulo="Bitácora de la plataforma",
        descripcion=(
            "Cada acción de cada usuario de todas las empresas y de la plataforma: fecha y hora (Bolivia), "
            "empresa, usuario, rol, IP y acción. Las fechas filtran por fecha de la acción."
        ),
        columnas=["Fecha", "Empresa", "Usuario", "Rol", "IP", "Acción"],
        obtener=bitacora_service.filas, resumir=bitacora_service.resumir, orden=("Fecha", True),
    ),
}


# --------------------------------------------------------------------------- motor (reportes_personalizados)

QUIEN = "del administrador de una plataforma SaaS de tiendas de ropa"
EJEMPLOS = (
    "«ingresos de octubre del plan Profesional», «empresas que vencen este mes», "
    "«ventas por empresa ordenadas por total» o «inicios de sesión fallidos de esta semana»"
)


def catalogo() -> list[dict]:
    return motor.catalogo(REPORTES)


def generar(db: Session, tipo: str, **opciones) -> Reporte:
    return motor.generar(REPORTES, db, tipo, **opciones)


def prompt_interpretacion(fecha_hoy: date) -> str:
    return motor.prompt_interpretacion(REPORTES, fecha_hoy, QUIEN)


def opciones_desde_ia(datos: Any) -> dict:
    return motor.opciones_desde_ia(REPORTES, datos)


def interpretar(pedido: str) -> dict:
    return motor.interpretar(REPORTES, pedido, QUIEN, EJEMPLOS)


# --------------------------------------------------------------------------- indicadores

def _meses_hacia_atras(hoy: date, cantidad: int) -> list[tuple[int, int]]:
    anio, mes, meses = hoy.year, hoy.month, []
    for _ in range(cantidad):
        meses.append((anio, mes))
        anio, mes = (anio - 1, 12) if mes == 1 else (anio, mes - 1)
    return list(reversed(meses))


def indicadores(db: Session) -> dict:
    """Lo que muestra el tablero del superadmin."""
    hoy = _hoy()
    suscripciones, planes = _suscripciones(db), _planes(db)
    tiendas = db.scalars(select(Tienda)).all()

    vigentes = [t for t in tiendas if _vigente(t, suscripciones.get(t.id))]
    ingreso_mensual = round(sum(_monto(planes[suscripciones[t.id].plan_id].precio_mensual) for t in vigentes), 2)

    por_plan = defaultdict(lambda: {"cantidad": 0, "ingreso_mensual": 0.0})
    for t in tiendas:
        s = suscripciones.get(t.id)
        if s:
            plan = planes[s.plan_id]
            por_plan[plan.nombre]["cantidad"] += 1
            if _vigente(t, s):
                por_plan[plan.nombre]["ingreso_mensual"] += _monto(plan.precio_mensual)

    meses = _meses_hacia_atras(hoy, MESES_EN_EL_GRAFICO)
    ingresos = defaultdict(float)
    for fecha, monto in db.execute(
        select(MovimientoSuscripcion.fecha, MovimientoSuscripcion.monto)
        .where(MovimientoSuscripcion.monto > 0, MovimientoSuscripcion.fecha >= _inicio_dia(date(meses[0][0], meses[0][1], 1)))
    ).all():
        ingresos[(fecha.year, fecha.month)] += _monto(monto)

    proximos = []
    for t in vigentes:
        dias = _dias_restantes(suscripciones[t.id], hoy)
        if dias is not None and dias <= DIAS_POR_VENCER:
            proximos.append({"empresa": t.nombre, "slug": t.slug, "vence": suscripciones[t.id].fecha_vencimiento, "dias": dias})

    ventas = sorted(_filas_ventas(db, None, None), key=lambda f: -f["Total vendido (Bs.)"])
    return {
        "empresas": len(tiendas),
        "vigentes": len(vigentes),
        "suspendidas": sum(t.estado == "suspendida" for t in tiendas),
        "sin_suscripcion_vigente": sum(t.estado == "activa" and not _vigente(t, suscripciones.get(t.id)) for t in tiendas),
        "ingreso_mensual": ingreso_mensual,
        "ingresos_mes_actual": round(ingresos.get((hoy.year, hoy.month), 0.0), 2),
        "ingresos_por_mes": [
            {"mes": f"{anio}-{mes:02d}", "etiqueta": f"{MESES[mes - 1]} {anio}", "monto": round(ingresos.get((anio, mes), 0.0), 2)}
            for anio, mes in meses
        ],
        "empresas_por_plan": [
            {"plan": nombre, "cantidad": datos["cantidad"], "ingreso_mensual": round(datos["ingreso_mensual"], 2)}
            for nombre, datos in sorted(por_plan.items(), key=lambda x: -x[1]["cantidad"])
        ],
        "ventas_por_empresa": [{"empresa": f["Empresa"], "ventas": f["Ventas"], "total": f["Total vendido (Bs.)"]} for f in ventas],
        "proximos_vencimientos": sorted(proximos, key=lambda p: p["dias"]),
    }
