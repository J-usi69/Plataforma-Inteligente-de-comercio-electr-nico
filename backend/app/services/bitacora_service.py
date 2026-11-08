"""Bitácora como reporte (característica 3): cada acción con fecha y hora, usuario, rol, IP y empresa.

Se lee con la sesión de quien consulta: en la de una empresa el ORM deja solo sus filas; en la de
la plataforma (superadmin) se ven todas las empresas y las acciones de la propia plataforma.
"""
from collections import defaultdict
from datetime import date
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.seguridad import Bitacora, Rol, Usuario, UsuarioRol
from app.models.tienda import Tienda
from app.services.reportes_personalizados import Fila, en_rango, fecha_hora_local

# Tope de filas por consulta (las más recientes): para períodos largos conviene filtrar por fecha
LIMITE = 5000
PLATAFORMA = "Plataforma"


def filas(db: Session, desde: Optional[date], hasta: Optional[date]) -> list[Fila]:
    registros = db.execute(
        select(Bitacora, Usuario.correo, Usuario.es_superadmin, Tienda.nombre)
        .outerjoin(Usuario, Usuario.id == Bitacora.usuario_id)
        .outerjoin(Tienda, Tienda.id == Bitacora.tienda_id)
        .where(*en_rango(Bitacora.fecha, desde, hasta))
        .order_by(Bitacora.fecha.desc(), Bitacora.id.desc())
        .limit(LIMITE)
    ).all()
    ids = {b.usuario_id for b, *_ in registros}
    roles: dict[int, list[str]] = defaultdict(list)
    if ids:
        for usuario_id, nombre in db.execute(
            select(UsuarioRol.usuario_id, Rol.nombre).join(Rol, Rol.id == UsuarioRol.rol_id).where(UsuarioRol.usuario_id.in_(ids))
        ).all():
            roles[usuario_id].append(nombre)
    return [
        {
            "Fecha": fecha_hora_local(b.fecha),
            "Empresa": empresa or PLATAFORMA,
            "Usuario": correo or f"Usuario #{b.usuario_id}",
            "Rol": ", ".join(sorted(roles[b.usuario_id])) or ("Superadmin" if superadmin else "-"),
            "IP": b.ip or "-",
            "Acción": b.accion,
            "_orden_fecha": b.fecha,
        }
        for b, correo, superadmin, empresa in registros
    ]


def resumir(filas_filtradas: list[Fila], periodo: str) -> str:
    usuarios = len({f["Usuario"] for f in filas_filtradas})
    fallidos = sum("fallido" in f["Acción"].lower() for f in filas_filtradas)
    texto = f"{len(filas_filtradas)} acciones registradas {periodo} por {usuarios} usuario(s)"
    texto += f"; {fallidos} intento(s) fallido(s) de inicio de sesión." if fallidos else "."
    if len(filas_filtradas) >= LIMITE:
        texto += f" Se muestran las {LIMITE} más recientes: acotá las fechas para ver las anteriores."
    return texto
