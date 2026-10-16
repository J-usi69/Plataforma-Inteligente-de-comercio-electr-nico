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


def test_login_se_bloquea_tras_varios_fallos_y_avisa_cuanto_esperar(monkeypatch: pytest.MonkeyPatch):
    from app.api.v1.endpoints import auth
    from app.core.limite_intentos import LimiteIntentos

    # Contadores propios y una sesión falsa: el test no depende de la base ni de otros tests
    monkeypatch.setattr(auth, "intentos_por_cuenta", LimiteIntentos(maximo=3, ventana_segundos=600))
    monkeypatch.setattr(auth, "intentos_por_ip", LimiteIntentos(maximo=100, ventana_segundos=600))
    app.dependency_overrides[auth.get_db] = lambda: _SesionSinUsuarios()
    try:
        cuerpo = {"login": "nadie@ejemplo.com", "password": "incorrecta"}
        codigos = [client.post("/api/v1/auth/login", json=cuerpo).status_code for _ in range(3)]
        bloqueado = client.post("/api/v1/auth/login", json=cuerpo)
        otra_cuenta = client.post("/api/v1/auth/login", json={**cuerpo, "login": "otra@ejemplo.com"})
    finally:
        app.dependency_overrides.clear()

    assert codigos == [401, 401, 401]
    assert bloqueado.status_code == 429
    assert int(bloqueado.headers["retry-after"]) > 0
    assert "minuto" in bloqueado.json()["detail"]
    assert otra_cuenta.status_code == 401  # el bloqueo es por cuenta, no corta a todos


class _SesionSinUsuarios:
    """Sesión falsa: cualquier búsqueda de usuario no encuentra nada."""

    def scalars(self, *_):
        return self

    def first(self):
        return None


def test_cada_respuesta_trae_un_request_id_y_respeta_el_que_llega():
    nuevo = client.get("/no-existe")
    propio = client.get("/no-existe", headers={"X-Request-ID": "abc123"})

    assert len(nuevo.headers.get("x-request-id", "")) == 12
    assert propio.headers["x-request-id"] == "abc123"


def test_error_inesperado_responde_generico_sin_detalles_internos():
    from fastapi import APIRouter

    router = APIRouter()

    @router.get("/_prueba_error")
    def _explota():
        raise ValueError("detalle interno que no debe salir")

    app.include_router(router)
    try:
        respuesta = TestClient(app, raise_server_exceptions=False).get("/_prueba_error")
    finally:
        app.router.routes[:] = [r for r in app.router.routes if getattr(r, "path", "") != "/_prueba_error"]

    assert respuesta.status_code == 500
    assert "detalle interno" not in respuesta.text
    assert respuesta.json()["request_id"] == respuesta.headers["x-request-id"]


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
