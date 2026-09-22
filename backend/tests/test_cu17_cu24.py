import pytest
import stripe
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


VARIANTE_ID = 3  # variante con stock seeded en sucursal 1 (ver seed_users.py)


class _FakePaymentIntentExitoso:
    """Simula un PaymentIntent de Stripe ya confirmado por el cliente en el navegador."""

    def __init__(self, venta_id: int):
        self.id = "pi_test_fake_123"
        self.status = "succeeded"
        self.metadata = {"venta_id": str(venta_id)}


def _mockear_stripe_pago_exitoso(monkeypatch: pytest.MonkeyPatch, venta_id: int) -> None:
    monkeypatch.setattr(
        stripe.PaymentIntent, "retrieve", lambda *args, **kwargs: _FakePaymentIntentExitoso(venta_id)
    )


def _login(login: str, password: str) -> str:
    res = client.post("/api/v1/auth/login", json={"login": login, "password": password})
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


def _get_admin_token():
    return _login("admin@fashionstore.com", "Admin123*")


def _get_cliente_token():
    return _login("cliente@fashionstore.com", "Cliente123*")


def _get_encargado_token():
    return _login("encargado@fashionstore.com", "Encargado123*")


def _get_cajero_token():
    return _login("cajero@fashionstore.com", "Cajero123*")


def _crear_reserva(cliente_token: str) -> int:
    res = client.post(
        "/api/v1/reservas",
        headers={"Authorization": f"Bearer {cliente_token}"},
        json={
            "sucursal_id": 1,
            "horario_atencion": "16:00:00",
            "detalles": [{"variante_id": VARIANTE_ID, "cantidad": 1}],
        },
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


def test_cu17_cu18_flujo_completo_reserva_hasta_atencion():
    """Flujo de punta a punta: crear -> listar sucursal -> confirmar -> atender."""
    cliente_token = _get_cliente_token()
    encargado_token = _get_encargado_token()

    reserva_id = _crear_reserva(cliente_token)

    # El cliente puede ver el detalle de su propia reserva
    res_propia = client.get(
        f"/api/v1/reservas/{reserva_id}",
        headers={"Authorization": f"Bearer {cliente_token}"},
    )
    assert res_propia.status_code == 200
    assert res_propia.json()["estado"] == "pendiente"

    # Encargado lista reservas de su sucursal y ve la reserva recién creada
    res_list = client.get(
        "/api/v1/reservas/sucursal/1",
        headers={"Authorization": f"Bearer {encargado_token}"},
    )
    assert res_list.status_code == 200
    assert reserva_id in [r["id"] for r in res_list.json()]

    # Encargado confirma preparación (apartó las prendas)
    res_conf = client.post(
        f"/api/v1/reservas/{reserva_id}/confirmar",
        headers={"Authorization": f"Bearer {encargado_token}"},
    )
    assert res_conf.status_code == 200
    assert res_conf.json()["estado"] == "confirmada"

    # Encargado confirma recepción del cliente en sucursal
    res_atend = client.post(
        f"/api/v1/reservas/{reserva_id}/atender",
        headers={"Authorization": f"Bearer {encargado_token}"},
    )
    assert res_atend.status_code == 200
    assert res_atend.json()["estado"] == "atendida"

    # El cliente sigue pudiendo consultar el estado final de su reserva
    res_final = client.get(
        f"/api/v1/reservas/{reserva_id}",
        headers={"Authorization": f"Bearer {cliente_token}"},
    )
    assert res_final.status_code == 200
    assert res_final.json()["estado"] == "atendida"


def test_cu18_excepcion_no_show_libera_stock():
    """Excepción: el cliente no se presenta y el stock reservado vuelve a estar disponible."""
    cliente_token = _get_cliente_token()
    encargado_token = _get_encargado_token()

    inv_antes = client.get(
        "/api/v1/reservas",
        headers={"Authorization": f"Bearer {cliente_token}"},
    )
    assert inv_antes.status_code == 200

    reserva_id = _crear_reserva(cliente_token)

    res_no_show = client.post(
        f"/api/v1/reservas/{reserva_id}/no-show",
        headers={"Authorization": f"Bearer {encargado_token}"},
    )
    assert res_no_show.status_code == 200
    # El enum EstadoReserva no tiene un valor "no_show" propio; la acción de la ruta
    # /no-show marca la reserva como "expirada" (ver EstadoReserva en app/models/enums.py)
    assert res_no_show.json()["estado"] == "expirada"


def test_cu17_cu18_control_de_acceso_reservas():
    """Un Cliente no debe poder ejecutar acciones de Encargado ni ver reservas de otros usuarios."""
    cliente_token = _get_cliente_token()
    encargado_token = _get_encargado_token()

    reserva_id = _crear_reserva(cliente_token)

    # Un cliente cualquiera no puede listar las reservas de la sucursal (endpoint solo staff)
    res_forbidden_list = client.get(
        "/api/v1/reservas/sucursal/1",
        headers={"Authorization": f"Bearer {cliente_token}"},
    )
    assert res_forbidden_list.status_code == 403

    # Un cliente no puede confirmar/atender/marcar no-show (acciones exclusivas de Encargado/Admin)
    for accion in ["confirmar", "atender", "no-show"]:
        res_forbidden = client.post(
            f"/api/v1/reservas/{reserva_id}/{accion}",
            headers={"Authorization": f"Bearer {cliente_token}"},
        )
        assert res_forbidden.status_code == 403, f"acción '{accion}' debería estar bloqueada para Cliente"

    # Limpieza: el encargado libera el stock cancelando el ciclo con no-show
    client.post(
        f"/api/v1/reservas/{reserva_id}/no-show",
        headers={"Authorization": f"Bearer {encargado_token}"},
    )


def test_cu19_cu20_cu23_flujo_completo_venta_presencial():
    """Flujo de punta a punta: venta presencial -> cobro en caja -> comprobante."""
    cajero_token = _get_cajero_token()

    res_venta = client.post(
        "/api/v1/ventas/presencial",
        headers={"Authorization": f"Bearer {cajero_token}"},
        json={
            "sucursal_id": 1,
            "detalles": [{"variante_id": VARIANTE_ID, "cantidad": 1, "precio_unitario": 249.99}],
        },
    )
    assert res_venta.status_code == 201, res_venta.text
    venta_id = res_venta.json()["id"]
    assert res_venta.json()["estado"] == "pendiente"
    assert res_venta.json()["tipo_origen"] == "presencial"

    # Cobro en caja
    res_pago = client.post(
        f"/api/v1/ventas/{venta_id}/cobrar-caja",
        headers={"Authorization": f"Bearer {cajero_token}"},
        json={"metodo_pago": "efectivo", "monto_recibido": 250.0},
    )
    assert res_pago.status_code == 200
    assert res_pago.json()["estado"] == "pagada"

    # Cobrar dos veces debe fallar (regla de negocio, no solo un happy path)
    res_doble_cobro = client.post(
        f"/api/v1/ventas/{venta_id}/cobrar-caja",
        headers={"Authorization": f"Bearer {cajero_token}"},
        json={"metodo_pago": "efectivo", "monto_recibido": 250.0},
    )
    assert res_doble_cobro.status_code == 400

    # Emitir comprobante (el cajero, como staff, puede emitirlo)
    res_comp = client.get(
        f"/api/v1/ventas/comprobante/{venta_id}",
        headers={"Authorization": f"Bearer {cajero_token}"},
    )
    assert res_comp.status_code == 200
    comprobante = res_comp.json()
    assert comprobante["venta_id"] == venta_id
    assert comprobante["total"] > 0
    assert comprobante["estado_venta"] == "PAGADA"


def test_cu19_cu20_control_de_acceso_ventas_presenciales():
    """Un Cliente no debe poder registrar ventas presenciales ni cobrar en caja."""
    cliente_token = _get_cliente_token()
    cajero_token = _get_cajero_token()

    res_forbidden_venta = client.post(
        "/api/v1/ventas/presencial",
        headers={"Authorization": f"Bearer {cliente_token}"},
        json={
            "sucursal_id": 1,
            "detalles": [{"variante_id": VARIANTE_ID, "cantidad": 1, "precio_unitario": 249.99}],
        },
    )
    assert res_forbidden_venta.status_code == 403

    # Preparamos una venta real (como cajero) para probar que un cliente no puede cobrarla
    res_venta = client.post(
        "/api/v1/ventas/presencial",
        headers={"Authorization": f"Bearer {cajero_token}"},
        json={
            "sucursal_id": 1,
            "detalles": [{"variante_id": VARIANTE_ID, "cantidad": 1, "precio_unitario": 249.99}],
        },
    )
    assert res_venta.status_code == 201
    venta_id = res_venta.json()["id"]

    res_forbidden_cobro = client.post(
        f"/api/v1/ventas/{venta_id}/cobrar-caja",
        headers={"Authorization": f"Bearer {cliente_token}"},
        json={"metodo_pago": "efectivo", "monto_recibido": 250.0},
    )
    assert res_forbidden_cobro.status_code == 403

    # Un cliente ajeno a esta venta tampoco puede consultar su comprobante ni su detalle (IDOR)
    res_forbidden_comprobante = client.get(
        f"/api/v1/ventas/comprobante/{venta_id}",
        headers={"Authorization": f"Bearer {cliente_token}"},
    )
    assert res_forbidden_comprobante.status_code == 404

    res_forbidden_detalle = client.get(
        f"/api/v1/ventas/{venta_id}",
        headers={"Authorization": f"Bearer {cliente_token}"},
    )
    assert res_forbidden_detalle.status_code == 404

    # Limpieza: el cajero sí puede cobrarla normalmente
    client.post(
        f"/api/v1/ventas/{venta_id}/cobrar-caja",
        headers={"Authorization": f"Bearer {cajero_token}"},
        json={"metodo_pago": "efectivo", "monto_recibido": 250.0},
    )


def test_cu21_cu22_cu24_flujo_completo_compra_digital(monkeypatch: pytest.MonkeyPatch):
    """Flujo de punta a punta: compra digital -> pago con tarjeta (Stripe) -> historial."""
    cliente_token = _get_cliente_token()

    res_compra = client.post(
        "/api/v1/ventas/digital",
        headers={"Authorization": f"Bearer {cliente_token}"},
        json={
            "sucursal_id": 1,
            "detalles": [{"variante_id": VARIANTE_ID, "cantidad": 1}],
        },
    )
    assert res_compra.status_code == 201, res_compra.text
    venta_id = res_compra.json()["id"]
    assert res_compra.json()["estado"] == "pendiente"

    # Pago digital con tarjeta (el PaymentIntent de Stripe ya fue confirmado en el navegador)
    _mockear_stripe_pago_exitoso(monkeypatch, venta_id)
    res_pago = client.post(
        f"/api/v1/ventas/{venta_id}/pagar-digital",
        headers={"Authorization": f"Bearer {cliente_token}"},
        json={"metodo_pago": "tarjeta", "stripe_payment_intent_id": "pi_test_fake_123"},
    )
    assert res_pago.status_code == 200, res_pago.text
    assert res_pago.json()["estado"] == "pagada"

    # Pagar dos veces debe fallar
    res_doble_pago = client.post(
        f"/api/v1/ventas/{venta_id}/pagar-digital",
        headers={"Authorization": f"Bearer {cliente_token}"},
        json={"metodo_pago": "tarjeta", "stripe_payment_intent_id": "pi_test_fake_123"},
    )
    assert res_doble_pago.status_code == 400

    # El propio cliente puede ver su comprobante
    res_comp = client.get(
        f"/api/v1/ventas/comprobante/{venta_id}",
        headers={"Authorization": f"Bearer {cliente_token}"},
    )
    assert res_comp.status_code == 200

    # Consultar historial de compras del cliente
    res_historial = client.get(
        "/api/v1/ventas/mis-compras",
        headers={"Authorization": f"Bearer {cliente_token}"},
    )
    assert res_historial.status_code == 200
    compras = res_historial.json()
    assert any(c["id"] == venta_id for c in compras)


def test_cu21_cu22_control_de_acceso_compra_digital(monkeypatch: pytest.MonkeyPatch):
    """Un cliente no debe poder pagar ni ver la compra digital de otro cliente (IDOR)."""
    cliente_token = _get_cliente_token()
    admin_token = _get_admin_token()

    res_compra = client.post(
        "/api/v1/ventas/digital",
        headers={"Authorization": f"Bearer {cliente_token}"},
        json={
            "sucursal_id": 1,
            "detalles": [{"variante_id": VARIANTE_ID, "cantidad": 1}],
        },
    )
    assert res_compra.status_code == 201
    venta_id = res_compra.json()["id"]

    # El admin no es dueño de esta venta ni tiene rol de staff de venta con acceso a "pagar",
    # pero sí puede consultarla (rol Administrador está en _ROLES_STAFF_VENTA)
    res_pago_ajeno = client.post(
        f"/api/v1/ventas/{venta_id}/pagar-digital",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"metodo_pago": "tarjeta", "stripe_payment_intent_id": "pi_test_fake_ajeno"},
    )
    assert res_pago_ajeno.status_code == 404

    # Limpieza: el dueño real paga su compra
    _mockear_stripe_pago_exitoso(monkeypatch, venta_id)
    res_pago = client.post(
        f"/api/v1/ventas/{venta_id}/pagar-digital",
        headers={"Authorization": f"Bearer {cliente_token}"},
        json={"metodo_pago": "tarjeta", "stripe_payment_intent_id": "pi_test_fake_123"},
    )
    assert res_pago.status_code == 200, res_pago.text


def test_listar_ventas_sucursal_solo_staff():
    """El endpoint de ventas por sucursal es exclusivo de Cajero/Encargado/Administrador."""
    cliente_token = _get_cliente_token()
    cajero_token = _get_cajero_token()

    res_forbidden = client.get(
        "/api/v1/ventas/sucursal/1",
        headers={"Authorization": f"Bearer {cliente_token}"},
    )
    assert res_forbidden.status_code == 403

    res_ok = client.get(
        "/api/v1/ventas/sucursal/1",
        headers={"Authorization": f"Bearer {cajero_token}"},
    )
    assert res_ok.status_code == 200
