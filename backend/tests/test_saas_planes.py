"""SaaS: alta pública de tiendas, marca de la tienda, límites y funciones por plan, cambio de plan
con Stripe (simulado, nunca se le pega a Stripe) y administración de tiendas por el superadmin."""
import time
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.security import get_password_hash
from app.db.session import engine
from app.main import app

client = TestClient(app)
PASSWORD = "ClaveSegura123*"


@pytest.fixture
def tienda_nueva(borrar_tienda):
    """Una tienda recién dada de alta por el formulario público (plan Gratis)."""
    ts = int(time.time() * 1000)
    res = client.post("/api/v1/plataforma/registro", json={
        "nombre_tienda": "Boutique Prueba", "slug": f"saas-{ts}", "correo": f"dueno{ts}@boutique.com", "password": PASSWORD,
    })
    assert res.status_code == 201, res.text
    datos = res.json()
    headers = {"X-Tienda": datos["slug"], "Authorization": f"Bearer {datos['access_token']}"}
    with engine.connect() as conn:
        tienda_id = conn.execute(text("SELECT id FROM tienda WHERE slug = :s"), {"s": datos["slug"]}).scalar()
    yield {"slug": datos["slug"], "id": tienda_id, "headers": headers}
    borrar_tienda(tienda_id)


def _sucursal(n: int) -> dict:
    return {"nombre": f"Sucursal {n} {int(time.time() * 1000)}", "ciudad_id": 1, "direccion": "Av. Siempre Viva 123"}


def test_el_alta_deja_al_dueno_con_sesion_en_su_tienda(tienda_nueva):
    yo = client.get("/api/v1/auth/me", headers=tienda_nueva["headers"])
    assert yo.status_code == 200
    assert yo.json()["roles"] == ["Administrador"]

    marca = client.get("/api/v1/tienda", headers={"X-Tienda": tienda_nueva["slug"]}).json()
    assert marca["nombre"] == "Boutique Prueba"
    assert marca["plan"] == "gratis"
    assert marca["funciones"] == {"ia": False, "vestidor_ar": False, "pago_qr": False}


def test_la_direccion_ya_tomada_no_esta_disponible(tienda_nueva):
    assert client.get(f"/api/v1/plataforma/disponible/{tienda_nueva['slug']}").json()["disponible"] is False
    assert client.get(f"/api/v1/plataforma/disponible/libre-{int(time.time() * 1000)}").json()["disponible"] is True


def test_la_tienda_original_conserva_todas_sus_funciones():
    marca = client.get("/api/v1/tienda").json()
    assert marca["slug"] == "fashionstore"
    assert marca["plan"] == "empresa"
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


def test_el_plan_gratis_limita_sucursales_y_funciones(tienda_nueva):
    headers = tienda_nueva["headers"]
    assert client.post("/api/v1/sucursales", json=_sucursal(1), headers=headers).status_code == 201
    segunda = client.post("/api/v1/sucursales", json=_sucursal(2), headers=headers)
    assert segunda.status_code == 402
    assert "Gratis" in segunda.json()["detail"]

    chat = client.post("/api/v1/ia/chat", json={"mensaje": "hola"}, headers={"X-Tienda": tienda_nueva["slug"]})
    assert chat.status_code == 402

    uso = client.get("/api/v1/tienda/plan", headers=headers).json()
    assert uso["plan"]["codigo"] == "gratis"
    assert uso["uso"]["sucursales"] == 1
    assert [p["codigo"] for p in uso["planes_disponibles"]] == ["gratis", "pro", "empresa"]


def test_pasar_a_pro_con_stripe_habilita_las_funciones(tienda_nueva):
    headers = tienda_nueva["headers"]

    class _Sesion(dict):
        url = "https://checkout.stripe.com/c/pay/cs_test_123"

    with patch("app.services.suscripciones_service.settings.stripe_secret_key", "sk_test_falsa"), \
         patch("stripe.checkout.Session.create", return_value=_Sesion()) as crear:
        res = client.post("/api/v1/tienda/plan", json={"plan_codigo": "pro"}, headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["url"].startswith("https://checkout.stripe.com")
    enviado = crear.call_args.kwargs
    assert enviado["mode"] == "subscription"
    assert enviado["metadata"] == {"tienda_id": str(tienda_nueva["id"]), "plan_codigo": "pro"}
    assert f"/t/{tienda_nueva['slug']}/admin?suscripcion=ok" in enviado["success_url"]

    pagada = {
        "status": "complete", "customer": "cus_123", "metadata": {"tienda_id": str(tienda_nueva["id"]), "plan_codigo": "pro"},
        "subscription": {"id": "sub_123", "status": "active", "current_period_end": int(datetime(2026, 11, 15, tzinfo=timezone.utc).timestamp())},
    }
    with patch("stripe.checkout.Session.retrieve", return_value=pagada):
        res = client.post("/api/v1/tienda/plan/confirmar", json={"session_id": "cs_test_123"}, headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["plan"]["codigo"] == "pro"
    assert res.json()["periodo_fin"].startswith("2026-11-15")

    with patch("app.api.v1.endpoints.ia.llamar_groq", return_value="¡Hola! ¿En qué te ayudo?"):
        chat = client.post("/api/v1/ia/chat", json={"mensaje": "hola"}, headers={"X-Tienda": tienda_nueva["slug"]})
    assert chat.status_code == 200, chat.text


def test_un_pago_de_otra_tienda_no_sirve_para_confirmar(tienda_nueva):
    ajena = {"status": "complete", "metadata": {"tienda_id": "1", "plan_codigo": "empresa"}, "subscription": {}}
    with patch("stripe.checkout.Session.retrieve", return_value=ajena):
        res = client.post("/api/v1/tienda/plan/confirmar", json={"session_id": "cs_ajena"}, headers=tienda_nueva["headers"])
    assert res.status_code == 400


def test_el_superadmin_ve_y_suspende_tiendas(tienda_nueva):
    ts = int(time.time() * 1000)
    correo = f"super{ts}@plataforma.com"
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO usuario (tienda_id, correo, password_hash, estado, es_superadmin, creado_en) "
            "VALUES (NULL, :c, :h, true, true, now())"
        ), {"c": correo, "h": get_password_hash(PASSWORD)})

    # Una cuenta de tienda no entra a la plataforma, ni la plataforma sin sesión
    assert client.get("/api/v1/plataforma/tiendas").status_code == 401
    assert client.get("/api/v1/plataforma/tiendas", headers={"Authorization": tienda_nueva["headers"]["Authorization"]}).status_code == 401

    token = client.post("/api/v1/plataforma/login", json={"correo": correo, "password": PASSWORD}).json()["access_token"]
    super_h = {"Authorization": f"Bearer {token}"}
    tiendas = client.get("/api/v1/plataforma/tiendas", headers=super_h).json()
    assert {"fashionstore", tienda_nueva["slug"]} <= {t["slug"] for t in tiendas}

    res = client.patch(f"/api/v1/plataforma/tiendas/{tienda_nueva['id']}", json={"estado": "suspendida", "plan_codigo": "pro"}, headers=super_h)
    assert res.status_code == 200, res.text
    assert (res.json()["estado"], res.json()["plan"]) == ("suspendida", "Pro")
    assert client.get("/api/v1/prendas", headers={"X-Tienda": tienda_nueva["slug"]}).status_code == 403

    # Y la cuenta de plataforma no sirve dentro de una tienda
    assert client.get("/api/v1/auth/me", headers=super_h).status_code in (401, 404)


def test_el_webhook_de_stripe_exige_firma():
    res = client.post("/api/v1/plataforma/stripe/webhook", content=b"{}", headers={"stripe-signature": "falsa"})
    assert res.status_code in (400, 503)
