"""La última unidad: varios pedidos simultáneos por la misma prenda (hilos de verdad contra
Postgres). Siempre uno solo se la lleva, el stock nunca queda negativo y nada se devuelve dos
veces. Ver app/services/inventario_service.py."""
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import Callable
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text

from app.core.config import settings
from app.core.security import get_password_hash
from app.db.session import SessionLocal, engine
from app.db.tenancy import CLAVE_TIENDA
from app.main import app
from app.models.catalogo import Categoria, Color, Prenda, Talla, VariantePrenda
from app.models.inventario import InventarioSucursal
from app.models.reserva import DetalleReserva
from app.models.seguridad import Rol, Usuario, UsuarioRol
from app.models.sucursal import Ciudad, Personal, Sucursal
from app.models.venta import Venta
from app.services.inventario_service import liberar_apartados_vencidos
from app.services.tiendas_service import crear_tienda

PASSWORD = "ClaveSegura123*"
SIMULTANEOS = 8


@pytest.fixture(scope="module")
def tienda(borrar_tienda):
    marca = int(time.time() * 1000)
    datos = {"slug": f"conc-{marca}"}
    with SessionLocal() as db:
        datos["id"] = crear_tienda(
            db, slug=datos["slug"], nombre="Tienda Concurrida", correo_admin=f"admin{marca}@conc.com", password_admin=PASSWORD
        ).id

    ahora = datetime.now(timezone.utc)
    with SessionLocal(info={CLAVE_TIENDA: datos["id"]}) as db:
        ciudad = db.scalars(select(Ciudad).order_by(Ciudad.id)).first()
        sucursal = Sucursal(nombre=f"Única {marca}", ciudad_id=ciudad.id, direccion="Calle 1", estado=True)
        categoria, talla, color = Categoria(nombre="Camperas", estado=True), Talla(nombre="M"), Color(nombre="Azul")
        db.add_all([sucursal, categoria, talla, color])
        db.flush()
        roles = {r.nombre: r for r in db.scalars(select(Rol))}
        for clave, rol, personal in [("cliente1", "Cliente", False), ("cliente2", "Cliente", False), ("encargado", "Encargado", True), ("cajero", "Cajero", True)]:
            usuario = Usuario(correo=f"{clave}{marca}@conc.com", password_hash=get_password_hash(PASSWORD), estado=True, creado_en=ahora)
            db.add(usuario)
            db.flush()
            db.add(UsuarioRol(usuario_id=usuario.id, rol_id=roles[rol].id))
            if personal:
                db.add(Personal(usuario_id=usuario.id, sucursal_id=sucursal.id, nombres=clave, apellidos="Prueba", cargo=rol, estado=True))
            datos[clave] = usuario.correo
        prenda = Prenda(nombre="Campera única", categoria_id=categoria.id, precio_base=100, estado=True)
        db.add(prenda)
        db.flush()
        variante = VariantePrenda(prenda_id=prenda.id, talla_id=talla.id, color_id=color.id, codigo_barras=f"C{marca}", estado=True)
        db.add(variante)
        db.flush()
        db.add(InventarioSucursal(variante_id=variante.id, sucursal_id=sucursal.id, stock_disponible=0, stock_reservado=0, stock_minimo=0))
        datos.update(sucursal=sucursal.id, variante=variante.id)
        db.commit()

    cliente = TestClient(app)
    datos["tokens"] = {}
    for clave in ("cliente1", "cliente2", "encargado", "cajero"):
        res = cliente.post("/api/v1/auth/login", json={"login": datos[clave], "password": PASSWORD}, headers={"X-Tienda": datos["slug"]})
        assert res.status_code == 200, res.text
        datos["tokens"][clave] = res.json()["access_token"]
    yield datos
    borrar_tienda(datos["id"])


@pytest.fixture(autouse=True)
def libelula_de_prueba(monkeypatch):
    monkeypatch.setattr(settings, "libelula_appkey", "")  # QR de demostración, sin la API real


def _en(t: dict, quien: str) -> dict:
    return {"X-Tienda": t["slug"], "Authorization": f"Bearer {t['tokens'][quien]}"}


def _poner_stock(t: dict, disponible: int) -> None:
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE inventario_sucursal SET stock_disponible = :d, stock_reservado = 0 WHERE variante_id = :v AND sucursal_id = :s"),
            {"d": disponible, "v": t["variante"], "s": t["sucursal"]},
        )


def _stock(t: dict) -> tuple[int, int]:
    with engine.connect() as conn:
        return tuple(conn.execute(
            text("SELECT stock_disponible, stock_reservado FROM inventario_sucursal WHERE variante_id = :v AND sucursal_id = :s"),
            {"v": t["variante"], "s": t["sucursal"]},
        ).one())


def _a_la_vez(*pedidos: Callable[[TestClient], object]) -> list:
    """Lanza los pedidos en hilos que arrancan juntos (cada uno con su cliente HTTP)."""
    barrera = threading.Barrier(len(pedidos))

    def correr(pedido):
        cliente = TestClient(app)
        barrera.wait()
        return pedido(cliente)

    with ThreadPoolExecutor(len(pedidos)) as pool:
        return list(pool.map(correr, pedidos))


def _reservar(t: dict, quien: str = "cliente1") -> Callable[[TestClient], object]:
    cuerpo = {"sucursal_id": t["sucursal"], "detalles": [{"variante_id": t["variante"], "cantidad": 1}]}
    return lambda cliente: cliente.post("/api/v1/reservas", json=cuerpo, headers=_en(t, quien))


def _venta_digital(t: dict, quien: str) -> int:
    res = TestClient(app).post(
        "/api/v1/ventas/digital",
        json={"sucursal_id": t["sucursal"], "detalles": [{"variante_id": t["variante"], "cantidad": 1}]},
        headers=_en(t, quien),
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _generar_qr(t: dict, venta_id: int, quien: str) -> Callable[[TestClient], object]:
    return lambda cliente: cliente.post(f"/api/v1/ventas/{venta_id}/qr-libelula", headers=_en(t, quien))


def test_varias_reservas_simultaneas_de_la_ultima_unidad_solo_una_gana(tienda):
    _poner_stock(tienda, 1)

    respuestas = _a_la_vez(*[_reservar(tienda) for _ in range(SIMULTANEOS)])

    codigos = sorted(r.status_code for r in respuestas)
    assert codigos == [201] + [400] * (SIMULTANEOS - 1), [r.text for r in respuestas if r.status_code not in (201, 400)]
    assert _stock(tienda) == (0, 1)
    with SessionLocal(info={CLAVE_TIENDA: tienda["id"]}) as db:
        ganadora = next(r.json()["id"] for r in respuestas if r.status_code == 201)
        reservadas = db.scalar(select(func.sum(DetalleReserva.cantidad)).where(DetalleReserva.reserva_id == ganadora))
        assert reservadas == 1


def test_cancelar_y_marcar_no_show_a_la_vez_devuelve_el_stock_una_sola_vez(tienda):
    _poner_stock(tienda, 1)
    reserva = _reservar(tienda)(TestClient(app)).json()["id"]
    assert _stock(tienda) == (0, 1)

    cancelar, no_show = _a_la_vez(
        lambda c: c.post(f"/api/v1/reservas/{reserva}/cancelar", headers=_en(tienda, "cliente1")),
        lambda c: c.post(f"/api/v1/reservas/{reserva}/no-show", headers=_en(tienda, "encargado")),
    )

    assert sorted([cancelar.status_code, no_show.status_code]) == [200, 400]
    assert _stock(tienda) == (1, 0)


def test_dos_clientes_pagando_la_ultima_unidad_solo_uno_llega_a_pagar(tienda):
    _poner_stock(tienda, 1)
    venta_1, venta_2 = _venta_digital(tienda, "cliente1"), _venta_digital(tienda, "cliente2")  # los dos la tienen en el carrito

    qr_1, qr_2 = _a_la_vez(_generar_qr(tienda, venta_1, "cliente1"), _generar_qr(tienda, venta_2, "cliente2"))

    assert sorted([qr_1.status_code, qr_2.status_code]) == [200, 400]
    perdedor = qr_2 if qr_1.status_code == 200 else qr_1
    assert "stock" in perdedor.json()["detail"]
    assert _stock(tienda) == (0, 1)  # apartada para el que está pagando

    ganador, quien = (venta_1, "cliente1") if qr_1.status_code == 200 else (venta_2, "cliente2")
    assert qr_1.json().get("apartado_hasta") or qr_2.json().get("apartado_hasta")
    pagada = TestClient(app).post(f"/api/v1/ventas/{ganador}/qr-libelula/simular-pago", headers=_en(tienda, quien))
    assert pagada.status_code == 200 and pagada.json()["estado"] == "pagada"
    assert _stock(tienda) == (0, 0)  # salió de lo apartado, no se descontó dos veces


def test_volver_a_generar_el_qr_no_aparta_dos_veces(tienda):
    _poner_stock(tienda, 2)
    venta = _venta_digital(tienda, "cliente1")

    respuestas = _a_la_vez(*[_generar_qr(tienda, venta, "cliente1") for _ in range(3)])  # triple clic

    assert all(r.status_code == 200 for r in respuestas), [r.text for r in respuestas]
    assert _stock(tienda) == (1, 1)


def test_el_apartado_de_un_pago_que_no_se_completa_vuelve_al_stock(tienda):
    _poner_stock(tienda, 1)
    abandonada, otra = _venta_digital(tienda, "cliente1"), _venta_digital(tienda, "cliente2")
    assert _generar_qr(tienda, abandonada, "cliente1")(TestClient(app)).status_code == 200
    assert _generar_qr(tienda, otra, "cliente2")(TestClient(app)).status_code == 400  # está apartada

    with engine.begin() as conn:  # pasaron los minutos del apartado sin que se pague
        conn.execute(text("UPDATE venta SET apartado_hasta = now() - interval '1 minute' WHERE id = :v"), {"v": abandonada})
    assert liberar_apartados_vencidos() >= 1

    assert _stock(tienda) == (1, 0)
    with SessionLocal(info={CLAVE_TIENDA: tienda["id"]}) as db:
        assert db.get(Venta, abandonada).apartado_hasta is None
    assert _generar_qr(tienda, otra, "cliente2")(TestClient(app)).status_code == 200
    assert _generar_qr(tienda, abandonada, "cliente1")(TestClient(app)).status_code == 400


def test_ventas_offline_simultaneas_de_la_ultima_unidad(tienda):
    _poner_stock(tienda, 1)
    registrada = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()

    def lote(cliente: TestClient):
        op = {
            "id": str(uuid4()), "tipo": "venta", "tienda": tienda["slug"], "sucursal_id": tienda["sucursal"],
            "registrada_en": registrada, "datos": {"detalles": [{"variante_id": tienda["variante"], "cantidad": 1, "precio_unitario": 100}], "total": 100},
        }
        return cliente.post("/api/v1/sync/operaciones", json={"operaciones": [op]}, headers=_en(tienda, "cajero"))

    respuestas = _a_la_vez(lote, lote)

    estados = sorted(r.json()["resultados"][0]["estado"] for r in respuestas)
    assert estados == ["confirmada", "conflicto"]
    assert _stock(tienda) == (0, 0)
