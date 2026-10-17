"""La segunda empresa de prueba (seed_empresa_demo.py): existe con el plan Básico, tiene sus
propios datos y no ve ni se mezcla con los de FashionStore."""
import pytest
from fastapi.testclient import TestClient

import seed_empresa_demo
from app.main import app

client = TestClient(app)
EN_MODA_ANDINA = {"X-Tienda": seed_empresa_demo.SLUG}


@pytest.fixture(scope="module", autouse=True)
def empresa_demo():
    seed_empresa_demo.seed()  # si ya existe (base de pruebas armada con ella) no cambia nada


def _token(correo: str, password: str, headers: dict | None = None) -> str:
    res = client.post("/api/v1/auth/login", json={"login": correo, "password": password}, headers=headers or {})
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


def test_la_segunda_empresa_tiene_el_plan_basico_y_su_marca():
    marca = client.get("/api/v1/tienda", headers=EN_MODA_ANDINA).json()
    assert (marca["nombre"], marca["plan"], marca["color_primario"]) == ("Moda Andina", "basico", "#0F766E")
    assert marca["funciones"]["reportes_ia"] is False


def test_cada_empresa_ve_solo_su_catalogo_y_sus_sucursales():
    prendas_andina = {p["nombre"] for p in client.get("/api/v1/prendas", headers=EN_MODA_ANDINA).json()}
    prendas_fashion = {p["nombre"] for p in client.get("/api/v1/prendas").json()}
    assert len(prendas_andina) == len(seed_empresa_demo.PRENDAS)
    assert not prendas_andina & prendas_fashion

    sucursales = sorted(s["nombre"] for s in client.get("/api/v1/sucursales", headers=EN_MODA_ANDINA).json())
    assert sucursales == ["Moda Andina Centro", "Moda Andina Cochabamba"]
    assert all(not s["nombre"].startswith("Moda Andina") for s in client.get("/api/v1/sucursales").json())


def test_los_reportes_de_cada_empresa_salen_solo_de_sus_ventas():
    token_andina = _token(f"admin@{seed_empresa_demo.DOMINIO}", "Admin123*", EN_MODA_ANDINA)
    ventas_andina = client.get("/api/v1/reportes/ventas", headers={**EN_MODA_ANDINA, "Authorization": f"Bearer {token_andina}"}).json()
    assert ventas_andina and all(v["sucursal_nombre"].startswith("Moda Andina") for v in ventas_andina)
    assert sum(v["cantidad_ventas"] for v in ventas_andina) > 0

    token_fashion = _token("admin@fashionstore.com", "Admin123*")
    ventas_fashion = client.get("/api/v1/reportes/ventas", headers={"Authorization": f"Bearer {token_fashion}"}).json()
    assert all(not v["sucursal_nombre"].startswith("Moda Andina") for v in ventas_fashion)


def test_las_cuentas_de_una_empresa_no_entran_en_la_otra():
    assert _token(f"cajero@{seed_empresa_demo.DOMINIO}", "Cajero123*", EN_MODA_ANDINA)
    otra = client.post("/api/v1/auth/login", json={"login": f"cajero@{seed_empresa_demo.DOMINIO}", "password": "Cajero123*"})
    assert otra.status_code == 401
