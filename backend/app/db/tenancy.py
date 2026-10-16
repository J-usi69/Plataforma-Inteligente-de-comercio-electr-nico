"""Multi-tienda (SaaS): todas las tiendas comparten la base y cada fila de negocio lleva su
tienda_id. Dos capas evitan que una tienda vea datos de otra:

1. ORM: en cada pedido la sesión sabe de qué tienda es (session.info["tienda_id"]); toda
   consulta se filtra sola por esa tienda y todo lo que se inserta la recibe. Ningún endpoint
   tiene que acordarse de filtrar.
2. Postgres (Row Level Security): cada transacción corre con un rol sin privilegios de bypass y
   con app.tienda_id fijado, así que aunque una consulta se escapara del ORM, la base no
   devuelve ni acepta filas de otra tienda.

La tienda sale de la cabecera X-Tienda (o ?tienda=, o el subdominio si hay dominio propio); sin
ninguna, la tienda por defecto, para que la web y la app actuales sigan funcionando igual.
"""
import time
from dataclasses import dataclass
from typing import Optional

from fastapi import HTTPException, Request, status
from sqlalchemy import ForeignKey, event, text
from sqlalchemy.orm import Mapped, Session, mapped_column, with_loader_criteria

from app.core.config import settings

ROL_APP = "fashionstore_app"  # rol sin BYPASSRLS creado por la migración de RLS
CLAVE_TIENDA = "tienda_id"


class PerteneceATienda:
    """Fila de negocio de una tienda: tienda_id obligatorio."""

    tienda_id: Mapped[int] = mapped_column(ForeignKey("tienda.id"), index=True)


class PerteneceATiendaOPlataforma:
    """tienda_id vacío = de la plataforma (superadmin y su bitácora). Dentro de una tienda solo
    se ven las filas de esa tienda, nunca las de la plataforma."""

    tienda_id: Mapped[Optional[int]] = mapped_column(ForeignKey("tienda.id"), index=True)


_CON_TIENDA = (PerteneceATienda, PerteneceATiendaOPlataforma)


@event.listens_for(Session, "do_orm_execute")
def _filtrar_por_tienda(estado) -> None:
    tienda_id = estado.session.info.get(CLAVE_TIENDA)
    if tienda_id is None:
        return
    # Las cargas de relaciones heredan el filtro de la consulta que trajo al objeto
    if estado.is_select and (estado.is_column_load or estado.is_relationship_load):
        return
    if not (estado.is_select or estado.is_update or estado.is_delete):
        return
    estado.statement = estado.statement.options(
        *(
            with_loader_criteria(mixin, lambda cls: cls.tienda_id == tienda_id, include_aliases=True)
            for mixin in _CON_TIENDA
        )
    )


@event.listens_for(Session, "before_flush")
def _asignar_tienda(session: Session, _flush_context, _instances) -> None:
    tienda_id = session.info.get(CLAVE_TIENDA)
    if tienda_id is None:
        return
    for obj in session.new:
        if not isinstance(obj, _CON_TIENDA):
            continue
        if obj.tienda_id is None:
            obj.tienda_id = tienda_id
        elif obj.tienda_id != tienda_id:
            raise ValueError(f"No se puede crear {type(obj).__name__} de la tienda {obj.tienda_id} desde la tienda {tienda_id}")


@event.listens_for(Session, "after_begin")
def _activar_rls(session: Session, _transaccion, conexion) -> None:
    tienda_id = session.info.get(CLAVE_TIENDA)
    if tienda_id is None or not settings.rls_habilitado or conexion.dialect.name != "postgresql":
        return
    # SET LOCAL: dura lo que la transacción; cada commit abre otra y este evento lo vuelve a fijar
    conexion.exec_driver_sql(f"SET LOCAL ROLE {ROL_APP}")
    conexion.execute(text("SELECT set_config('app.tienda_id', :t, true)"), {"t": str(tienda_id)})


# ------------------------------------------------------------------------------
# De qué tienda es cada pedido
# ------------------------------------------------------------------------------
@dataclass(frozen=True)
class TiendaActual:
    id: int
    slug: str
    nombre: str
    estado: str


_CACHE_SEGUNDOS = 60
_cache: dict[str, tuple[Optional[TiendaActual], float]] = {}


def olvidar_tienda(slug: str) -> None:
    """Llamar al cambiar el estado o los datos de una tienda (si no, se ve hasta 60 s después)."""
    _cache.pop(slug, None)


def slug_de_la_peticion(request: Request) -> str:
    # En la ruta (avisos de pasarelas, que no mandan cabeceras), en la cabecera o como parámetro
    slug = (
        request.path_params.get("tienda_slug")
        or request.headers.get("X-Tienda")
        or request.query_params.get("tienda")
    )
    if not slug and settings.dominio_base:
        # Subdominio: mi-tienda.dominio.com -> "mi-tienda"
        host = (request.headers.get("host") or "").split(":")[0].lower()
        sufijo = "." + settings.dominio_base.lower()
        if host.endswith(sufijo):
            slug = host[: -len(sufijo)]
    return (slug or settings.tienda_por_defecto).strip().lower()


def buscar_tienda(slug: str) -> Optional[TiendaActual]:
    guardada = _cache.get(slug)
    if guardada and guardada[1] > time.monotonic():
        return guardada[0]
    from app.db.session import SessionLocal
    from app.models.tienda import Tienda

    with SessionLocal() as db:  # sin tienda: la tabla tienda es de la plataforma
        fila = db.query(Tienda).filter(Tienda.slug == slug).first()
        tienda = TiendaActual(fila.id, fila.slug, fila.nombre, fila.estado) if fila else None
    _cache[slug] = (tienda, time.monotonic() + _CACHE_SEGUNDOS)
    return tienda


def tienda_de_la_peticion(request: Request) -> TiendaActual:
    tienda = getattr(request.state, "tienda", None)
    if tienda is None:
        slug = slug_de_la_peticion(request)
        tienda = buscar_tienda(slug)
        if tienda is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No existe la tienda '{slug}'")
        if tienda.estado != "activa":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Esta tienda está suspendida")
        request.state.tienda = tienda
    return tienda
