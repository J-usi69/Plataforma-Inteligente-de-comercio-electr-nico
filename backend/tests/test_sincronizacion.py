"""Operación sin conexión: reglas críticas de la sincronización (idempotencia, integridad del
inventario, conflictos, cambios de prendas dentro del plazo, autorización por sucursal y
aislamiento entre empresas). Cada test fija el stock que necesita en una tienda desechable."""
import time
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text

from app.core.security import get_password_hash
from app.db.session import SessionLocal, engine
from app.db.tenancy import CLAVE_TIENDA, buscar_tienda, olvidar_tienda
from app.main import app
from app.models.catalogo import Categoria, Color, Prenda, Talla, VariantePrenda
from app.models.inventario import InventarioSucursal, MovimientoInventario
from app.models.seguridad import Rol, Usuario, UsuarioRol
from app.models.sincronizacion import CambioPrenda
from app.models.sucursal import Ciudad, Personal, Sucursal
from app.models.venta import Pago
from app.services.tiendas_service import crear_tienda

client = TestClient(app)
PASSWORD = "ClaveSegura123*"


def _token(correo: str, slug: str) -> str:
    res = client.post("/api/v1/auth/login", json={"login": correo, "password": PASSWORD}, headers={"X-Tienda": slug})
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


@pytest.fixture(scope="module")
def tienda(borrar_tienda):
    """Dos sucursales (cajero y encargado en la A), un cliente y tres variantes:
    v1 y v2 = Polera (Bs. 100, M y L), v3 = Campera (Bs. 150)."""
    marca = int(time.time() * 1000)
    datos = {"slug": f"sync-{marca}", "admin": f"admin{marca}@sync.com"}
    with SessionLocal() as db:
        datos["id"] = crear_tienda(
            db, slug=datos["slug"], nombre="Tienda Offline", correo_admin=datos["admin"], password_admin=PASSWORD
        ).id

    ahora = datetime.now(timezone.utc)
    with SessionLocal(info={CLAVE_TIENDA: datos["id"]}) as db:
        ciudad = db.scalars(select(Ciudad).order_by(Ciudad.id)).first()
        sucursal_a = Sucursal(nombre=f"Centro {marca}", ciudad_id=ciudad.id, direccion="Calle 1", estado=True)
        sucursal_b = Sucursal(nombre=f"Norte {marca}", ciudad_id=ciudad.id, direccion="Calle 2", estado=True)
        db.add_all([sucursal_a, sucursal_b])
        db.flush()
        roles = {r.nombre: r for r in db.scalars(select(Rol))}

        def usuario(clave: str, rol: str, sucursal: Sucursal | None = None) -> Usuario:
            nuevo = Usuario(correo=f"{clave}{marca}@sync.com", password_hash=get_password_hash(PASSWORD), estado=True, creado_en=ahora)
            db.add(nuevo)
            db.flush()
            db.add(UsuarioRol(usuario_id=nuevo.id, rol_id=roles[rol].id))
            if sucursal:
                db.add(Personal(usuario_id=nuevo.id, sucursal_id=sucursal.id, nombres=clave.title(), apellidos="Prueba", cargo=rol, estado=True))
            datos[clave] = nuevo.correo
            return nuevo

        cliente = usuario("cliente", "Cliente")
        usuario("cajero", "Cajero", sucursal_a)
        usuario("encargado", "Encargado", sucursal_a)

        categoria, talla_m, talla_l = Categoria(nombre="Poleras", estado=True), Talla(nombre="M"), Talla(nombre="L")
        color = Color(nombre="Negro", hex="#111111")
        db.add_all([categoria, talla_m, talla_l, color])
        db.flush()
        polera = Prenda(nombre="Polera básica", categoria_id=categoria.id, precio_base=100, estado=True)
        campera = Prenda(nombre="Campera liviana", categoria_id=categoria.id, precio_base=150, estado=True)
        db.add_all([polera, campera])
        db.flush()
        variantes = [
            VariantePrenda(prenda_id=polera.id, talla_id=talla_m.id, color_id=color.id, codigo_barras=f"S{marca}1", estado=True),
            VariantePrenda(prenda_id=polera.id, talla_id=talla_l.id, color_id=color.id, codigo_barras=f"S{marca}2", estado=True),
            VariantePrenda(prenda_id=campera.id, talla_id=talla_m.id, color_id=color.id, codigo_barras=f"S{marca}3", estado=True),
        ]
        db.add_all(variantes)
        db.flush()
        datos.update(
            sucursal_a=sucursal_a.id, sucursal_b=sucursal_b.id, cliente_id=cliente.id,
            v1=variantes[0].id, v2=variantes[1].id, v3=variantes[2].id,
        )
        db.commit()

    datos["tokens"] = {rol: _token(datos[rol], datos["slug"]) for rol in ("admin", "cajero", "encargado", "cliente")}
    yield datos
    borrar_tienda(datos["id"])


def _en(t: dict, rol: str | None = None) -> dict:
    headers = {"X-Tienda": t["slug"]}
    if rol:
        headers["Authorization"] = f"Bearer {t['tokens'][rol]}"
    return headers


def _poner_stock(t: dict, variante: int, sucursal: int, cantidad: int) -> None:
    with SessionLocal(info={CLAVE_TIENDA: t["id"]}) as db:
        fila = db.scalars(
            select(InventarioSucursal).where(InventarioSucursal.variante_id == variante, InventarioSucursal.sucursal_id == sucursal)
        ).first()
        if fila is None:
            fila = InventarioSucursal(variante_id=variante, sucursal_id=sucursal, stock_minimo=0)
            db.add(fila)
        fila.stock_disponible, fila.stock_reservado = cantidad, 0
        db.commit()


def _stock(t: dict, variante: int, sucursal: int) -> tuple[int, int]:
    with SessionLocal(info={CLAVE_TIENDA: t["id"]}) as db:
        fila = db.scalars(
            select(InventarioSucursal).where(InventarioSucursal.variante_id == variante, InventarioSucursal.sucursal_id == sucursal)
        ).first()
        return (fila.stock_disponible, fila.stock_reservado) if fila else (0, 0)


def _kardex_de_venta(t: dict, venta_id: int) -> list[tuple[str, int]]:
    with SessionLocal(info={CLAVE_TIENDA: t["id"]}) as db:
        movimientos = db.scalars(
            select(MovimientoInventario).where(
                MovimientoInventario.referencia_id == venta_id,
                MovimientoInventario.referencia_tipo.in_(["venta_offline", "faltante_sync"]),
            )
        ).all()
        return sorted((m.referencia_tipo, m.cantidad) for m in movimientos)


def _op(t: dict, tipo: str, datos: dict, sucursal: int | None = None, hace: timedelta = timedelta(minutes=10), **cambios) -> dict:
    op = {
        "id": str(uuid4()),
        "tipo": tipo,
        "tienda": t["slug"],
        "sucursal_id": sucursal or t["sucursal_a"],
        "registrada_en": (datetime.now(timezone.utc) - hace).isoformat(),
        "dispositivo": "pytest",
        "datos": datos,
    }
    op.update(cambios)
    return op


def _venta(t: dict, variante: int, cantidad: int, precio: float = 100.0, **kwargs) -> dict:
    datos = {"detalles": [{"variante_id": variante, "cantidad": cantidad, "precio_unitario": precio}], "total": round(precio * cantidad, 2)}
    return _op(t, "venta", datos, **kwargs)


def _cambio(t: dict, devuelve: list[tuple[int, int]], entrega: list[tuple[int, int, float]], diferencia: float, **origen) -> dict:
    datos = {
        "devuelve": [{"variante_id": v, "cantidad": c} for v, c in devuelve],
        "entrega": [{"variante_id": v, "cantidad": c, "precio_unitario": p} for v, c, p in entrega],
        "diferencia": diferencia,
        **origen,
    }
    return _op(t, "cambio", datos, hace=timedelta(minutes=5))


def _enviar(t: dict, rol: str, *ops: dict) -> list[dict]:
    res = client.post("/api/v1/sync/operaciones", json={"operaciones": list(ops)}, headers=_en(t, rol))
    assert res.status_code == 200, res.text
    return res.json()["resultados"]


def _resolver(t: dict, op_id: str, accion: str, rol: str = "encargado"):
    return client.post(f"/api/v1/sync/operaciones/{op_id}/resolver", json={"accion": accion, "nota": "test"}, headers=_en(t, rol))


# ------------------------------------------------------------------------------
# Ventas
# ------------------------------------------------------------------------------
def test_la_venta_offline_se_confirma_descuenta_stock_y_conserva_la_hora_de_la_tienda(tienda):
    _poner_stock(tienda, tienda["v1"], tienda["sucursal_a"], 5)
    op = _venta(tienda, tienda["v1"], 2, hace=timedelta(hours=2))
    op["datos"]["monto_recibido"] = 250

    [resultado] = _enviar(tienda, "cajero", op)

    assert (resultado["estado"], resultado["referencia_tipo"], resultado["duplicada"]) == ("confirmada", "venta", False)
    assert _stock(tienda, tienda["v1"], tienda["sucursal_a"]) == (3, 0)
    venta = client.get(f"/api/v1/ventas/{resultado['referencia_id']}", headers=_en(tienda, "cajero")).json()
    assert (venta["estado"], venta["total"], venta["pagos"][0]["metodo_pago"]) == ("pagada", 200.0, "efectivo")
    # La venta queda con la hora en que se hizo en la tienda, no con la de la sincronización
    registrada = datetime.fromisoformat(op["registrada_en"])
    assert abs(datetime.fromisoformat(venta["fecha_venta"]) - registrada) < timedelta(seconds=1)
    assert _kardex_de_venta(tienda, venta["id"]) == [("venta_offline", 2)]


def test_reenviar_una_operacion_no_la_duplica(tienda):
    _poner_stock(tienda, tienda["v1"], tienda["sucursal_a"], 5)
    op = _venta(tienda, tienda["v1"], 1)

    primero, repetido_en_el_lote = _enviar(tienda, "cajero", op, op)
    [reenvio] = _enviar(tienda, "cajero", op)  # p. ej. se cortó la respuesta y el dispositivo reintenta

    assert primero["estado"] == "confirmada" and not primero["duplicada"]
    assert repetido_en_el_lote["duplicada"] and reenvio["duplicada"]
    assert repetido_en_el_lote["referencia_id"] == reenvio["referencia_id"] == primero["referencia_id"]
    assert _stock(tienda, tienda["v1"], tienda["sucursal_a"]) == (4, 0)
    with SessionLocal(info={CLAVE_TIENDA: tienda["id"]}) as db:
        assert len(db.scalars(select(Pago).where(Pago.transaccion_id == f"OFFLINE-{op['id']}")).all()) == 1
    panel = client.get("/api/v1/sync/operaciones", headers=_en(tienda, "admin")).json()
    assert next(o for o in panel if o["id"] == op["id"])["intentos"] == 3


def test_el_mismo_id_con_otro_contenido_no_pisa_lo_guardado(tienda):
    _poner_stock(tienda, tienda["v1"], tienda["sucursal_a"], 5)
    op = _venta(tienda, tienda["v1"], 1)
    [original] = _enviar(tienda, "cajero", op)
    alterada = {**op, "datos": {**op["datos"], "detalles": [{"variante_id": tienda["v1"], "cantidad": 3, "precio_unitario": 100}], "total": 300}}

    [resultado] = _enviar(tienda, "cajero", alterada)

    assert (resultado["estado"], resultado["codigo"]) == ("rechazada", "id_repetido")
    estado = client.get("/api/v1/sync/estado", params={"ids": [op["id"]]}, headers=_en(tienda, "cajero")).json()
    assert estado["resultados"][0]["referencia_id"] == original["referencia_id"]
    assert _stock(tienda, tienda["v1"], tienda["sucursal_a"]) == (4, 0)


def test_sin_stock_suficiente_la_venta_queda_en_conflicto_y_el_encargado_la_acepta(tienda):
    _poner_stock(tienda, tienda["v2"], tienda["sucursal_a"], 1)
    op = _venta(tienda, tienda["v2"], 3)

    [resultado] = _enviar(tienda, "cajero", op)

    assert (resultado["estado"], resultado["codigo"], resultado["referencia_id"]) == ("conflicto", "sin_stock", None)
    assert _stock(tienda, tienda["v2"], tienda["sucursal_a"]) == (1, 0)  # no se aplicó nada
    conflictos = client.get("/api/v1/sync/operaciones", params={"estado": "conflicto"}, headers=_en(tienda, "encargado")).json()
    assert op["id"] in [o["id"] for o in conflictos]

    aceptada = _resolver(tienda, op["id"], "aceptar")
    assert aceptada.status_code == 200, aceptada.text
    assert (aceptada.json()["estado"], aceptada.json()["referencia_tipo"]) == ("confirmada", "venta")
    assert aceptada.json()["resuelta_por_correo"] == tienda["encargado"]
    # El stock no queda negativo: el faltante entra como ajuste en el kardex
    assert _stock(tienda, tienda["v2"], tienda["sucursal_a"]) == (0, 0)
    assert _kardex_de_venta(tienda, aceptada.json()["referencia_id"]) == [("faltante_sync", 2), ("venta_offline", 3)]

    assert _resolver(tienda, op["id"], "aceptar").status_code == 409  # ya resuelta: no se registra dos veces
    estado = client.get("/api/v1/sync/estado", params={"ids": [op["id"]]}, headers=_en(tienda, "cajero")).json()
    assert estado["resultados"][0]["estado"] == "confirmada"


def test_el_encargado_puede_rechazar_un_conflicto(tienda):
    _poner_stock(tienda, tienda["v2"], tienda["sucursal_a"], 0)
    op = _venta(tienda, tienda["v2"], 1)
    _enviar(tienda, "cajero", op)

    rechazada = _resolver(tienda, op["id"], "rechazar")

    assert rechazada.status_code == 200
    assert (rechazada.json()["estado"], rechazada.json()["referencia_id"]) == ("rechazada", None)
    assert _resolver(tienda, op["id"], "aceptar", rol="cajero").status_code == 403  # el cajero no resuelve


def test_cada_operacion_del_lote_se_resuelve_por_separado(tienda):
    _poner_stock(tienda, tienda["v1"], tienda["sucursal_a"], 5)
    fashionstore = buscar_tienda("fashionstore")
    with SessionLocal(info={CLAVE_TIENDA: fashionstore.id}) as db:
        variante_ajena = db.scalars(select(VariantePrenda.id)).first()
    total_mal = _venta(tienda, tienda["v1"], 1)
    total_mal["datos"]["total"] = 80

    resultados = _enviar(
        tienda, "cajero",
        _venta(tienda, tienda["v1"], 1),
        _venta(tienda, variante_ajena, 1),  # prenda de otra empresa
        total_mal,
        _venta(tienda, tienda["v1"], 1, tienda="fashionstore"),
        _op(tienda, "devolucion", {}),
        _op(tienda, "venta", {"detalles": []}),
        _venta(tienda, tienda["v1"], 1, hace=-timedelta(days=1)),  # reloj del dispositivo adelantado
    )

    assert [(r["estado"], r["codigo"]) for r in resultados] == [
        ("confirmada", None),
        ("rechazada", "variante_invalida"),
        ("rechazada", "total_inconsistente"),
        ("rechazada", "otra_empresa"),
        ("rechazada", "tipo_desconocido"),
        ("rechazada", "datos_invalidos"),
        ("rechazada", "fecha_futura"),
    ]
    assert _stock(tienda, tienda["v1"], tienda["sucursal_a"]) == (4, 0)


def test_el_personal_opera_solo_en_su_sucursal_y_el_admin_en_cualquiera(tienda):
    _poner_stock(tienda, tienda["v1"], tienda["sucursal_b"], 2)

    [del_cajero] = _enviar(tienda, "cajero", _venta(tienda, tienda["v1"], 1, sucursal=tienda["sucursal_b"]))
    [del_admin] = _enviar(tienda, "admin", _venta(tienda, tienda["v1"], 1, sucursal=tienda["sucursal_b"]))

    assert (del_cajero["estado"], del_cajero["codigo"]) == ("rechazada", "sucursal_no_autorizada")
    assert del_admin["estado"] == "confirmada"
    assert _stock(tienda, tienda["v1"], tienda["sucursal_b"]) == (1, 0)


# ------------------------------------------------------------------------------
# Reservas
# ------------------------------------------------------------------------------
def test_un_cliente_reserva_para_si_pero_no_registra_ventas(tienda):
    _poner_stock(tienda, tienda["v1"], tienda["sucursal_a"], 3)
    reserva = _op(tienda, "reserva", {"detalles": [{"variante_id": tienda["v1"], "cantidad": 1}]})
    para_otro = _op(tienda, "reserva", {"cliente_id": tienda["cliente_id"] + 999, "detalles": [{"variante_id": tienda["v1"], "cantidad": 1}]})

    venta, reservada, ajena = _enviar(tienda, "cliente", _venta(tienda, tienda["v1"], 1), reserva, para_otro)

    assert (venta["estado"], venta["codigo"]) == ("rechazada", "sin_permiso")
    assert (reservada["estado"], reservada["referencia_tipo"]) == ("confirmada", "reserva")
    assert (ajena["estado"], ajena["codigo"]) == ("rechazada", "sin_permiso")
    assert _stock(tienda, tienda["v1"], tienda["sucursal_a"]) == (2, 1)
    mias = client.get("/api/v1/reservas", headers=_en(tienda, "cliente")).json()
    assert reservada["referencia_id"] in [r["id"] for r in mias]


def test_la_reserva_del_personal_exige_cliente_y_sin_stock_se_rechaza(tienda):
    _poner_stock(tienda, tienda["v3"], tienda["sucursal_a"], 1)
    detalle = [{"variante_id": tienda["v3"], "cantidad": 2}]

    sin_cliente, sin_stock = _enviar(
        tienda, "cajero",
        _op(tienda, "reserva", {"detalles": detalle}),
        _op(tienda, "reserva", {"cliente_id": tienda["cliente_id"], "detalles": detalle}),
    )

    assert (sin_cliente["estado"], sin_cliente["codigo"]) == ("rechazada", "falta_cliente")
    # A diferencia de una venta, la reserva no movió prendas ni dinero: no es un conflicto
    assert (sin_stock["estado"], sin_stock["codigo"]) == ("rechazada", "sin_stock")
    assert _stock(tienda, tienda["v3"], tienda["sucursal_a"]) == (1, 0)


# ------------------------------------------------------------------------------
# Cambios de prendas
# ------------------------------------------------------------------------------
def test_cambio_de_una_venta_hecha_sin_conexion_dentro_del_plazo(tienda):
    _poner_stock(tienda, tienda["v1"], tienda["sucursal_a"], 5)
    _poner_stock(tienda, tienda["v3"], tienda["sucursal_a"], 3)
    venta = _venta(tienda, tienda["v1"], 1)
    cambio = _cambio(tienda, [(tienda["v1"], 1)], [(tienda["v3"], 1, 150.0)], 50.0, venta_operacion_id=venta["id"])

    de_la_venta, del_cambio = _enviar(tienda, "cajero", venta, cambio)  # en el mismo lote, la venta primero

    assert de_la_venta["estado"] == "confirmada"
    assert (del_cambio["estado"], del_cambio["referencia_tipo"]) == ("confirmada", "cambio"), del_cambio
    assert _stock(tienda, tienda["v1"], tienda["sucursal_a"]) == (5, 0)  # vendida y devuelta
    assert _stock(tienda, tienda["v3"], tienda["sucursal_a"]) == (2, 0)
    with SessionLocal(info={CLAVE_TIENDA: tienda["id"]}) as db:
        registro = db.get(CambioPrenda, del_cambio["referencia_id"])
        assert (registro.venta_id, float(registro.diferencia)) == (de_la_venta["referencia_id"], 50.0)


def test_cambios_que_no_cumplen_las_reglas_se_rechazan(tienda):
    _poner_stock(tienda, tienda["v1"], tienda["sucursal_a"], 5)
    _poner_stock(tienda, tienda["v3"], tienda["sucursal_a"], 5)
    vieja, polera, campera = _enviar(
        tienda, "cajero",
        _venta(tienda, tienda["v1"], 1, hace=timedelta(days=10)),  # el plazo de la tienda es de 7 días
        _venta(tienda, tienda["v1"], 1),
        _venta(tienda, tienda["v3"], 1, precio=150.0),
    )

    fuera_de_plazo, de_mas, menor_valor, ajena = _enviar(
        tienda, "cajero",
        _cambio(tienda, [(tienda["v1"], 1)], [(tienda["v2"], 1, 100.0)], 0, venta_id=vieja["referencia_id"]),
        _cambio(tienda, [(tienda["v1"], 2)], [(tienda["v2"], 2, 100.0)], 0, venta_id=polera["referencia_id"]),
        _cambio(tienda, [(tienda["v3"], 1)], [(tienda["v1"], 1, 100.0)], -50, venta_id=campera["referencia_id"]),
        _cambio(tienda, [(tienda["v3"], 1)], [(tienda["v3"], 1, 150.0)], 0, venta_id=polera["referencia_id"]),
    )

    assert (fuera_de_plazo["estado"], fuera_de_plazo["codigo"]) == ("rechazada", "fuera_de_plazo")
    assert de_mas["codigo"] == "cantidad_excede"
    assert menor_valor["codigo"] == "cambio_de_menor_valor"
    assert ajena["codigo"] == "no_estaba_en_la_venta"


def test_un_cambio_de_una_venta_que_todavia_no_llego_queda_en_espera(tienda):
    _poner_stock(tienda, tienda["v1"], tienda["sucursal_a"], 5)
    _poner_stock(tienda, tienda["v2"], tienda["sucursal_a"], 2)
    venta = _venta(tienda, tienda["v1"], 1)
    cambio = _cambio(tienda, [(tienda["v1"], 1)], [(tienda["v2"], 1, 100.0)], 0, venta_operacion_id=venta["id"])

    [en_espera] = _enviar(tienda, "cajero", cambio)  # la venta todavía no se sincronizó
    assert (en_espera["estado"], en_espera["codigo"]) == ("conflicto", "venta_no_confirmada")

    _enviar(tienda, "cajero", venta)
    aceptado = _resolver(tienda, cambio["id"], "aceptar")
    assert aceptado.status_code == 200, aceptado.text
    assert aceptado.json()["estado"] == "confirmada"
    assert _stock(tienda, tienda["v2"], tienda["sucursal_a"]) == (1, 0)


# ------------------------------------------------------------------------------
# Paquete, plan, suscripción y aislamiento
# ------------------------------------------------------------------------------
def test_el_paquete_trae_solo_lo_que_cada_usuario_puede_usar(tienda):
    _poner_stock(tienda, tienda["v1"], tienda["sucursal_a"], 4)
    _poner_stock(tienda, tienda["v1"], tienda["sucursal_b"], 2)
    [venta] = _enviar(tienda, "cajero", _venta(tienda, tienda["v1"], 1))

    del_cajero = client.get("/api/v1/sync/paquete", headers=_en(tienda, "cajero")).json()
    assert [s["id"] for s in del_cajero["sucursales"]] == [tienda["sucursal_a"]]
    assert {i["sucursal_id"] for i in del_cajero["inventario"]} == {tienda["sucursal_a"]}
    assert {v["id"] for v in del_cajero["variantes"]} == {tienda["v1"], tienda["v2"], tienda["v3"]}  # nada de otra empresa
    assert tienda["cliente"] in [c["correo"] for c in del_cajero["clientes"]]
    vendida = next(v for v in del_cajero["ventas"] if v["id"] == venta["referencia_id"])
    assert vendida["detalles"] == [{"variante_id": tienda["v1"], "cantidad": 1, "precio_unitario": 100.0, "devuelto": 0}]
    assert (del_cajero["tienda"], del_cajero["dias_para_cambio"]) == (tienda["slug"], 7)
    assert del_cajero["vigencia_horas"] > 0 and del_cajero["generado_en"]

    del_cliente = client.get("/api/v1/sync/paquete", headers=_en(tienda, "cliente")).json()
    assert len(del_cliente["sucursales"]) == 2
    assert del_cliente["clientes"] == [] and del_cliente["ventas"] == []

    solo_b = client.get("/api/v1/sync/paquete", params={"sucursal_id": tienda["sucursal_b"]}, headers=_en(tienda, "admin")).json()
    assert [s["id"] for s in solo_b["sucursales"]] == [tienda["sucursal_b"]]
    ajena = client.get("/api/v1/sync/paquete", params={"sucursal_id": tienda["sucursal_b"]}, headers=_en(tienda, "cajero"))
    assert ajena.status_code == 403


def test_dos_empresas_pueden_usar_el_mismo_id_de_operacion(tienda):
    _poner_stock(tienda, tienda["v1"], tienda["sucursal_a"], 5)
    op = _venta(tienda, tienda["v1"], 1)
    fashionstore = buscar_tienda("fashionstore")
    with engine.begin() as conn:  # una operación de otra empresa con el mismo id
        conn.execute(
            text(
                "INSERT INTO operacion_sync (tienda_id, uuid, tipo, registrada_en, recibida_en, ultimo_intento, estado, huella, datos) "
                "VALUES (:t, :u, 'venta', now(), now(), now(), 'rechazada', 'x', '{}')"
            ),
            {"t": fashionstore.id, "u": op["id"]},
        )
    try:
        [resultado] = _enviar(tienda, "cajero", op)
        assert (resultado["estado"], resultado["duplicada"]) == ("confirmada", False)
    finally:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM operacion_sync WHERE tienda_id = :t AND uuid = :u"), {"t": fashionstore.id, "u": op["id"]})


def test_con_la_suscripcion_vencida_el_lote_queda_en_el_dispositivo(tienda):
    op = _venta(tienda, tienda["v1"], 1)
    with engine.begin() as conn:
        vence = conn.execute(text("SELECT fecha_vencimiento FROM suscripcion WHERE tienda_id = :t"), {"t": tienda["id"]}).scalar()
        conn.execute(text("UPDATE suscripcion SET fecha_vencimiento = now() - interval '1 day' WHERE tienda_id = :t"), {"t": tienda["id"]})
    olvidar_tienda(tienda["slug"])
    try:
        res = client.post("/api/v1/sync/operaciones", json={"operaciones": [op]}, headers=_en(tienda, "cajero"))
        assert res.status_code == 402
        # Consultar sigue permitido: el servidor no la recibió, el dispositivo la conserva
        estado = client.get("/api/v1/sync/estado", params={"ids": [op["id"]]}, headers=_en(tienda, "cajero")).json()
        assert estado["desconocidas"] == [op["id"]]
    finally:
        with engine.begin() as conn:
            conn.execute(text("UPDATE suscripcion SET fecha_vencimiento = :v WHERE tienda_id = :t"), {"v": vence, "t": tienda["id"]})
        olvidar_tienda(tienda["slug"])


def test_sin_operacion_offline_en_el_plan_no_hay_sincronizacion(tienda):
    with engine.begin() as conn:
        plan_original = conn.execute(text("SELECT plan_id FROM suscripcion WHERE tienda_id = :t"), {"t": tienda["id"]}).scalar()
        plan_id = conn.execute(
            text("INSERT INTO plan (codigo, nombre, operacion_offline, estado) VALUES (:c, 'Sin offline', false, false) RETURNING id"),
            {"c": f"sin-offline-{int(time.time() * 1000)}"},
        ).scalar()
        conn.execute(text("UPDATE suscripcion SET plan_id = :p WHERE tienda_id = :t"), {"p": plan_id, "t": tienda["id"]})
    try:
        res = client.get("/api/v1/sync/paquete", headers=_en(tienda, "cajero"))
        assert res.status_code == 402
        assert "sin conexión" in res.json()["detail"]
    finally:
        with engine.begin() as conn:
            conn.execute(text("UPDATE suscripcion SET plan_id = :p WHERE tienda_id = :t"), {"p": plan_original, "t": tienda["id"]})
            conn.execute(text("DELETE FROM plan WHERE id = :p"), {"p": plan_id})


def test_el_administrador_configura_el_plazo_de_cambio(tienda):
    assert client.get("/api/v1/tienda", headers=_en(tienda)).json()["dias_para_cambio"] == 7
    try:
        res = client.put("/api/v1/tienda", json={"dias_para_cambio": 15}, headers=_en(tienda, "admin"))
        assert res.status_code == 200 and res.json()["dias_para_cambio"] == 15
        assert client.put("/api/v1/tienda", json={"dias_para_cambio": 15}, headers=_en(tienda, "cajero")).status_code == 403
    finally:
        client.put("/api/v1/tienda", json={"dias_para_cambio": 7}, headers=_en(tienda, "admin"))
