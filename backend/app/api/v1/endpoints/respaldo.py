"""Respaldo y restauración de los datos de la empresa (característica 6), para su administrador.

El respaldo del sistema completo (todas las empresas) lo hace el superadmin: ver plataforma.py.
"""
from fastapi import APIRouter, Depends, File, Form, Request, Response, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_client_ip, get_db, registrar_bitacora, require_roles
from app.db.tenancy import CLAVE_TIENDA
from app.models.seguridad import Usuario
from app.models.tienda import Tienda
from app.schemas.tienda import RestauracionOut
from app.services import respaldo_service

router = APIRouter()
solo_administrador = require_roles(["Administrador"])


@router.get("")
def descargar_respaldo(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(solo_administrador),
):
    """Todos los datos de la empresa en un archivo .json.gz: catálogo, inventario, sucursales,
    personal, cuentas, roles y permisos, ventas, reservas y bitácora."""
    tienda = db.get(Tienda, db.info[CLAVE_TIENDA])
    contenido, resumen = respaldo_service.respaldar(db, tienda)
    registrar_bitacora(db, current_user.id, f"Respaldo de la empresa descargado ({sum(resumen.values())} registros)", get_client_ip(request))
    return Response(
        content=contenido, media_type="application/gzip",
        headers={"Content-Disposition": f'attachment; filename="{respaldo_service.nombre_archivo(tienda)}"'},
    )


@router.post("/restaurar", response_model=RestauracionOut)
def restaurar_respaldo(
    request: Request,
    archivo: UploadFile = File(..., description="El .json.gz descargado con «Descargar respaldo»"),
    simular: bool = Form(False, description="true: verifica y muestra qué se restauraría, sin cambiar nada"),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(solo_administrador),
):
    """Vuelve los datos de la empresa al estado del respaldo, en una sola transacción (si algo
    falla no cambia nada). La bitácora se conserva y el plan y la suscripción no cambian."""
    contenido = respaldo_service.leer(archivo.file.read(respaldo_service.MAX_COMPRIMIDO + 1))
    resultado = respaldo_service.restaurar(
        db, contenido, alcance="empresa", tienda_id=db.info[CLAVE_TIENDA], actor_id=current_user.id, simular=simular,
    )
    if not simular:
        fecha = (resultado.get("respaldo_del") or "")[:16].replace("T", " ")
        registrar_bitacora(db, current_user.id, f"Empresa restaurada desde el respaldo del {fecha} UTC", get_client_ip(request))
    return resultado
