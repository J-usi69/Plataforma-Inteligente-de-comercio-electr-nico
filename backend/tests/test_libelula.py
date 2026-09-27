"""Pago con QR a través de Libélula. Nunca se le pega a la API real: en modo de prueba no hace
falta, y con llave se reemplaza la llamada HTTP del servicio por respuestas simuladas."""
import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.services import libelula_service

client = TestClient(app)

VARIANTE_ID = 3  # variante con stock seeded en sucursal 1 (ver seed_users.py)


def _cliente_headers() -> dict:
    res = client.post("/api/v1/auth/login", json={"login": "cliente@fashionstore.com", "password": "Cliente123*"})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _crear_venta_digital(headers: dict) -> dict:
    res = client.post(
        "/api/v1/ventas/digital",
        headers=headers,
        json={"sucursal_id": 1, "detalles": [{"variante_id": VARIANTE_ID, "cantidad": 1}]},
    )
    assert res.status_code == 201, res.text
    return res.json()


class _LibelulaFalsa:
    """Reemplaza las llamadas HTTP a Libélula: registra deudas y responde si están pagadas."""

    def __init__(self):
        self.pagadas: dict[str, float] = {}  # identificador -> monto pagado
        self.registradas: list[dict] = []

    def post(self, ruta: str, cuerpo: dict) -> dict:
        if ruta == "/rest/deuda/registrar":
            self.registradas.append(cuerpo)
            return {
                "error": 0,
                "mensaje": "Deuda registrada",
                "id_transaccion": f"tx-falsa-{uuid.uuid4()}",
                "url_pasarela_pagos": "https://pagos.libelula.bo/?id=falso",
                "qr_simple_url": "https://api.libelula.bo/qr/falso.png",
            }
        identificador = cuerpo["identificador"]
        pagado = identificador in self.pagadas
        return {
            "error": 0,
            "mensaje": "1 deuda encontrada.",
            "datos": [{"identificador": identificador, "pagado": pagado, "valor_total": self.pagadas.get(identificador)}],
        }

    def pagar(self, identificador: str, monto: float) -> None:
        self.pagadas[identificador] = monto


@pytest.fixture
def libelula_falsa(monkeypatch: pytest.MonkeyPatch) -> _LibelulaFalsa:
    falsa = _LibelulaFalsa()
    monkeypatch.setattr(settings, "libelula_appkey", "llave-de-prueba")
    monkeypatch.setattr(libelula_service, "_post", falsa.post)
    return falsa


def test_qr_libelula_modo_prueba_flujo_completo(monkeypatch: pytest.MonkeyPatch):
    """Sin appkey: QR de demostración, pago con "Simular pago" y comprobante con método QR."""
    monkeypatch.setattr(settings, "libelula_appkey", "")
    headers = _cliente_headers()
    venta = _crear_venta_digital(headers)

    res_qr = client.post(f"/api/v1/ventas/{venta['id']}/qr-libelula", headers=headers)
    assert res_qr.status_code == 200, res_qr.text
    qr = res_qr.json()
    assert qr["modo_prueba"] is True
    assert qr["qr_url"].startswith("data:image/png;base64,")
    assert qr["monto"] == venta["total"]

    res_estado = client.get(f"/api/v1/ventas/{venta['id']}/qr-libelula/estado", headers=headers)
    assert res_estado.json()["pagado"] is False

    res_simular = client.post(f"/api/v1/ventas/{venta['id']}/qr-libelula/simular-pago", headers=headers)
    assert res_simular.status_code == 200, res_simular.text
    assert res_simular.json()["estado"] == "pagada"

    res_estado = client.get(f"/api/v1/ventas/{venta['id']}/qr-libelula/estado", headers=headers)
    assert res_estado.json()["pagado"] is True

    res_comp = client.get(f"/api/v1/ventas/comprobante/{venta['id']}", headers=headers)
    assert res_comp.json()["metodo_pago"] == "QR"

    # Una venta pagada no genera otro QR
    res_otro_qr = client.post(f"/api/v1/ventas/{venta['id']}/qr-libelula", headers=headers)
    assert res_otro_qr.status_code == 400


def test_qr_libelula_callback_confirma_contra_libelula(libelula_falsa: _LibelulaFalsa):
    """Con appkey: el aviso de Libélula solo aprueba si al consultar la deuda figura pagada."""
    headers = _cliente_headers()
    venta = _crear_venta_digital(headers)

    res_qr = client.post(f"/api/v1/ventas/{venta['id']}/qr-libelula", headers=headers)
    assert res_qr.status_code == 200, res_qr.text
    qr = res_qr.json()
    assert qr["modo_prueba"] is False
    assert qr["qr_url"] == "https://api.libelula.bo/qr/falso.png"
    registrada = libelula_falsa.registradas[-1]
    assert registrada["appkey"] == "llave-de-prueba"
    assert registrada["callback_url"].endswith("/api/v1/ventas/libelula/callback")
    assert sum(l["cantidad"] * l["costo_unitario"] for l in registrada["lineas_detalle_deuda"]) == pytest.approx(venta["total"])

    # Con la llave real no se puede "simular" un pago
    res_simular = client.post(f"/api/v1/ventas/{venta['id']}/qr-libelula/simular-pago", headers=headers)
    assert res_simular.status_code == 404

    # Aviso sin que Libélula tenga el pago registrado (aviso falso): no se aprueba
    callback = f"/api/v1/ventas/libelula/callback?transaction_id={qr['transaccion_id']}"
    assert client.get(callback).json()["ok"] is False
    assert client.get(f"/api/v1/ventas/{venta['id']}", headers=headers).json()["estado"] == "pendiente"

    # El cliente paga el QR: ahora el aviso sí se confirma y se cierra la venta
    libelula_falsa.pagar(registrada["identificador"], venta["total"])
    assert client.get(callback).json()["ok"] is True
    assert client.get(f"/api/v1/ventas/{venta['id']}", headers=headers).json()["estado"] == "pagada"

    # Libélula puede repetir el aviso: no se vuelve a descontar nada
    assert client.get(callback).json()["mensaje"] == "La venta ya estaba pagada"


def test_qr_libelula_consulta_de_estado_aprueba_sin_callback(libelula_falsa: _LibelulaFalsa):
    """Si el aviso de Libélula no llega, la consulta de estado que hace el frontend cierra la venta."""
    headers = _cliente_headers()
    venta = _crear_venta_digital(headers)
    client.post(f"/api/v1/ventas/{venta['id']}/qr-libelula", headers=headers)
    identificador = libelula_falsa.registradas[-1]["identificador"]

    # Pagó un monto distinto al de la venta: no se aprueba
    libelula_falsa.pagar(identificador, venta["total"] - 10)
    res_estado = client.get(f"/api/v1/ventas/{venta['id']}/qr-libelula/estado", headers=headers)
    assert res_estado.json()["pagado"] is False

    libelula_falsa.pagar(identificador, venta["total"])
    res_estado = client.get(f"/api/v1/ventas/{venta['id']}/qr-libelula/estado", headers=headers)
    assert res_estado.json()["pagado"] is True


def test_qr_libelula_callback_de_transaccion_desconocida():
    res = client.get("/api/v1/ventas/libelula/callback?transaction_id=no-existe-123")
    assert res.status_code == 404


def test_qr_libelula_requiere_sesion():
    assert client.post("/api/v1/ventas/1/qr-libelula").status_code == 401
    assert client.get("/api/v1/ventas/1/qr-libelula/estado").status_code == 401
