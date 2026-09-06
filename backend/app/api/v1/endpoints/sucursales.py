from datetime import datetime, time, timezone
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.models.inventario import InventarioSucursal
from app.models.reserva import Reserva
from app.models.seguridad import Usuario
from app.models.sucursal import Ciudad, Sucursal
from app.schemas.sucursal import (
    CiudadCreate,
    CiudadOut,
    SucursalCreate,
    SucursalOut,
    SucursalUpdate,
)

router = APIRouter()


# --- Ciudades ---
@router.get("/ciudades", response_model=List[CiudadOut])
def listar_ciudades(db: Session = Depends(get_db)):
    """Listar todas las ciudades activas"""
    stmt = select(Ciudad).where(Ciudad.estado.is_(True), Ciudad.fecha_eliminacion.is_(None)).order_by(Ciudad.nombre)
    return list(db.scalars(stmt).all())


@router.post("/ciudades", response_model=CiudadOut, status_code=status.HTTP_201_CREATED)
def crear_ciudad(
    datos: CiudadCreate,
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_roles(["Administrador"])),
):
    """Crear una nueva ciudad"""
    existente = db.scalars(select(Ciudad).where(Ciudad.nombre == datos.nombre)).first()
    if existente:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"La ciudad '{datos.nombre}' ya existe",
        )
    nueva_ciudad = Ciudad(nombre=datos.nombre, estado=True)
    db.add(nueva_ciudad)
    db.commit()
    db.refresh(nueva_ciudad)
    return nueva_ciudad


# --- Sucursales ---
@router.get("", response_model=List[SucursalOut])
def listar_sucursales(
    ciudad_id: int | None = None,
    db: Session = Depends(get_db),
):
    """CU-06: Listado de sucursales existentes (accesible por clientes y administradores)"""
    stmt = select(Sucursal).where(Sucursal.estado.is_(True), Sucursal.fecha_eliminacion.is_(None))
    if ciudad_id:
        stmt = stmt.where(Sucursal.ciudad_id == ciudad_id)
    sucursales = db.scalars(stmt.order_by(Sucursal.id)).all()

    resultado = []
    for s in sucursales:
        ciudad = db.get(Ciudad, s.ciudad_id)
        resultado.append(
            SucursalOut(
                id=s.id,
                nombre=s.nombre,
                ciudad_id=s.ciudad_id,
                direccion=s.direccion,
                telefono=s.telefono,
                hora_inicio=s.hora_inicio,
                hora_fin=s.hora_fin,
                estado=s.estado,
                ciudad_nombre=ciudad.nombre if ciudad else None,
            )
        )
    return resultado


@router.get("/{sucursal_id}", response_model=SucursalOut)
def obtener_sucursal(sucursal_id: int, db: Session = Depends(get_db)):
    """Obtener detalle de una sucursal por su ID"""
    sucursal = db.get(Sucursal, sucursal_id)
    if not sucursal or sucursal.fecha_eliminacion is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sucursal no encontrada")

    ciudad = db.get(Ciudad, sucursal.ciudad_id)
    return SucursalOut(
        id=sucursal.id,
        nombre=sucursal.nombre,
        ciudad_id=sucursal.ciudad_id,
        direccion=sucursal.direccion,
        telefono=sucursal.telefono,
        hora_inicio=sucursal.hora_inicio,
        hora_fin=sucursal.hora_fin,
        estado=sucursal.estado,
        ciudad_nombre=ciudad.nombre if ciudad else None,
    )


@router.post("", response_model=SucursalOut, status_code=status.HTTP_201_CREATED)
def crear_sucursal(
    datos: SucursalCreate,
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_roles(["Administrador"])),
):
    """CU-06: Registrar nueva sucursal con ciudad, dirección y horarios"""
    ciudad = db.get(Ciudad, datos.ciudad_id)
    if not ciudad or not ciudad.estado:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La ciudad especificada no es válida")

    def parse_time(val):
        if val is None or isinstance(val, time):
            return val
        return time.fromisoformat(str(val))

    nueva = Sucursal(
        nombre=datos.nombre,
        ciudad_id=datos.ciudad_id,
        direccion=datos.direccion,
        telefono=datos.telefono,
        hora_inicio=parse_time(datos.hora_inicio),
        hora_fin=parse_time(datos.hora_fin),
        estado=True,
    )
    db.add(nueva)
    db.commit()
    db.refresh(nueva)

    return SucursalOut(
        id=nueva.id,
        nombre=nueva.nombre,
        ciudad_id=nueva.ciudad_id,
        direccion=nueva.direccion,
        telefono=nueva.telefono,
        hora_inicio=nueva.hora_inicio,
        hora_fin=nueva.hora_fin,
        estado=nueva.estado,
        ciudad_nombre=ciudad.nombre,
    )


@router.put("/{sucursal_id}", response_model=SucursalOut)
def actualizar_sucursal(
    sucursal_id: int,
    datos: SucursalUpdate,
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_roles(["Administrador"])),
):
    """CU-06: Editar información de una sucursal existente"""
    sucursal = db.get(Sucursal, sucursal_id)
    if not sucursal or sucursal.fecha_eliminacion is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sucursal no encontrada")

    if datos.ciudad_id is not None:
        ciudad = db.get(Ciudad, datos.ciudad_id)
        if not ciudad or not ciudad.estado:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ciudad inválida")
        sucursal.ciudad_id = datos.ciudad_id

    if datos.nombre is not None:
        sucursal.nombre = datos.nombre
    if datos.direccion is not None:
        sucursal.direccion = datos.direccion
    if datos.telefono is not None:
        sucursal.telefono = datos.telefono

    def parse_time(val):
        if val is None or isinstance(val, time):
            return val
        return time.fromisoformat(str(val))

    if datos.hora_inicio is not None:
        sucursal.hora_inicio = parse_time(datos.hora_inicio)
    if datos.hora_fin is not None:
        sucursal.hora_fin = parse_time(datos.hora_fin)
    if datos.estado is not None:
        sucursal.estado = datos.estado

    db.commit()
    db.refresh(sucursal)

    ciudad = db.get(Ciudad, sucursal.ciudad_id)
    return SucursalOut(
        id=sucursal.id,
        nombre=sucursal.nombre,
        ciudad_id=sucursal.ciudad_id,
        direccion=sucursal.direccion,
        telefono=sucursal.telefono,
        hora_inicio=sucursal.hora_inicio,
        hora_fin=sucursal.hora_fin,
        estado=sucursal.estado,
        ciudad_nombre=ciudad.nombre if ciudad else None,
    )


@router.delete("/{sucursal_id}")
def eliminar_sucursal(
    sucursal_id: int,
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_roles(["Administrador"])),
):
    """CU-06: Desactivar una sucursal con validación de reservas o inventario activo"""
    sucursal = db.get(Sucursal, sucursal_id)
    if not sucursal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sucursal no encontrada")

    # Excepción CU-06: Advertir / validar si hay reservas pendientes o inventario activo
    reservas_activas = db.scalars(
        select(Reserva).where(
            Reserva.sucursal_id == sucursal_id,
            Reserva.estado.in_(["pendiente", "confirmada"]),
        )
    ).all()
    if reservas_activas:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se puede desactivar la sucursal porque tiene {len(reservas_activas)} reserva(s) activa(s)",
        )

    inventario_activo = db.scalars(
        select(InventarioSucursal).where(
            InventarioSucursal.sucursal_id == sucursal_id,
            InventarioSucursal.stock_disponible > 0,
        )
    ).all()
    if inventario_activo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La sucursal tiene inventario con stock disponible. Debe transferirlo antes de darla de baja.",
        )

    sucursal.estado = False
    sucursal.fecha_eliminacion = datetime.now(timezone.utc)
    db.commit()
    return {"message": f"Sucursal '{sucursal.nombre}' desactivada correctamente"}

