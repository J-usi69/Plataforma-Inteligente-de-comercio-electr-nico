"""Pruebas del registro de tokens push y del envío por FCM. Se mockea la llamada
HTTP a Firebase para no depender de credenciales reales ni de la red."""
import time
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.services import push_service

client = TestClient(app)


def _crear_y_loguear_cliente() -> str:
    ts = int(time.time() * 1000)
    correo = f"push_test_{ts}@test.com"
    client.post("/api/v1/auth/register", json={"correo": correo, "password": "Password123*"})
    res = client.post("/api/v1/auth/login", json={"login": correo, "password": "Password123*"})
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


def test_registrar_y_actualizar_token():
    token = _crear_y_loguear_cliente()
    headers = {"Authorization": f"Bearer {token}"}

    res = client.post("/api/v1/notificaciones/token", headers=headers, json={"token": "fcm-token-abc", "plataforma": "android"})
    assert res.status_code == 204, res.text

    # Re-registrar el mismo token no debe fallar (upsert)
    res = client.post("/api/v1/notificaciones/token", headers=headers, json={"token": "fcm-token-abc", "plataforma": "android"})
    assert res.status_code == 204, res.text


def test_eliminar_token():
    token = _crear_y_loguear_cliente()
    headers = {"Authorization": f"Bearer {token}"}

    client.post("/api/v1/notificaciones/token", headers=headers, json={"token": "fcm-token-a-borrar"})
    res = client.request("DELETE", "/api/v1/notificaciones/token", headers=headers, json={"token": "fcm-token-a-borrar"})
    assert res.status_code == 204, res.text


def test_registrar_token_requiere_autenticacion():
    res = client.post("/api/v1/notificaciones/token", json={"token": "sin-sesion"})
    assert res.status_code == 401


def test_enviar_push_sin_firebase_configurado_no_falla():
    """Si no hay FIREBASE_CREDENTIALS_JSON, el servicio debe degradar en silencio (no lanzar)."""
    from app.db.session import SessionLocal
    db = SessionLocal()
    try:
        push_service.enviar_push_a_usuario(db, usuario_id=999999, titulo="t", cuerpo="c")
    finally:
        db.close()


def test_enviar_push_con_token_invalido_lo_elimina():
    token = _crear_y_loguear_cliente()
    headers = {"Authorization": f"Bearer {token}"}
    client.post("/api/v1/notificaciones/token", headers=headers, json={"token": "fcm-token-invalido"})

    from app.db.session import SessionLocal
    db = SessionLocal()
    try:
        with patch("app.services.push_service._access_token", return_value="fake-token"), \
             patch("app.services.push_service._proyecto_id", return_value="fake-project"), \
             patch("app.services.push_service._enviar_a_token", return_value="invalido"):
            usuario_id = client.get("/api/v1/auth/me", headers=headers).json()["id"]
            push_service.enviar_push_a_usuario(db, usuario_id, "t", "c")

        from app.models.seguridad import PushToken
        restante = db.query(PushToken).filter(PushToken.token == "fcm-token-invalido").first()
        assert restante is None
    finally:
        db.close()
