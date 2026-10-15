"""Cierre de una venta pagada (descuento de stock). Corre sobre SQLite en memoria, sin tocar la
base compartida: SQLite ignora el FOR UPDATE, así que esto prueba la lógica del cierre; el
bloqueo de filas lo hace Postgres en producción."""
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import app.main  # noqa: F401  (registra todos los modelos para configurar las relaciones)
from app.api.v1.endpoints.ventas import _cerrar_venta_pagada, _venta_pendiente_bloqueada
from app.db.session import Base
from app.models.enums import CanalVenta, EstadoVenta
from app.models.inventario import InventarioSucursal, MovimientoInventario
from app.models.venta import DetalleVenta, Pago, Venta

AHORA = datetime(2026, 10, 15, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    tablas = [t.__table__ for t in (Venta, DetalleVenta, Pago, InventarioSucursal, MovimientoInventario)]
    Base.metadata.create_all(engine, tables=tablas)
    with Session(engine) as sesion:
        yield sesion


def _venta_con_stock(db: Session, stock: int, cantidad: int, estado=EstadoVenta.pendiente) -> Venta:
    venta = Venta(
        sucursal_id=1, tipo_origen=CanalVenta.presencial, estado=estado, total=100, fecha_venta=AHORA
    )
    db.add(venta)
    db.flush()
    db.add(DetalleVenta(venta_id=venta.id, variante_id=7, cantidad=cantidad, precio_unitario=50, subtotal=50 * cantidad))
    db.add(InventarioSucursal(variante_id=7, sucursal_id=1, stock_disponible=stock, stock_reservado=0, stock_minimo=0))
    db.commit()
    return venta


def _stock(db: Session) -> int:
    return db.query(InventarioSucursal).filter_by(variante_id=7, sucursal_id=1).one().stock_disponible


def test_descuenta_stock_registra_kardex_y_marca_pagada(db):
    venta = _venta_con_stock(db, stock=5, cantidad=2)

    _cerrar_venta_pagada(db, venta, usuario_id=None, ahora=AHORA, exigir_stock=True)
    db.commit()

    assert _stock(db) == 3
    assert venta.estado == EstadoVenta.pagada
    movimiento = db.query(MovimientoInventario).one()
    assert (movimiento.cantidad, movimiento.referencia_id, movimiento.referencia_tipo) == (2, venta.id, "venta_presencial")


def test_caja_sin_stock_suficiente_rechaza_y_no_toca_nada(db):
    venta_id = _venta_con_stock(db, stock=1, cantidad=2).id
    venta = db.get(Venta, venta_id)

    with pytest.raises(HTTPException) as error:
        _cerrar_venta_pagada(db, venta, usuario_id=None, ahora=AHORA, exigir_stock=True)

    assert error.value.status_code == 409
    assert _stock(db) == 1
    assert db.get(Venta, venta_id).estado == EstadoVenta.pendiente
    assert db.query(MovimientoInventario).count() == 0


def test_pago_ya_cobrado_cierra_la_venta_aunque_falte_stock(db):
    # Tarjeta o QR: el cliente ya pagó, la venta se cierra igual y el stock no queda negativo
    venta = _venta_con_stock(db, stock=1, cantidad=2)

    _cerrar_venta_pagada(db, venta, usuario_id=None, ahora=AHORA)
    db.commit()

    assert _stock(db) == 0
    assert venta.estado == EstadoVenta.pagada


@pytest.mark.parametrize("estado", [EstadoVenta.pagada, EstadoVenta.anulada])
def test_no_se_vuelve_a_cobrar_una_venta_pagada_o_anulada(db, estado):
    venta_id = _venta_con_stock(db, stock=5, cantidad=1, estado=estado).id

    assert _venta_pendiente_bloqueada(db, venta_id) is None


def test_venta_pendiente_se_puede_cobrar(db):
    venta_id = _venta_con_stock(db, stock=5, cantidad=1).id

    assert _venta_pendiente_bloqueada(db, venta_id).id == venta_id
