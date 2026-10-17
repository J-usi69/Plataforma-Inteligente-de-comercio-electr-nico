"""SaaS: planes del enunciado (Básico y Profesional) con sus límites y funciones, suscripción con
inicio y vencimiento, cambio de plan y renovación con pago simulado, modo consulta con la
suscripción vencida, cobro opcional con Stripe (simulado: nunca se le pega a Stripe) y la
administración de empresas y planes por el superadmin."""
import json
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.config import settings
from app.core.security import get_password_hash
from app.db.session import engine
from app.db.tenancy import estado_de_suscripcion, olvidar_tienda
from app.main import app
from app.services.suscripciones_service import sumar_meses

client = TestClient(app)
PASSWORD = "ClaveSegura123*"


@pytest.fixture
def tienda_nueva(borrar_tienda):
    """Una empresa recién dada de alta por el formulario público (plan Básico por defecto)."""
    ts = int(time.time() * 1000)
    correo = f"dueno{ts}@boutique.com"
    res = client.post("/api/v1/plataforma/registro", json={
        "nombre_tienda": "Boutique Prueba", "slug": f"saas-{ts}", "correo": correo, "password": PASSWORD,
    })
    assert res.status_code == 201, res.text
    datos = res.json()
    headers = {"X-Tienda": datos["slug"], "Authorization": f"Bearer {datos['access_token']}"}
    with engine.connect() as conn:
        tienda_id = conn.execute(text("SELECT id FROM tienda WHERE slug = :s"), {"s": datos["slug"]}).scalar()
    yield {"slug": datos["slug"], "id": tienda_id, "correo": correo, "headers": headers}
    borrar_tienda(tienda_id)


@pytest.fixture
def superadmin():
    """Sesión de un superadmin de la plataforma (el conftest borra la cuenta al final)."""
    correo = f"super{int(time.time() * 1000)}@plataforma.com"
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO usuario (tienda_id, correo, password_hash, estado, es_superadmin, creado_en) "
            "VALUES (NULL, :c, :h, true, true, now())"
        ), {"c": correo, "h": get_password_hash(PASSWORD)})
    token = client.post("/api/v1/plataforma/login", json={"correo": correo, "password": PASSWORD}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _sucursal(n: int) -> dict:
    return {"nombre": f"Sucursal {n} {int(time.time() * 1000)}", "ciudad_id": 1, "direccion": "Av. Siempre Viva 123"}


def _vencer(tienda: dict) -> None:
    with engine.begin() as conn:
        conn.execute(text("UPDATE suscripcion SET fecha_vencimiento = now() - interval '1 day' WHERE tienda_id = :t"), {"t": tienda["id"]})
    olvidar_tienda(tienda["slug"])


def _pasar_a_profesional(tienda: dict) -> dict:
    res = client.post("/api/v1/tienda/plan", json={"plan_codigo": "profesional"}, headers=tienda["headers"])
    assert res.status_code == 200, res.text
    return res.json()


# --- Planes y alta -------------------------------------------------------------------------

def test_los_planes_son_los_del_enunciado():
    planes = {p["codigo"]: p for p in client.get("/api/v1/plataforma/planes").json()}
    assert list(planes) == ["basico", "profesional"]
    basico, profesional = planes["basico"], planes["profesional"]
    assert (basico["max_sucursales"], profesional["max_sucursales"]) == (2, 10)
    assert (basico["reportes_ia"], profesional["reportes_ia"]) == (False, True)
    # Productos, ventas, reservas, operación offline y reportes convencionales: en los dos
    for plan in (basico, profesional):
        assert plan["operacion_offline"] and plan["reportes"]


def test_el_alta_deja_al_dueno_con_sesion_y_el_primer_mes_contratado(tienda_nueva):
    yo = client.get("/api/v1/auth/me", headers=tienda_nueva["headers"])
    assert yo.status_code == 200
    assert yo.json()["roles"] == ["Administrador"]

    marca = client.get("/api/v1/tienda", headers={"X-Tienda": tienda_nueva["slug"]}).json()
    assert (marca["nombre"], marca["plan"], marca["suscripcion_vigente"]) == ("Boutique Prueba", "basico", True)
    assert marca["funciones"]["reportes_ia"] is False
    assert marca["funciones"]["vestidor_ar"] is True  # las capacidades del primer parcial siguen

    plan = client.get("/api/v1/tienda/plan", headers=tienda_nueva["headers"]).json()
    assert plan["suscripcion"]["estado"] == "activa"
    assert 28 <= plan["suscripcion"]["dias_restantes"] <= 31
    alta = plan["movimientos"][0]
    assert (alta["tipo"], alta["plan"], alta["monto"], alta["origen"]) == ("alta", "Básico", 20.0, "simulado")


def test_la_direccion_ya_tomada_no_esta_disponible(tienda_nueva):
    assert client.get(f"/api/v1/plataforma/disponible/{tienda_nueva['slug']}").json()["disponible"] is False
    assert client.get(f"/api/v1/plataforma/disponible/libre-{int(time.time() * 1000)}").json()["disponible"] is True


def test_la_tienda_original_tiene_el_plan_profesional():
    marca = client.get("/api/v1/tienda").json()
    assert (marca["slug"], marca["plan"]) == ("fashionstore", "profesional")
    assert all(marca["funciones"].values())


def test_el_admin_cambia_la_marca_y_un_cliente_no_puede(tienda_nueva):
    res = client.put("/api/v1/tienda", json={"color_primario": "#0F766E", "nombre": "Boutique Verde"}, headers=tienda_nueva["headers"])
    assert res.status_code == 200, res.text
    assert res.json()["color_primario"] == "#0F766E"
    assert client.put("/api/v1/tienda", json={"color_primario": "rojo"}, headers=tienda_nueva["headers"]).status_code == 422

    client.post("/api/v1/auth/register", json={"correo": "cli@boutique.com", "password": PASSWORD}, headers={"X-Tienda": tienda_nueva["slug"]})
    login = client.post("/api/v1/auth/login", json={"login": "cli@boutique.com", "password": PASSWORD}, headers={"X-Tienda": tienda_nueva["slug"]})
    cliente = {"X-Tienda": tienda_nueva["slug"], "Authorization": f"Bearer {login.json()['access_token']}"}
    assert client.put("/api/v1/tienda", json={"nombre": "Hackeada"}, headers=cliente).status_code == 403


# --- Límites y funciones -------------------------------------------------------------------

def test_el_plan_basico_limita_sucursales_y_no_incluye_reportes_ia(tienda_nueva):
    headers = tienda_nueva["headers"]
    assert client.post("/api/v1/sucursales", json=_sucursal(1), headers=headers).status_code == 201
    assert client.post("/api/v1/sucursales", json=_sucursal(2), headers=headers).status_code == 201
    tercera = client.post("/api/v1/sucursales", json=_sucursal(3), headers=headers)
    assert tercera.status_code == 402
    assert "Básico" in tercera.json()["detail"]

    assert client.post("/api/v1/ia/reportes", json={"prompt": "ventas del mes"}, headers=headers).status_code == 402
    # El asistente con IA del primer parcial sí está en el Básico
    with patch("app.api.v1.endpoints.ia.llamar_groq", return_value="¡Hola! ¿En qué te ayudo?"):
        assert client.post("/api/v1/ia/chat", json={"mensaje": "hola"}, headers={"X-Tienda": tienda_nueva["slug"]}).status_code == 200

    uso = client.get("/api/v1/tienda/plan", headers=headers).json()
    assert (uso["plan"]["codigo"], uso["uso"]["sucursales"]) == ("basico", 2)
    assert [p["codigo"] for p in uso["planes_disponibles"]] == ["basico", "profesional"]


def test_pasar_a_profesional_habilita_reportes_ia_y_queda_en_el_historial(tienda_nueva):
    estado = _pasar_a_profesional(tienda_nueva)
    assert estado["url"] is None  # cobro simulado: aplicado en el acto
    assert estado["estado"]["plan"]["codigo"] == "profesional"
    cambio = estado["estado"]["movimientos"][0]
    assert (cambio["tipo"], cambio["monto"], cambio["origen"], cambio["detalle"]) == ("cambio_plan", 50.0, "simulado", "De Básico a Profesional")

    for n in range(3):
        assert client.post("/api/v1/sucursales", json=_sucursal(n), headers=tienda_nueva["headers"]).status_code == 201
    pedido = json.dumps({"tipo": "ventas", "desde": None, "hasta": None, "sucursal_id": None})
    with patch("app.api.v1.endpoints.ia.llamar_mistral", return_value=pedido):
        res = client.post("/api/v1/ia/reportes", json={"prompt": "ventas por sucursal"}, headers=tienda_nueva["headers"])
    assert res.status_code == 200, res.text


def test_no_se_puede_bajar_a_un_plan_cuyos_limites_ya_se_superan(tienda_nueva):
    _pasar_a_profesional(tienda_nueva)
    for n in range(3):
        client.post("/api/v1/sucursales", json=_sucursal(n), headers=tienda_nueva["headers"])

    res = client.post("/api/v1/tienda/plan", json={"plan_codigo": "basico"}, headers=tienda_nueva["headers"])
    assert res.status_code == 409
    assert "3 sucursales" in res.json()["detail"]
    assert client.post("/api/v1/tienda/plan", json={"plan_codigo": "profesional"}, headers=tienda_nueva["headers"]).status_code == 400


# --- Vencimiento y renovación --------------------------------------------------------------

def test_renovar_suma_los_meses_al_vencimiento_sin_perder_dias(tienda_nueva):
    antes = datetime.fromisoformat(client.get("/api/v1/tienda/plan", headers=tienda_nueva["headers"]).json()["suscripcion"]["fecha_vencimiento"])
    res = client.post("/api/v1/tienda/plan/renovar", json={"meses": 2}, headers=tienda_nueva["headers"])
    assert res.status_code == 200, res.text
    despues = datetime.fromisoformat(res.json()["suscripcion"]["fecha_vencimiento"])
    assert despues == sumar_meses(antes, 2)
    renovacion = res.json()["movimientos"][0]
    assert (renovacion["tipo"], renovacion["monto"]) == ("renovacion", 40.0)


def test_con_la_suscripcion_vencida_la_tienda_queda_en_modo_consulta(tienda_nueva):
    headers = tienda_nueva["headers"]
    _vencer(tienda_nueva)

    assert client.get("/api/v1/tienda", headers={"X-Tienda": tienda_nueva["slug"]}).json()["suscripcion_vigente"] is False
    assert client.get("/api/v1/tienda/plan", headers=headers).json()["suscripcion"]["estado"] == "vencida"
    bloqueada = client.post("/api/v1/sucursales", json=_sucursal(1), headers=headers)
    assert bloqueada.status_code == 402
    assert "modo consulta" in bloqueada.json()["detail"]
    # Consultar, iniciar sesión y renovar siguen funcionando
    assert client.get("/api/v1/prendas", headers=headers).status_code == 200
    login = client.post("/api/v1/auth/login", json={"login": tienda_nueva["correo"], "password": PASSWORD}, headers={"X-Tienda": tienda_nueva["slug"]})
    assert login.status_code == 200

    renovada = client.post("/api/v1/tienda/plan/renovar", json={"meses": 1}, headers=headers)
    assert renovada.json()["suscripcion"]["estado"] == "activa"
    assert renovada.json()["suscripcion"]["dias_restantes"] >= 28  # vencida: el mes cuenta desde hoy
    assert client.post("/api/v1/sucursales", json=_sucursal(1), headers=headers).status_code == 201


# --- Cobro opcional con Stripe -------------------------------------------------------------

def test_con_cobro_por_stripe_el_cambio_pasa_por_checkout(tienda_nueva):
    headers = tienda_nueva["headers"]

    class _Sesion(dict):
        url = "https://checkout.stripe.com/c/pay/cs_test_123"

    with patch.object(settings, "cobro_suscripciones", "stripe"), patch.object(settings, "stripe_secret_key", "sk_test_falsa"), \
         patch("stripe.checkout.Session.create", return_value=_Sesion()) as crear:
        res = client.post("/api/v1/tienda/plan", json={"plan_codigo": "profesional"}, headers=headers)
        assert res.status_code == 200, res.text
        assert res.json()["url"].startswith("https://checkout.stripe.com")
        enviado = crear.call_args.kwargs
        assert enviado["mode"] == "subscription"
        assert enviado["metadata"] == {"tienda_id": str(tienda_nueva["id"]), "plan_codigo": "profesional"}
        assert f"/t/{tienda_nueva['slug']}/admin/plan?suscripcion=ok" in enviado["success_url"]

        pagada = {
            "status": "complete", "customer": "cus_123", "metadata": {"tienda_id": str(tienda_nueva["id"]), "plan_codigo": "profesional"},
            "subscription": {"id": "sub_123", "status": "active", "current_period_end": int(datetime(2026, 12, 15, tzinfo=timezone.utc).timestamp())},
        }
        with patch("stripe.checkout.Session.retrieve", return_value=pagada):
            res = client.post("/api/v1/tienda/plan/confirmar", json={"session_id": "cs_test_123"}, headers=headers)
        assert res.status_code == 200, res.text
        assert res.json()["plan"]["codigo"] == "profesional"
        assert res.json()["suscripcion"]["fecha_vencimiento"].startswith("2026-12-15")
        assert res.json()["movimientos"][0]["origen"] == "stripe"
        # Con Stripe no hay renovación manual: la hace Stripe cada mes
        assert client.post("/api/v1/tienda/plan/renovar", json={"meses": 1}, headers=headers).status_code == 409


def test_un_pago_de_otra_tienda_no_sirve_para_confirmar(tienda_nueva):
    ajena = {"status": "complete", "metadata": {"tienda_id": "1", "plan_codigo": "profesional"}, "subscription": {}}
    with patch("stripe.checkout.Session.retrieve", return_value=ajena):
        res = client.post("/api/v1/tienda/plan/confirmar", json={"session_id": "cs_ajena"}, headers=tienda_nueva["headers"])
    assert res.status_code == 400


def test_el_webhook_de_stripe_exige_firma():
    res = client.post("/api/v1/plataforma/stripe/webhook", content=b"{}", headers={"stripe-signature": "falsa"})
    assert res.status_code in (400, 503)


# --- Superadmin ----------------------------------------------------------------------------

def test_el_superadmin_administra_la_suscripcion_de_una_empresa(tienda_nueva, superadmin):
    # Una cuenta de tienda no entra a la plataforma, ni la plataforma sin sesión
    assert client.get("/api/v1/plataforma/tiendas").status_code == 401
    assert client.get("/api/v1/plataforma/tiendas", headers={"Authorization": tienda_nueva["headers"]["Authorization"]}).status_code == 401

    tiendas = {t["slug"]: t for t in client.get("/api/v1/plataforma/tiendas", headers=superadmin).json()}
    assert tiendas["fashionstore"]["plan_codigo"] == "profesional"
    assert tiendas[tienda_nueva["slug"]]["fecha_vencimiento"] is not None

    url = f"/api/v1/plataforma/tiendas/{tienda_nueva['id']}"
    res = client.patch(url, json={"estado": "suspendida", "plan_codigo": "profesional"}, headers=superadmin)
    assert res.status_code == 200, res.text
    assert (res.json()["estado"], res.json()["plan"]) == ("suspendida", "Profesional")
    assert client.get("/api/v1/prendas", headers={"X-Tienda": tienda_nueva["slug"]}).status_code == 403

    res = client.patch(url, json={"estado": "activa", "estado_suscripcion": "cancelada"}, headers=superadmin)
    assert res.json()["estado_suscripcion"] == "cancelada"
    cancelada = client.post("/api/v1/sucursales", json=_sucursal(1), headers=tienda_nueva["headers"])
    assert cancelada.status_code == 402
    assert "cancelada" in cancelada.json()["detail"]

    res = client.post(f"{url}/renovar", json={"meses": 1}, headers=superadmin)
    assert res.json()["estado_suscripcion"] == "activa"

    historial = client.get("/api/v1/tienda/plan", headers=tienda_nueva["headers"]).json()["movimientos"]
    assert [m["tipo"] for m in historial][:5] == ["renovacion", "cancelacion", "reactivacion", "cambio_plan", "suspension"]
    asignado = historial[3]
    assert (asignado["origen"], asignado["monto"]) == ("plataforma", 0.0)  # asignación de la plataforma: sin cobro

    # Y la cuenta de plataforma no sirve dentro de una tienda
    assert client.get("/api/v1/auth/me", headers=superadmin).status_code in (401, 404)


def test_el_superadmin_registra_empresas_y_configura_los_planes(superadmin, borrar_tienda, tienda_nueva):
    ts = int(time.time() * 1000)
    res = client.post("/api/v1/plataforma/tiendas", json={
        "nombre_tienda": "Alta por la plataforma", "slug": f"alta-{ts}", "correo": f"admin{ts}@alta.com",
        "password": PASSWORD, "plan_codigo": "profesional",
    }, headers=superadmin)
    assert res.status_code == 201, res.text
    assert res.json()["plan_codigo"] == "profesional"
    borrar_tienda(res.json()["id"])

    # Límites configurables desde el backend: rigen en el acto para las tiendas con ese plan
    try:
        res = client.put("/api/v1/plataforma/planes/basico", json={"max_sucursales": 1}, headers=superadmin)
        assert res.status_code == 200, res.text
        assert res.json()["max_sucursales"] == 1
        assert client.post("/api/v1/sucursales", json=_sucursal(1), headers=tienda_nueva["headers"]).status_code == 201
        assert client.post("/api/v1/sucursales", json=_sucursal(2), headers=tienda_nueva["headers"]).status_code == 402
    finally:
        client.put("/api/v1/plataforma/planes/basico", json={"max_sucursales": 2}, headers=superadmin)

    assert client.put("/api/v1/plataforma/planes/basico", json={"nombre": None}, headers=superadmin).status_code == 422
    assert client.put("/api/v1/plataforma/planes/no-existe", json={"precio_mensual": 1}, headers=superadmin).status_code == 404
    assert client.put("/api/v1/plataforma/planes/basico", json={"max_sucursales": 9}, headers=tienda_nueva["headers"]).status_code == 401


# --- Reglas de fechas ----------------------------------------------------------------------

@pytest.mark.parametrize("desde, meses, esperado", [
    (datetime(2026, 1, 31, tzinfo=timezone.utc), 1, datetime(2026, 2, 28, tzinfo=timezone.utc)),
    (datetime(2026, 11, 30, tzinfo=timezone.utc), 3, datetime(2027, 2, 28, tzinfo=timezone.utc)),
    (datetime(2026, 10, 17, 9, 30, tzinfo=timezone.utc), 12, datetime(2027, 10, 17, 9, 30, tzinfo=timezone.utc)),
])
def test_sumar_meses(desde, meses, esperado):
    assert sumar_meses(desde, meses) == esperado


def test_una_suscripcion_activa_con_la_fecha_pasada_esta_vencida():
    ahora = datetime(2026, 10, 17, tzinfo=timezone.utc)
    assert estado_de_suscripcion("activa", ahora - timedelta(seconds=1), ahora) == "vencida"
    assert estado_de_suscripcion("activa", ahora + timedelta(days=1), ahora) == "activa"
    assert estado_de_suscripcion("activa", None, ahora) == "activa"  # sin vencimiento
    assert estado_de_suscripcion("cancelada", ahora + timedelta(days=1), ahora) == "cancelada"
