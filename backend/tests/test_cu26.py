from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

VARIANTE_ID = 3  # variante con inventario seeded en sucursal 1 (ver seed_users.py)


def _login(login: str, password: str) -> str:
    res = client.post("/api/v1/auth/login", json={"login": login, "password": password})
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


def _get_encargado_token() -> str:
    return _login("encargado@fashionstore.com", "Encargado123*")


def _get_cliente_token() -> str:
    return _login("cliente@fashionstore.com", "Cliente123*")


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_cu26_encargado_ve_variantes_de_su_sucursal():
    token = _get_encargado_token()
    res = client.get("/api/v1/inventario/encargado/variantes", headers=_headers(token))
    assert res.status_code == 200, res.text
    assert VARIANTE_ID in [v["variante_id"] for v in res.json()]


def test_cu26_cliente_no_puede_acceder():
    token = _get_cliente_token()
    res = client.get("/api/v1/inventario/encargado/variantes", headers=_headers(token))
    assert res.status_code == 403

    res_post = client.post(
        "/api/v1/inventario/encargado/movimientos",
        headers=_headers(token),
        json={"variante_id": VARIANTE_ID, "tipo": "ingreso", "cantidad": 1},
    )
    assert res_post.status_code == 403


def test_cu26_ingreso_incrementa_y_merma_decrementa_el_stock():
    """Flujo de punta a punta de los pasos 1 a 4 del caso de prueba: se deja el
    stock neto sin cambios (ingreso +N seguido de merma -N) para no ensuciar
    la base compartida."""
    token = _get_encargado_token()

    variantes = client.get("/api/v1/inventario/encargado/variantes", headers=_headers(token)).json()
    stock_inicial = next(v["stock_disponible"] for v in variantes if v["variante_id"] == VARIANTE_ID)

    res_ingreso = client.post(
        "/api/v1/inventario/encargado/movimientos",
        headers=_headers(token),
        json={"variante_id": VARIANTE_ID, "tipo": "ingreso", "cantidad": 3},
    )
    assert res_ingreso.status_code == 200, res_ingreso.text
    assert res_ingreso.json()["stock_disponible"] == stock_inicial + 3

    res_merma = client.post(
        "/api/v1/inventario/encargado/movimientos",
        headers=_headers(token),
        json={"variante_id": VARIANTE_ID, "tipo": "merma", "cantidad": 3},
    )
    assert res_merma.status_code == 200, res_merma.text
    assert res_merma.json()["stock_disponible"] == stock_inicial


def test_cu26_excepcion_merma_mayor_al_stock_disponible_es_rechazada():
    token = _get_encargado_token()

    variantes = client.get("/api/v1/inventario/encargado/variantes", headers=_headers(token)).json()
    stock_actual = next(v["stock_disponible"] for v in variantes if v["variante_id"] == VARIANTE_ID)

    res = client.post(
        "/api/v1/inventario/encargado/movimientos",
        headers=_headers(token),
        json={"variante_id": VARIANTE_ID, "tipo": "merma", "cantidad": stock_actual + 1000},
    )
    assert res.status_code == 400
    assert "Stock insuficiente" in res.json()["detail"]
    assert str(stock_actual) in res.json()["detail"]

    # El stock no debe haber cambiado tras el rechazo.
    variantes_despues = client.get("/api/v1/inventario/encargado/variantes", headers=_headers(token)).json()
    stock_despues = next(v["stock_disponible"] for v in variantes_despues if v["variante_id"] == VARIANTE_ID)
    assert stock_despues == stock_actual
