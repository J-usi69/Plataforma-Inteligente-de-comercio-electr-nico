from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _login(login: str, password: str) -> str:
    res = client.post("/api/v1/auth/login", json={"login": login, "password": password})
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_cu27_admin_ve_inventario_global_de_todas_las_sucursales():
    token = _login("admin@fashionstore.com", "Admin123*")
    res = client.get("/api/v1/reportes/inventario-global", headers=_headers(token))
    assert res.status_code == 200, res.text
    datos = res.json()
    assert len(datos) > 0
    item = datos[0]
    assert {"variante_id", "sucursal_id", "ciudad_id", "stock_disponible", "es_quiebre"} <= item.keys()


def test_cu27_filtro_por_ciudad_reduce_el_listado():
    token = _login("admin@fashionstore.com", "Admin123*")
    todos = client.get("/api/v1/reportes/inventario-global", headers=_headers(token)).json()
    ciudad_id = todos[0]["ciudad_id"]

    filtrado = client.get(
        "/api/v1/reportes/inventario-global",
        headers=_headers(token),
        params={"ciudad_id": ciudad_id},
    ).json()
    assert len(filtrado) > 0
    assert all(item["ciudad_id"] == ciudad_id for item in filtrado)


def test_cu27_filtro_sin_coincidencias_devuelve_vacio():
    token = _login("admin@fashionstore.com", "Admin123*")
    res = client.get(
        "/api/v1/reportes/inventario-global",
        headers=_headers(token),
        params={"ciudad_id": 999999},
    )
    assert res.status_code == 200
    assert res.json() == []


def test_cu27_cliente_no_puede_acceder():
    token = _login("cliente@fashionstore.com", "Cliente123*")
    res = client.get("/api/v1/reportes/inventario-global", headers=_headers(token))
    assert res.status_code == 403
