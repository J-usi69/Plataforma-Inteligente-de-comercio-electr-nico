"""Aislamiento entre tiendas (SaaS): lo de una tienda no se ve, no se toca y no se mezcla con lo
de otra, ni por la API (filtro del ORM) ni con SQL crudo (Row Level Security de Postgres)."""
import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.db.session import SessionLocal, engine
from app.db.tenancy import CLAVE_TIENDA, olvidar_tienda
from app.main import app
from app.services.tiendas_service import crear_tienda

client = TestClient(app)
PASSWORD = "ClaveSegura123*"


@pytest.fixture(scope="module")
def tienda_b(borrar_tienda):
    slug = f"prueba-{int(time.time() * 1000)}"
    correo = f"dueno{int(time.time() * 1000)}@tienda-b.com"
    with SessionLocal() as db:
        tienda = crear_tienda(db, slug=slug, nombre="Tienda B", correo_admin=correo, password_admin=PASSWORD)
        datos = {"id": tienda.id, "slug": slug, "correo": correo}
    yield datos
    borrar_tienda(datos["id"])


def _token(login: str, password: str, slug: str | None = None) -> str:
    headers = {"X-Tienda": slug} if slug else {}
    res = client.post("/api/v1/auth/login", json={"login": login, "password": password}, headers=headers)
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


def _en(slug: str | None, token: str | None = None) -> dict:
    headers = {"X-Tienda": slug} if slug else {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def test_lo_creado_en_una_tienda_solo_se_ve_en_ella(tienda_b):
    token_b = _token(tienda_b["correo"], PASSWORD, tienda_b["slug"])
    # El mismo nombre que ya usa la tienda por defecto: la unicidad es por tienda
    res = client.post(
        "/api/v1/catalogo-maestro/categorias",
        json={"nombre": "Poleras y Camisetas", "descripcion": "de la tienda B"},
        headers=_en(tienda_b["slug"], token_b),
    )
    assert res.status_code == 201, res.text

    en_b = client.get("/api/v1/catalogo-maestro/categorias", headers=_en(tienda_b["slug"])).json()
    en_default = client.get("/api/v1/catalogo-maestro/categorias").json()

    assert [c["descripcion"] for c in en_b] == ["de la tienda B"]
    assert all(c["descripcion"] != "de la tienda B" for c in en_default)
    assert len(en_default) >= 5  # las de la tienda por defecto siguen intactas


def test_una_tienda_nueva_no_ve_el_catalogo_ni_los_usuarios_de_otra(tienda_b):
    assert client.get("/api/v1/prendas", headers=_en(tienda_b["slug"])).json() == []
    assert len(client.get("/api/v1/prendas").json()) > 0
    # Cuentas de la tienda por defecto no existen en la tienda B
    res = client.post(
        "/api/v1/auth/login",
        json={"login": "admin@fashionstore.com", "password": "Admin123*"},
        headers=_en(tienda_b["slug"]),
    )
    assert res.status_code == 401


def test_una_sesion_de_una_tienda_no_sirve_en_otra(tienda_b):
    token_b = _token(tienda_b["correo"], PASSWORD, tienda_b["slug"])

    assert client.get("/api/v1/auth/me", headers=_en(tienda_b["slug"], token_b)).status_code == 200
    res = client.get("/api/v1/auth/me", headers=_en(None, token_b))
    assert res.status_code == 401
    assert "otra tienda" in res.json()["detail"]


def test_el_mismo_correo_puede_ser_cliente_de_dos_tiendas(tienda_b):
    res = client.post(
        "/api/v1/auth/register",
        json={"correo": "cliente@fashionstore.com", "password": "OtraClave456*"},
        headers=_en(tienda_b["slug"]),
    )
    assert res.status_code == 201, res.text
    # Cada tienda con su propia cuenta y contraseña
    assert _token("cliente@fashionstore.com", "OtraClave456*", tienda_b["slug"])
    assert _token("cliente@fashionstore.com", "Cliente123*")


def test_rls_aisla_aunque_la_consulta_no_pase_por_el_orm(tienda_b):
    # SQL crudo: el filtro del ORM no actúa, solo queda Postgres para proteger los datos
    with SessionLocal(info={CLAVE_TIENDA: tienda_b["id"]}) as db:
        assert db.execute(text("SELECT count(*) FROM prenda")).scalar() == 0
        assert db.execute(text("SELECT count(*) FROM usuario WHERE correo = 'admin@fashionstore.com'")).scalar() == 0
        assert db.execute(text("SELECT DISTINCT tienda_id FROM rol")).scalars().all() == [tienda_b["id"]]

    with SessionLocal(info={CLAVE_TIENDA: tienda_b["id"]}) as db:
        with pytest.raises(DBAPIError, match="row-level security"):
            db.execute(text("INSERT INTO categoria (nombre, estado, tienda_id) VALUES ('Intrusa', true, 1)"))


def test_tienda_inexistente_o_suspendida(tienda_b):
    assert client.get("/api/v1/prendas", headers=_en("no-existe-esta-tienda")).status_code == 404

    with engine.begin() as conn:
        conn.execute(text("UPDATE tienda SET estado = 'suspendida' WHERE id = :t"), {"t": tienda_b["id"]})
    olvidar_tienda(tienda_b["slug"])
    try:
        res = client.get("/api/v1/prendas", headers=_en(tienda_b["slug"]))
        assert res.status_code == 403
    finally:
        with engine.begin() as conn:
            conn.execute(text("UPDATE tienda SET estado = 'activa' WHERE id = :t"), {"t": tienda_b["id"]})
        olvidar_tienda(tienda_b["slug"])


@pytest.mark.parametrize("slug, codigo", [("ab", 422), ("Con Espacios", 422), ("plataforma", 409), ("fashionstore", 409)])
def test_direcciones_de_tienda_invalidas_o_tomadas(slug, codigo):
    from fastapi import HTTPException

    with SessionLocal() as db, pytest.raises(HTTPException) as error:
        crear_tienda(db, slug=slug, nombre="X", correo_admin="x@x.com", password_admin=PASSWORD)
    assert error.value.status_code == codigo
