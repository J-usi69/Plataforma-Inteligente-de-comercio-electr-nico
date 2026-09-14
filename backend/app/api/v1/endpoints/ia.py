import json
from datetime import date, datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.models.catalogo import Categoria, Coleccion, Prenda
from app.models.ia import InteraccionIA
from app.models.reserva import DetalleReserva, Reserva
from app.models.seguridad import Usuario
from app.models.venta import DetalleVenta, Venta
from app.schemas.catalogo import PrendaOut
from app.schemas.ia import ChatRequest, ChatResponse, RecomendacionOut, ReporteIARequest, ReporteIAResponse
from app.services import reportes_service
from app.services.ia_service import IAServiceError, llamar_claude

router = APIRouter()

_MENSAJE_LIMITACION_CHAT = (
    "En este momento el asistente virtual no está disponible. "
    "Podés explorar el catálogo directamente o visitar la sucursal más cercana para recibir ayuda."
)
_MENSAJE_REPORTE_AMBIGUO = (
    "No se pudo interpretar la solicitud. Reformulala con más detalle (por ejemplo, "
    "'ventas de la sucursal Equipetrol del último mes') o usá los reportes predefinidos."
)
_TIPOS_REPORTE_VALIDOS = {"ventas", "prendas_vendidas", "inventario"}


def _prenda_a_out(db: Session, prenda: Prenda) -> PrendaOut:
    cat = db.get(Categoria, prenda.categoria_id) if prenda.categoria_id else None
    col = db.get(Coleccion, prenda.coleccion_id) if prenda.coleccion_id else None
    return PrendaOut(
        id=prenda.id,
        nombre=prenda.nombre,
        descripcion=prenda.descripcion,
        categoria_id=prenda.categoria_id,
        coleccion_id=prenda.coleccion_id,
        proveedor_id=prenda.proveedor_id,
        precio_base=float(prenda.precio_base),
        modelo_3d_url=prenda.modelo_3d_url,
        imagen_url=prenda.imagen_url,
        estado=prenda.estado,
        categoria_nombre=cat.nombre if cat else None,
        coleccion_nombre=col.nombre if col else None,
        proveedor_nombre=None,
    )


def _registrar_interaccion(db: Session, usuario_id: int, tipo: str, prompt: Optional[str], sugeridas: Optional[str] = None, respuesta: Optional[str] = None) -> None:
    db.add(InteraccionIA(
        usuario_id=usuario_id,
        tipo_consulta=tipo,
        prompt_consulta=prompt,
        prendas_sugeridas_ids=sugeridas,
        respuesta=respuesta,
        fecha=datetime.now(timezone.utc),
    ))
    db.commit()


def _fallback_mas_vendidas(db: Session, limit: int = 5) -> List[Prenda]:
    resultado = []
    for item in reportes_service.prendas_mas_vendidas(db, limit=limit):
        if item["prenda_id"]:
            prenda = db.get(Prenda, item["prenda_id"])
            if prenda:
                resultado.append(prenda)
    return resultado


@router.post("/recomendaciones", response_model=RecomendacionOut)
def obtener_recomendaciones(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_roles(["Cliente"])),
):
    """CU-28: recomienda prendas al cliente según su historial de compras y reservas."""
    ventas_ids = db.scalars(
        select(Venta.id).where(Venta.usuario_id == current_user.id).order_by(Venta.fecha_venta.desc()).limit(10)
    ).all()
    reservas_ids = db.scalars(
        select(Reserva.id).where(Reserva.usuario_id == current_user.id).order_by(Reserva.fecha_reserva.desc()).limit(10)
    ).all()

    nombres_historial = set()
    for detalle in db.scalars(select(DetalleVenta).where(DetalleVenta.venta_id.in_(ventas_ids))).all():
        prenda = _prenda_de_variante(db, detalle.variante_id)
        if prenda:
            nombres_historial.add(prenda.nombre)
    for detalle in db.scalars(select(DetalleReserva).where(DetalleReserva.reserva_id.in_(reservas_ids))).all():
        prenda = _prenda_de_variante(db, detalle.variante_id)
        if prenda:
            nombres_historial.add(prenda.nombre)

    catalogo_activo = db.scalars(select(Prenda).where(Prenda.estado.is_(True)).order_by(Prenda.id.desc()).limit(30)).all()
    if not catalogo_activo:
        return RecomendacionOut(prendas=[], fuente="mas_vendidas")

    catalogo_resumen = [
        {"id": p.id, "nombre": p.nombre, "categoria_id": p.categoria_id, "precio": float(p.precio_base)}
        for p in catalogo_activo
    ]
    prompt = (
        f"Historial de compras/reservas del cliente: {sorted(nombres_historial) or 'sin historial previo'}.\n"
        f"Catálogo disponible (JSON): {json.dumps(catalogo_resumen, ensure_ascii=False)}\n\n"
        "Recomendá hasta 5 prendas del catálogo que mejor combinen con el historial del cliente "
        "(o las más versátiles si no hay historial). Respondé ÚNICAMENTE con un array JSON de los "
        'ids recomendados, por ejemplo: [12, 5, 8]. No agregues texto adicional.'
    )

    prendas_recomendadas: List[Prenda] = []
    fuente = "ia"
    try:
        respuesta = llamar_claude(
            system_prompt="Sos el asistente de recomendaciones de productos de FashionStore, una tienda de ropa.",
            user_prompt=prompt,
            max_tokens=200,
        )
        ids_validos = {p.id for p in catalogo_activo}
        ids_sugeridos = [i for i in json.loads(respuesta) if isinstance(i, int) and i in ids_validos]
        if not ids_sugeridos:
            raise ValueError("La IA no sugirió ids válidos")
        por_id = {p.id: p for p in catalogo_activo}
        prendas_recomendadas = [por_id[i] for i in ids_sugeridos[:5]]
    except (IAServiceError, ValueError, json.JSONDecodeError, TypeError):
        # Excepción documentada en CU-28: si el Servicio de IA no responde a tiempo o falla,
        # se muestran las prendas más vendidas de la temporada vigente como alternativa.
        fuente = "mas_vendidas"
        prendas_recomendadas = _fallback_mas_vendidas(db) or list(catalogo_activo[:5])

    _registrar_interaccion(
        db, current_user.id, "recomendacion", prompt[:2000],
        sugeridas=",".join(str(p.id) for p in prendas_recomendadas),
    )
    return RecomendacionOut(prendas=[_prenda_a_out(db, p) for p in prendas_recomendadas], fuente=fuente)


def _prenda_de_variante(db: Session, variante_id: int) -> Optional[Prenda]:
    from app.models.catalogo import VariantePrenda
    variante = db.get(VariantePrenda, variante_id)
    return db.get(Prenda, variante.prenda_id) if variante else None


@router.post("/chat", response_model=ChatResponse)
def chat_asistente(
    datos: ChatRequest,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_roles(["Cliente"])),
):
    """CU-29: asistente conversacional sobre prendas, tallas, disponibilidad y reservas."""
    categorias = db.scalars(select(Categoria).where(Categoria.estado.is_(True))).all()
    contexto = f"Categorías disponibles en la tienda: {', '.join(c.nombre for c in categorias)}."

    try:
        respuesta = llamar_claude(
            system_prompt=(
                "Sos el asistente virtual de FashionStore, una tienda de ropa con sucursales físicas y venta "
                "online. Ayudás a clientes con preguntas sobre prendas, tallas, disponibilidad y el proceso de "
                "reserva o compra. Sé breve y concreto. " + contexto
            ),
            user_prompt=datos.mensaje,
            max_tokens=400,
        )
    except IAServiceError:
        respuesta = _MENSAJE_LIMITACION_CHAT

    _registrar_interaccion(db, current_user.id, "chatbot", datos.mensaje[:2000], respuesta=respuesta[:4000])
    return ChatResponse(respuesta=respuesta)


@router.post("/reportes", response_model=ReporteIAResponse)
def generar_reporte_ia(
    datos: ReporteIARequest,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_roles(["Administrador"])),
):
    """CU-30: interpreta una solicitud de reporte en lenguaje natural y devuelve
    el mismo tipo de datos que los reportes predefinidos (CU-31)."""
    system_prompt = (
        "Traducís pedidos de reportes de negocio en lenguaje natural a un JSON estricto. "
        'Respondé ÚNICAMENTE con un objeto JSON de la forma '
        '{"tipo": "ventas"|"prendas_vendidas"|"inventario", "desde": "YYYY-MM-DD"|null, '
        '"hasta": "YYYY-MM-DD"|null, "sucursal_id": entero|null}. Sin texto adicional.'
    )
    try:
        respuesta = llamar_claude(system_prompt=system_prompt, user_prompt=datos.prompt, max_tokens=200)
        parametros = json.loads(respuesta)
        tipo = parametros.get("tipo")
        if tipo not in _TIPOS_REPORTE_VALIDOS:
            raise ValueError("tipo de reporte no soportado")
        desde = date.fromisoformat(parametros["desde"]) if parametros.get("desde") else None
        hasta = date.fromisoformat(parametros["hasta"]) if parametros.get("hasta") else None
        sucursal_id = parametros.get("sucursal_id")
    except (IAServiceError, ValueError, TypeError, json.JSONDecodeError, KeyError):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=_MENSAJE_REPORTE_AMBIGUO)

    if tipo == "ventas":
        resultado = reportes_service.ventas_por_sucursal(db, desde=desde, hasta=hasta)
    elif tipo == "prendas_vendidas":
        resultado = reportes_service.prendas_mas_vendidas(db, desde=desde, hasta=hasta, limit=10)
    else:
        resultado = reportes_service.quiebres_stock(db, sucursal_id=sucursal_id)

    _registrar_interaccion(db, current_user.id, "reporte", datos.prompt[:2000], respuesta=json.dumps(parametros))
    return ReporteIAResponse(tipo=tipo, parametros=parametros, datos=resultado)
