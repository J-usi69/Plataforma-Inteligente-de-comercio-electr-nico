"""Pruebas del módulo de IA (CU-28, CU-29, CU-30). Se mockea la llamada a Claude
para no depender de una API key real ni de la red en cada corrida de tests."""
import json
import time
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.services.ia_service import IAServiceError

client = TestClient(app)


def _crear_y_loguear_cliente() -> str:
    ts = int(time.time() * 1000)
    correo = f"ia_test_{ts}@test.com"
    client.post("/api/v1/auth/register", json={"correo": correo, "password": "Password123*"})
    res = client.post("/api/v1/auth/login", json={"login": correo, "password": "Password123*"})
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


def _login_admin() -> str:
    res = client.post("/api/v1/auth/login", json={"login": "admin@fashionstore.com", "password": "Admin123*"})
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


def test_cu28_recomendaciones_camino_feliz():
    token = _crear_y_loguear_cliente()
    headers = {"Authorization": f"Bearer {token}"}

    catalogo = client.get("/api/v1/prendas").json()
    assert catalogo, "se necesita al menos una prenda activa en el catálogo para esta prueba"
    ids_validos = [p["id"] for p in catalogo[:3]]

    with patch("app.api.v1.endpoints.ia.llamar_gemini", return_value=json.dumps(ids_validos)):
        res = client.post("/api/v1/ia/recomendaciones", headers=headers)

    assert res.status_code == 200, res.text
    data = res.json()
    assert data["fuente"] == "ia"
    assert len(data["prendas"]) == len(ids_validos)


def test_cu28_recomendaciones_fallback_a_mas_vendidas():
    """Excepción documentada de CU-28: si la IA falla, se muestran las prendas más vendidas."""
    token = _crear_y_loguear_cliente()
    headers = {"Authorization": f"Bearer {token}"}

    with patch("app.api.v1.endpoints.ia.llamar_gemini", side_effect=IAServiceError("timeout simulado")):
        res = client.post("/api/v1/ia/recomendaciones", headers=headers)

    assert res.status_code == 200, res.text
    assert res.json()["fuente"] == "mas_vendidas"


def test_cu29_chat_camino_feliz():
    token = _crear_y_loguear_cliente()
    headers = {"Authorization": f"Bearer {token}"}

    with patch("app.api.v1.endpoints.ia.llamar_groq", return_value="Tenemos poleras disponibles en varias tallas."):
        res = client.post("/api/v1/ia/chat", headers=headers, json={"mensaje": "¿Tienen poleras?"})

    assert res.status_code == 200, res.text
    assert "poleras" in res.json()["respuesta"].lower()


def test_cu29_chat_funciona_sin_sesion():
    """El chatbot debe atender también a visitantes anónimos, sin token."""
    with patch("app.api.v1.endpoints.ia.llamar_groq", return_value="Tenemos poleras disponibles."):
        res = client.post("/api/v1/ia/chat", json={"mensaje": "¿Tienen poleras?"})

    assert res.status_code == 200, res.text
    assert "poleras" in res.json()["respuesta"].lower()


def test_cu29_chat_mensaje_de_limitacion_si_ia_no_disponible():
    token = _crear_y_loguear_cliente()
    headers = {"Authorization": f"Bearer {token}"}

    with patch("app.api.v1.endpoints.ia.llamar_groq", side_effect=IAServiceError("sin api key")):
        res = client.post("/api/v1/ia/chat", headers=headers, json={"mensaje": "hola"})

    assert res.status_code == 200, res.text
    assert "no está disponible" in res.json()["respuesta"]


def test_cu30_reporte_ia_camino_feliz():
    token = _login_admin()
    headers = {"Authorization": f"Bearer {token}"}

    respuesta_ia = json.dumps({"tipo": "ventas", "desde": None, "hasta": None, "sucursal_id": None})
    with patch("app.api.v1.endpoints.ia.llamar_mistral", return_value=respuesta_ia):
        res = client.post("/api/v1/ia/reportes", headers=headers, json={"prompt": "ventas totales"})

    assert res.status_code == 200, res.text
    assert res.json()["tipo"] == "ventas"


def test_cu30_reporte_ia_solicitud_ambigua():
    """Excepción documentada de CU-30: si no se puede interpretar, se informa y se
    sugiere reformular o usar los reportes predefinidos (CU-31)."""
    token = _login_admin()
    headers = {"Authorization": f"Bearer {token}"}

    with patch("app.api.v1.endpoints.ia.llamar_mistral", return_value="esto no es JSON válido"):
        res = client.post("/api/v1/ia/reportes", headers=headers, json={"prompt": "algo muy ambiguo"})

    assert res.status_code == 422, res.text
    assert "reportes predefinidos" in res.json()["detail"]


def test_cu30_reporte_ia_requiere_rol_administrador():
    token = _crear_y_loguear_cliente()
    headers = {"Authorization": f"Bearer {token}"}
    res = client.post("/api/v1/ia/reportes", headers=headers, json={"prompt": "ventas"})
    assert res.status_code == 403
