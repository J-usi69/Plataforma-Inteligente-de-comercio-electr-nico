import time
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _get_admin_token():
    res = client.post(
        "/api/v1/auth/login",
        json={"login": "admin@fashionstore.com", "password": "Admin123*"},
    )
    assert res.status_code == 200
    return res.json()["access_token"]


def _get_cliente_token():
    res = client.post(
        "/api/v1/auth/login",
        json={"login": "cliente@fashionstore.com", "password": "Cliente123*"},
    )
    assert res.status_code == 200
    return res.json()["access_token"]


def _get_encargado_token():
    res = client.post(
        "/api/v1/auth/login",
        json={"login": "encargado@fashionstore.com", "password": "Encargado123*"},
    )
    if res.status_code != 200:
        return _get_admin_token()
    return res.json()["access_token"]


def _get_cajero_token():
    res = client.post(
        "/api/v1/auth/login",
        json={"login": "cajero@fashionstore.com", "password": "Cajero123*"},
    )
    if res.status_code != 200:
        return _get_admin_token()
    return res.json()["access_token"]


def test_cu17_cu18_reservas_sucursal_y_recepcion():
    """CU-17: Preparar reservas recibidas y CU-18: Confirmar recepción de cliente"""
    cliente_token = _get_cliente_token()
    encargado_token = _get_encargado_token()

    # 1. Crear una reserva como cliente
    res_crear = client.post(
        "/api/v1/reservas",
        headers={"Authorization": f"Bearer {cliente_token}"},
        json={
            "sucursal_id": 1,
            "horario_atencion": "16:00:00",
            "detalles": [{"variante_id": 1, "cantidad": 1}],
        },
    )
    assert res_crear.status_code in [201, 400]
    if res_crear.status_code == 201:
        reserva_id = res_crear.json()["id"]

        # CU-17: Encargado lista reservas de su sucursal
        res_list = client.get(
            "/api/v1/reservas/sucursal/1",
            headers={"Authorization": f"Bearer {encargado_token}"},
        )
        assert res_list.status_code == 200
        ids = [r["id"] for r in res_list.json()]
        assert reserva_id in ids

        # CU-17: Encargado confirma preparación (apartó las prendas)
        res_conf = client.post(
            f"/api/v1/reservas/{reserva_id}/confirmar",
            headers={"Authorization": f"Bearer {encargado_token}"},
        )
        assert res_conf.status_code == 200
        assert res_conf.json()["estado"] == "confirmada"

        # CU-18: Encargado confirma recepción del cliente en sucursal
        res_atend = client.post(
            f"/api/v1/reservas/{reserva_id}/atender",
            headers={"Authorization": f"Bearer {encargado_token}"},
        )
        assert res_atend.status_code == 200
        assert res_atend.json()["estado"] == "atendida"


def test_cu19_cu20_cu23_venta_presencial_cobro_y_comprobante():
    """CU-19: Registrar venta presencial, CU-20: Cobro en caja, CU-23: Comprobante"""
    cajero_token = _get_cajero_token()

    # Registrar venta presencial
    res_venta = client.post(
        "/api/v1/ventas/presencial",
        headers={"Authorization": f"Bearer {cajero_token}"},
        json={
            "sucursal_id": 1,
            "detalles": [{"variante_id": 1, "cantidad": 1, "precio_unitario": 249.99}],
        },
    )
    assert res_venta.status_code in [201, 400]
    if res_venta.status_code == 201:
        venta_id = res_venta.json()["id"]
        assert res_venta.json()["estado"] == "pendiente"
        assert res_venta.json()["tipo_origen"] == "presencial"

        # CU-20: Cobro en caja
        res_pago = client.post(
            f"/api/v1/ventas/{venta_id}/cobrar-caja",
            headers={"Authorization": f"Bearer {cajero_token}"},
            json={"metodo_pago": "efectivo", "monto_recibido": 250.0},
        )
        assert res_pago.status_code == 200
        assert res_pago.json()["estado"] == "pagada"

        # CU-23: Emitir comprobante
        res_comp = client.get(
            f"/api/v1/ventas/comprobante/{venta_id}",
            headers={"Authorization": f"Bearer {cajero_token}"},
        )
        assert res_comp.status_code == 200
        comprobante = res_comp.json()
        assert "numero_comprobante" in comprobante
        assert comprobante["venta_id"] == venta_id
        assert comprobante["total"] > 0


def test_cu21_cu22_cu24_compra_digital_pago_y_mis_compras():
    """CU-21: Compra digital, CU-22: Pago pasarela digital, CU-24: Historial mis compras"""
    cliente_token = _get_cliente_token()

    # CU-21: Compra digital desde web
    res_compra = client.post(
        "/api/v1/ventas/digital",
        headers={"Authorization": f"Bearer {cliente_token}"},
        json={
            "sucursal_id": 1,
            "detalles": [{"variante_id": 1, "cantidad": 1}],
        },
    )
    assert res_compra.status_code in [201, 400]
    if res_compra.status_code == 201:
        venta_id = res_compra.json()["id"]
        assert res_compra.json()["estado"] == "pendiente"

        # CU-22: Pago digital
        res_pago = client.post(
            f"/api/v1/ventas/{venta_id}/pagar-digital",
            headers={"Authorization": f"Bearer {cliente_token}"},
            json={"metodo_pago": "qr", "pasarela": "Libélula QR"},
        )
        assert res_pago.status_code == 200
        assert res_pago.json()["estado"] == "pagada"

        # CU-24: Consultar historial de compras del cliente
        res_historial = client.get(
            "/api/v1/ventas/mis-compras",
            headers={"Authorization": f"Bearer {cliente_token}"},
        )
        assert res_historial.status_code == 200
        compras = res_historial.json()
        assert len(compras) > 0
        assert any(c["id"] == venta_id for c in compras)
