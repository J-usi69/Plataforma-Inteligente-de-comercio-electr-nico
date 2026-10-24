"""Operación sin conexión (PWA y app móvil): el paquete de datos para trabajar sin Internet, la
recepción idempotente de las operaciones pendientes, la consulta de su estado y la resolución de
conflictos por el encargado. Las reglas están en app/services/sincronizacion_service.py."""
from datetime import datetime, timezone
from typing import List, Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_client_ip, get_current_active_user, get_db, get_user_roles, registrar_bitacora, require_roles
from app.models.seguridad import Usuario
from app.schemas.sincronizacion import (
    EstadoOperacionesOut,
    LoteIn,
    LoteOut,
    OperacionAdminOut,
    PaqueteOut,
    ResolverConflictoIn,
)
from app.services import sincronizacion_service as sync
from app.services.sincronizacion_service import Actor

router = APIRouter()
_ROLES_SUPERVISION = ["Encargado", "Administrador"]


def _actor(db: Session, usuario: Usuario) -> Actor:
    return Actor(usuario, frozenset(get_user_roles(usuario.id, db)))


@router.get("/paquete", response_model=PaqueteOut)
def descargar_paquete(
    sucursal_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    """Lo que el dispositivo guarda para trabajar sin conexión: catálogo con precios, tallas y
    colores, existencias de las sucursales autorizadas y, para el personal, los clientes y las
    ventas que todavía se pueden cambiar. Con generado_en y vigencia_horas la app avisa cuando lo
    que muestra puede estar desactualizado."""
    return sync.armar_paquete(db, _actor(db, current_user), sucursal_id)


@router.post("/operaciones", response_model=LoteOut)
def recibir_operaciones(
    lote: LoteIn,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    """Recibe las operaciones registradas sin conexión y devuelve el resultado de cada una
    (confirmada, rechazada, conflicto o error). Reenviar una operación ya recibida no la aplica
    de nuevo: devuelve el resultado guardado (duplicada = true). El dispositivo solo da por
    terminada una operación cuando recibe su resultado; si la respuesta no llega, la reenvía."""
    actor = _actor(db, current_user)
    recibido_en = datetime.now(timezone.utc)
    request_id = getattr(request.state, "request_id", None)
    resultados = [sync.procesar_operacion(db, actor, op, request_id) for op in lote.operaciones]
    return LoteOut(recibido_en=recibido_en, resultados=resultados)


@router.get("/estado", response_model=EstadoOperacionesOut)
def consultar_estado(
    ids: List[UUID] = Query(..., max_length=100),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    """Estado actual de operaciones ya enviadas (por ejemplo, un conflicto que el encargado ya
    resolvió). Las que el servidor no recibió vuelven en "desconocidas" para reenviarlas. Un
    cliente solo ve las suyas."""
    actor = _actor(db, current_user)
    return sync.estado_de(db, ids, None if actor.es_personal else current_user.id)


@router.get("/operaciones", response_model=List[OperacionAdminOut])
def listar_operaciones(
    estado: Optional[Literal["confirmada", "rechazada", "conflicto"]] = None,
    sucursal_id: Optional[int] = None,
    limite: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_roles(_ROLES_SUPERVISION)),
):
    """Panel de sincronización: qué llegó, de quién, desde qué dispositivo, cuántos intentos y con
    qué resultado. El encargado ve las de su sucursal; el administrador, las de todas."""
    actor = _actor(db, current_user)
    if not actor.es_admin:
        if actor.sucursal_id is None:
            return []
        sucursal_id = actor.sucursal_id
    return sync.listar(db, estado, sucursal_id, limite)


@router.post("/operaciones/{operacion_id}/resolver", response_model=OperacionAdminOut)
def resolver_conflicto(
    operacion_id: UUID,
    datos: ResolverConflictoIn,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_roles(_ROLES_SUPERVISION)),
):
    """Decide una operación en conflicto. aceptar: se registra como la hizo su autor y el faltante
    de inventario queda en el kardex. rechazar: no se registra."""
    resolutor = _actor(db, current_user)
    registro = sync.bloquear_para_resolver(db, operacion_id)
    if registro is None or (not resolutor.es_admin and registro.sucursal_id != resolutor.sucursal_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Operación no encontrada")
    if registro.estado != sync.CONFLICTO:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"La operación ya está {registro.estado}: solo se resuelven las que están en conflicto",
        )
    autor = db.get(Usuario, registro.usuario_id) if registro.usuario_id else None
    registro = sync.resolver_conflicto(
        db, registro, _actor(db, autor) if autor else None, current_user.id, datos.accion, datos.nota
    )
    resultado = "aceptada" if datos.accion == "aceptar" else "rechazada"
    registrar_bitacora(db, current_user.id, f"Sincronización: operación {registro.uuid} {resultado}", get_client_ip(request))
    return sync.para_supervision(db, registro)
