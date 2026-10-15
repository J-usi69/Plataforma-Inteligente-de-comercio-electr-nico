"""Clave JWT y CORS. Ninguno de estos tests usa la base de datos."""
import pytest
from fastapi.testclient import TestClient
from jose import jwt

from app.core import security
from app.core.config import settings
from app.main import app

client = TestClient(app)


def test_sin_jwt_secret_key_no_se_firman_sesiones(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "jwt_secret_key", "")

    with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
        security.create_access_token({"sub": "1"})


def test_sin_jwt_secret_key_el_servidor_no_arranca(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "jwt_secret_key", "")

    with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
        with TestClient(app):
            pass


def test_token_firmado_con_la_antigua_clave_de_respaldo_es_rechazado(monkeypatch: pytest.MonkeyPatch):
    # La clave de respaldo estaba en el repo: un token firmado con ella no debe valer
    monkeypatch.setattr(settings, "jwt_secret_key", "clave-de-prueba-larga-y-aleatoria-1234567890")
    falso = jwt.encode({"sub": "1"}, "default_secret_key_fashionstore", algorithm=security.ALGORITHM)

    assert security.decode_access_token(falso) is None
    assert security.decode_access_token(security.create_access_token({"sub": "1"}))["sub"] == "1"


def _preflight(origen: str):
    return client.options(
        "/api/v1/sucursales",
        headers={"Origin": origen, "Access-Control-Request-Method": "GET"},
    )


@pytest.mark.parametrize(
    "origen",
    ["https://fashionstore-uagrm.up.railway.app", "http://localhost:4200", "http://127.0.0.1:8080"],
)
def test_cors_permite_la_web_y_localhost(origen):
    assert _preflight(origen).headers.get("access-control-allow-origin") == origen


@pytest.mark.parametrize(
    "origen",
    [
        "https://sitio-malicioso.example",
        "https://fashionstore-uagrm.up.railway.app.malicioso.example",
        "http://localhost.malicioso.example",
    ],
)
def test_cors_rechaza_otros_sitios(origen):
    assert "access-control-allow-origin" not in _preflight(origen).headers
