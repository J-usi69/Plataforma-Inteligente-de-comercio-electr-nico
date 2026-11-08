"""Respaldo y restauración (característica 6).

Dos alcances:
- "empresa": todos los datos de una empresa (su administrador, o el superadmin para cualquiera).
- "sistema": la base entera, todas las empresas y la plataforma (solo el superadmin).

El respaldo es un JSON comprimido (gzip) con las filas de cada tabla. La restauración corre en una
sola transacción: si algo falla, la base queda como estaba. Con simular=True hace todo y al final
deshace, para mostrar qué se restauraría antes de confirmar.

Reglas para no perder información ni abrir huecos de seguridad:
- La bitácora no se vuelve atrás: se conservan las acciones actuales y se agregan las del respaldo
  que falten (la auditoría también registra la restauración).
- Las cuentas creadas después del respaldo no se borran (la bitácora las referencia): quedan
  desactivadas. La cuenta de quien restaura nunca se desactiva.
- Una empresa no puede restaurar su suscripción, su plan ni datos de otra empresa: cada fila del
  respaldo debe ser de esa empresa y cada referencia a otra fila, apuntar a una fila suya.
"""
import gzip
import io
import json
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, time, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Optional

from fastapi import HTTPException, status
from sqlalchemy import Enum as SAEnum
from sqlalchemy import Table, delete, func, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

import app.models  # noqa: F401 (registra todas las tablas en el metadata)
from app.db.session import Base

FORMATO = "fashionstore-respaldo"
VERSION = 1
MAX_COMPRIMIDO = 25 * 1024 * 1024
MAX_DESCOMPRIMIDO = 400 * 1024 * 1024
LOTE = 1000

# Cómo se restaura cada tabla
REEMPLAZAR = "reemplazar"  # se borran las filas actuales y se cargan las del respaldo
ACTUALIZAR = "actualizar"  # las del respaldo se insertan o actualizan; las demás quedan
USUARIOS = "usuarios"      # como ACTUALIZAR, y las cuentas que no están en el respaldo se desactivan
ANEXAR = "anexar"          # solo se agregan las del respaldo que falten (bitácora)
EXCLUIR = "excluir"

# Tokens de notificaciones push: son de cada dispositivo, no se respaldan
NO_SE_RESPALDAN = {"push_token"}
# De la plataforma pero con una fila por empresa: una empresa no restaura su propia suscripción
DE_SUSCRIPCION = {"suscripcion", "movimiento_suscripcion"}


def _modo(tabla: Table, alcance: str) -> str:
    if tabla.name in NO_SE_RESPALDAN:
        return EXCLUIR
    if tabla.name == "usuario":
        return USUARIOS
    if tabla.name == "bitacora":
        return ANEXAR
    if "tienda_id" in tabla.c and tabla.name not in DE_SUSCRIPCION:
        return REEMPLAZAR
    if alcance == "empresa":
        return EXCLUIR
    # Sistema: el historial de suscripciones se reemplaza; ciudades, permisos, planes, empresas y
    # suscripciones se actualizan (las filas nuevas quedan, otras tablas dependen de ellas)
    return REEMPLAZAR if tabla.name == "movimiento_suscripcion" else ACTUALIZAR


def _tablas(alcance: str) -> list[tuple[Table, str]]:
    """Las tablas del alcance con su modo, de madres a hijas (orden de las claves foráneas)."""
    return [(t, _modo(t, alcance)) for t in Base.metadata.sorted_tables if _modo(t, alcance) != EXCLUIR]


def _filtro(tabla: Table, tienda_id: Optional[int]):
    return [tabla.c.tienda_id == tienda_id] if tienda_id is not None else []


# --------------------------------------------------------------------------- valores <-> JSON

def _a_json(valor: Any) -> Any:
    if isinstance(valor, Enum):
        return valor.name
    if isinstance(valor, (datetime, date, time)):
        return valor.isoformat()
    if isinstance(valor, (Decimal, uuid.UUID)):
        return str(valor)
    return valor


def _tipo_python(columna) -> Optional[type]:
    try:
        return columna.type.python_type
    except NotImplementedError:
        return None


def _de_json(columna, valor: Any) -> Any:
    if valor is None or isinstance(columna.type, SAEnum):
        return valor
    convertir = {
        datetime: datetime.fromisoformat, date: date.fromisoformat, time: time.fromisoformat,
        Decimal: Decimal, uuid.UUID: uuid.UUID, int: int, bool: bool,
    }.get(_tipo_python(columna))
    return convertir(valor) if convertir else valor


# --------------------------------------------------------------------------- respaldar

def _revision(db: Session) -> Optional[str]:
    # En la sesión de una empresa la tabla no es visible (Row Level Security): queda sin revisión
    return db.execute(text("SELECT version_num FROM alembic_version")).scalar()


def respaldar(db: Session, tienda: Optional[Any] = None) -> tuple[bytes, dict]:
    """tienda=None: el sistema entero (sesión de la plataforma). Con tienda: solo esa empresa.
    Devuelve el archivo comprimido y el resumen (filas por tabla)."""
    alcance = "empresa" if tienda is not None else "sistema"
    tienda_id = tienda.id if tienda is not None else None
    tablas = {}
    for tabla, _ in _tablas(alcance):
        consulta = select(tabla).where(*_filtro(tabla, tienda_id))
        if "id" in tabla.c:
            consulta = consulta.order_by(tabla.c.id)
        filas = db.execute(consulta).all()
        columnas = [c.name for c in tabla.columns]
        tablas[tabla.name] = {"columnas": columnas, "filas": [[_a_json(v) for v in fila] for fila in filas]}
    resumen = {nombre: len(datos["filas"]) for nombre, datos in tablas.items()}
    contenido = {
        "formato": FORMATO,
        "version": VERSION,
        "alcance": alcance,
        "creado_en": datetime.now(timezone.utc).isoformat(),
        "revision_bd": _revision(db),
        "tienda": {"id": tienda.id, "slug": tienda.slug, "nombre": tienda.nombre} if tienda is not None else None,
        "resumen": resumen,
        "tablas": tablas,
    }
    datos = json.dumps(contenido, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return gzip.compress(datos, compresslevel=6), resumen


# --------------------------------------------------------------------------- leer y validar

def _invalido(detalle: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detalle)


def leer(archivo: bytes) -> dict:
    """Descomprime y valida la forma del archivo (no su contenido)."""
    if len(archivo) > MAX_COMPRIMIDO:
        raise _invalido(f"El archivo supera los {MAX_COMPRIMIDO // (1024 * 1024)} MB permitidos")
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(archivo)) as comprimido:
            datos = comprimido.read(MAX_DESCOMPRIMIDO + 1)
        if len(datos) > MAX_DESCOMPRIMIDO:
            raise _invalido("El respaldo es demasiado grande")
        contenido = json.loads(datos.decode("utf-8"))
    except (OSError, EOFError, UnicodeDecodeError, json.JSONDecodeError):
        raise _invalido("El archivo no es un respaldo de FashionStore (se espera el .json.gz que descargaste)")
    if not isinstance(contenido, dict) or contenido.get("formato") != FORMATO:
        raise _invalido("El archivo no es un respaldo de FashionStore")
    if contenido.get("version") != VERSION:
        raise _invalido(f"El respaldo es de otra versión del formato ({contenido.get('version')})")
    if contenido.get("alcance") not in ("empresa", "sistema") or not isinstance(contenido.get("tablas"), dict):
        raise _invalido("El respaldo está incompleto o dañado")
    return contenido


@dataclass
class _TablaRespaldo:
    tabla: Table
    modo: str
    filas: list[dict] = field(default_factory=list)


def _preparar(contenido: dict, alcance: str, tienda_id: Optional[int]) -> list[_TablaRespaldo]:
    """Convierte las filas a los tipos de cada columna y valida que pertenezcan al alcance."""
    conocidas = {t.name: (t, modo) for t, modo in _tablas(alcance)}
    desconocidas = set(contenido["tablas"]) - set(conocidas)
    if desconocidas:
        raise _invalido(f"El respaldo trae tablas que no son de este alcance o de esta versión: {', '.join(sorted(desconocidas))}")
    preparadas = []
    for nombre, (tabla, modo) in conocidas.items():
        datos = contenido["tablas"].get(nombre) or {"columnas": [], "filas": []}
        columnas = datos.get("columnas") or []
        sobrantes = [c for c in columnas if c not in tabla.c]
        if sobrantes:
            raise _invalido(f"La tabla {nombre} del respaldo tiene columnas que esta versión no conoce: {', '.join(sobrantes)}")
        faltantes = [
            c.name for c in tabla.columns
            if c.name not in columnas and not c.nullable and c.server_default is None and datos.get("filas")
        ]
        if faltantes:
            raise _invalido(f"A la tabla {nombre} del respaldo le faltan columnas obligatorias: {', '.join(faltantes)}")
        filas = []
        for valores in datos.get("filas") or []:
            if not isinstance(valores, list) or len(valores) != len(columnas):
                raise _invalido(f"Hay una fila dañada en la tabla {nombre}")
            try:
                fila = {c: _de_json(tabla.c[c], v) for c, v in zip(columnas, valores)}
            except (TypeError, ValueError, ArithmeticError):
                raise _invalido(f"Hay un valor inválido en la tabla {nombre}")
            if tienda_id is not None and "tienda_id" in tabla.c and fila.get("tienda_id") != tienda_id:
                raise _invalido(f"El respaldo trae filas de otra empresa (tabla {nombre})")
            if tienda_id is not None and nombre == "usuario" and fila.get("es_superadmin"):
                raise _invalido("El respaldo de una empresa no puede traer cuentas de la plataforma")
            filas.append(fila)
        preparadas.append(_TablaRespaldo(tabla, modo, filas))
    return preparadas


def _validar_referencias(db: Session, preparadas: list[_TablaRespaldo], tienda_id: int) -> None:
    """En el respaldo de una empresa, cada referencia a una fila de la empresa debe apuntar a una
    fila del mismo respaldo (o a una cuenta actual de la empresa): nada de filas de otra empresa."""
    ids: dict[str, set] = {p.tabla.name: {f.get("id") for f in p.filas} for p in preparadas if "id" in p.tabla.c}
    usuarios = next(p.tabla for p in preparadas if p.tabla.name == "usuario")
    ids["usuario"] = ids.get("usuario", set()) | set(
        db.scalars(select(usuarios.c.id).where(usuarios.c.tienda_id == tienda_id)).all()
    )
    for p in preparadas:
        for fk in p.tabla.foreign_keys:
            destino = fk.column.table.name
            if destino not in ids or fk.parent.name == "tienda_id":
                continue  # tablas globales (ciudad, permiso): las valida la base
            for fila in p.filas:
                valor = fila.get(fk.parent.name)
                if valor is not None and valor not in ids[destino]:
                    raise _invalido(
                        f"La tabla {p.tabla.name} del respaldo referencia {destino} #{valor}, que no es de esta empresa"
                    )


# --------------------------------------------------------------------------- restaurar

def _en_lotes(filas: list[dict]):
    for i in range(0, len(filas), LOTE):
        yield filas[i:i + LOTE]


def _cargar(db: Session, p: _TablaRespaldo) -> None:
    if not p.filas:
        return
    clave = [c.name for c in p.tabla.primary_key.columns]
    for lote in _en_lotes(p.filas):
        if p.modo == REEMPLAZAR:
            db.execute(p.tabla.insert(), lote)
            continue
        # Mismas columnas en todo el lote (un INSERT ... ON CONFLICT con varias filas lo exige)
        columnas = list(lote[0])
        sentencia = pg_insert(p.tabla).values([{c: f.get(c) for c in columnas} for f in lote])
        if p.modo == ANEXAR:
            sentencia = sentencia.on_conflict_do_nothing(index_elements=clave)
        else:
            sentencia = sentencia.on_conflict_do_update(
                index_elements=clave, set_={c: sentencia.excluded[c] for c in columnas if c not in clave},
            )
        db.execute(sentencia)


def _ajustar_secuencias(db: Session, tablas: list[Table]) -> None:
    """Si el respaldo viene de otra base, las secuencias quedan detrás de los ids cargados: se
    adelantan (nunca se atrasan)."""
    for tabla in tablas:
        if "id" not in tabla.c or _tipo_python(tabla.c.id) is not int:
            continue
        secuencia = db.execute(text("SELECT pg_get_serial_sequence(:t, 'id')"), {"t": tabla.name}).scalar()
        maximo = db.execute(select(func.max(tabla.c.id))).scalar() if secuencia else None
        if maximo:
            # El nombre de la secuencia lo devuelve el catálogo de Postgres (no viene del respaldo)
            db.execute(
                text(f"SELECT setval(:s, GREATEST(:m, (SELECT last_value FROM {secuencia})))"),
                {"s": secuencia, "m": maximo},
            )


def restaurar(
    db: Session,
    contenido: dict,
    *,
    alcance: str,
    tienda_id: Optional[int] = None,
    actor_id: Optional[int] = None,
    simular: bool = False,
) -> dict:
    """Restaura un respaldo ya leído. alcance "empresa" exige tienda_id (la empresa a restaurar);
    "sistema" restaura todo (sesión de la plataforma). Devuelve qué se restauró."""
    if contenido["alcance"] != alcance:
        es = "del sistema completo" if contenido["alcance"] == "sistema" else "de una empresa"
        quiere = "de una empresa" if alcance == "empresa" else "del sistema completo"
        raise _invalido(f"Este respaldo es {es}: acá se restaura uno {quiere}")
    if alcance == "empresa":
        origen = contenido.get("tienda") or {}
        if origen.get("id") != tienda_id:
            raise _invalido(
                f"El respaldo es de otra empresa ({origen.get('nombre', 'desconocida')}): solo se puede restaurar en la misma empresa"
            )
    revision_actual, revision_respaldo = _revision(db), contenido.get("revision_bd")
    if revision_actual and revision_respaldo and revision_actual != revision_respaldo:
        raise _invalido(f"El respaldo es de otra versión de la base ({revision_respaldo}); la actual es {revision_actual}")

    filtro_tienda = tienda_id if alcance == "empresa" else None
    preparadas = _preparar(contenido, alcance, filtro_tienda)
    if alcance == "empresa":
        _validar_referencias(db, preparadas, tienda_id)

    desactivados = suspendidas = 0
    try:
        for p in reversed(preparadas):
            if p.modo == REEMPLAZAR:
                db.execute(delete(p.tabla).where(*_filtro(p.tabla, filtro_tienda)))
        for p in preparadas:
            _cargar(db, p)
            ids = [f["id"] for f in p.filas if "id" in f]
            if p.modo == USUARIOS:
                condiciones = [*_filtro(p.tabla, filtro_tienda), p.tabla.c.estado.is_(True), p.tabla.c.id.not_in(ids)]
                if actor_id is not None:
                    condiciones.append(p.tabla.c.id != actor_id)
                desactivados = db.execute(
                    update(p.tabla).where(*condiciones).values(estado=False, fecha_eliminacion=datetime.now(timezone.utc))
                ).rowcount
            if p.tabla.name == "tienda":
                # Empresas dadas de alta después del respaldo: sus datos ya no están; quedan suspendidas
                suspendidas = db.execute(
                    update(p.tabla).where(p.tabla.c.id.not_in(ids), p.tabla.c.estado != "suspendida").values(estado="suspendida")
                ).rowcount
        if alcance == "sistema":
            _ajustar_secuencias(db, [p.tabla for p in preparadas])
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"No se pudo restaurar: el respaldo no es compatible con los datos actuales ({type(exc.orig).__name__}). No se cambió nada.",
        )
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo restaurar el respaldo. No se cambió nada.",
        )

    if simular:
        db.rollback()
    else:
        db.commit()
    return {
        "simulado": simular,
        "alcance": alcance,
        "empresa": (contenido.get("tienda") or {}).get("nombre"),
        "respaldo_del": contenido.get("creado_en"),
        "tablas": {p.tabla.name: len(p.filas) for p in preparadas},
        "filas": sum(len(p.filas) for p in preparadas),
        "usuarios_desactivados": desactivados,
        "empresas_suspendidas": suspendidas,
    }


def nombre_archivo(tienda: Optional[Any] = None) -> str:
    marca = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M")
    return f"respaldo_{tienda.slug if tienda is not None else 'sistema'}_{marca}.json.gz"
