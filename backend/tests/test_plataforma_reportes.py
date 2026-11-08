"""Reportes personalizables e indicadores del superadmin (característica 5: el usuario elige
columnas, criterios de selección y orden, y exporta a Excel, PDF, HTML o correo)."""
import time
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.config import settings
from app.core.security import get_password_hash
from app.db.session import engine
from app.main import app

client = TestClient(app)
PASSWORD = "ClaveSegura123*"
BASE = "/api/v1/plataforma"


@pytest.fixture
def tienda_nueva(borrar_tienda):
    ts = int(time.time() * 1000)
    res = client.post(f"{BASE}/registro", json={
        "nombre_tienda": f"Reportes {ts}", "slug": f"rep-{ts}", "correo": f"dueno{ts}@rep.com", "password": PASSWORD,
    })
    assert res.status_code == 201, res.text
    with engine.connect() as conn:
        tienda_id = conn.execute(text("SELECT id FROM tienda WHERE slug = :s"), {"s": res.json()["slug"]}).scalar()
    yield {"id": tienda_id, "nombre": f"Reportes {ts}", "slug": res.json()["slug"]}
    borrar_tienda(tienda_id)


@pytest.fixture
def superadmin():
    correo = f"super{int(time.time() * 1000)}@plataforma.com"
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO usuario (tienda_id, correo, password_hash, estado, es_superadmin, creado_en) "
            "VALUES (NULL, :c, :h, true, true, now())"
        ), {"c": correo, "h": get_password_hash(PASSWORD)})
    token = client.post(f"{BASE}/login", json={"correo": correo, "password": PASSWORD}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_los_reportes_y_los_indicadores_son_solo_del_superadmin(tienda_nueva):
    for url in ("/indicadores", "/reportes", "/reportes/empresas", "/reportes/empresas/exportar?formato=excel"):
        assert client.get(f"{BASE}{url}").status_code == 401, url
    assert client.post(f"{BASE}/reportes/empresas/enviar", json={"destinatario": "a@b.com"}).status_code == 401


def test_el_catalogo_ofrece_los_seis_reportes_con_sus_columnas(superadmin):
    catalogo = {r["tipo"]: r for r in client.get(f"{BASE}/reportes", headers=superadmin).json()}
    assert set(catalogo) == {"empresas", "ingresos", "uso", "ventas", "historial", "bitacora"}
    assert "Plan" in catalogo["empresas"]["columnas"] and catalogo["ingresos"]["columnas_monto"] == ["Monto (USD)"]


def test_el_usuario_elige_columnas_criterios_y_orden(superadmin, tienda_nueva):
    res = client.get(f"{BASE}/reportes/empresas", headers=superadmin, params={
        "columnas": ["Plan", "Empresa"], "criterio": [f"Empresa|contiene|{tienda_nueva['nombre']}", "Plan|igual|basico"],
        "orden": "Empresa", "descendente": "false",
    })
    assert res.status_code == 200, res.text
    reporte = res.json()
    assert reporte["columnas"] == ["Plan", "Empresa"]  # en el orden pedido
    assert reporte["filas"] == [["Básico", tienda_nueva["nombre"]]]  # "basico" coincide sin tilde
    assert "Plan es igual a «basico»" in reporte["filtros"] and "Orden: Empresa (ascendente)" in reporte["filtros"]
    assert reporte["totales"]["Plan"].startswith("TOTAL (1 filas)")

    otro_plan = client.get(f"{BASE}/reportes/empresas", headers=superadmin, params={
        "criterio": [f"Empresa|contiene|{tienda_nueva['nombre']}", "Plan|distinto|Básico"],
    }).json()
    assert otro_plan["filas"] == [] and otro_plan["totales"] is None


def test_los_criterios_numericos_comparan_como_numeros(superadmin):
    todas = client.get(f"{BASE}/reportes/ventas", headers=superadmin).json()
    con_ventas = client.get(f"{BASE}/reportes/ventas", headers=superadmin, params={"criterio": "Ventas|mayor|0"}).json()
    indice = todas["columnas"].index("Ventas")
    assert all(f[indice] > 0 for f in con_ventas["filas"])
    assert len(con_ventas["filas"]) == sum(1 for f in todas["filas"] if f[indice] > 0)
    totales = [f[todas["columnas"].index("Total vendido (Bs.)")] for f in todas["filas"]]
    assert totales == sorted(totales, reverse=True)  # orden por defecto: más vendido primero


def test_opciones_invalidas_se_rechazan_con_un_mensaje_claro(superadmin):
    assert client.get(f"{BASE}/reportes/inventado", headers=superadmin).status_code == 404
    columna = client.get(f"{BASE}/reportes/empresas", headers=superadmin, params={"columnas": "Color"})
    assert columna.status_code == 422 and "Color" in columna.json()["detail"]
    operador = client.get(f"{BASE}/reportes/empresas", headers=superadmin, params={"criterio": "Plan|parecido|x"})
    assert operador.status_code == 422
    fechas = client.get(f"{BASE}/reportes/ingresos", headers=superadmin, params={"desde": "2026-12-01", "hasta": "2026-01-01"})
    assert fechas.status_code == 422


def test_el_alta_queda_en_el_historial_y_en_los_ingresos(superadmin, tienda_nueva):
    filtro = {"criterio": f"Empresa|igual|{tienda_nueva['nombre']}"}
    historial = client.get(f"{BASE}/reportes/historial", headers=superadmin, params=filtro).json()
    movimientos = [dict(zip(historial["columnas"], f)) for f in historial["filas"]]
    assert [m["Movimiento"] for m in movimientos] == ["Alta"]
    assert movimientos[0]["Responsable"] == "La empresa (autoservicio)"
    ingresos = client.get(f"{BASE}/reportes/ingresos", headers=superadmin, params=filtro).json()
    assert ingresos["totales"]["Monto (USD)"] == 20.0  # primer mes del plan Básico


def test_se_exporta_a_excel_pdf_y_html(superadmin, tienda_nueva):
    firmas = {"excel": b"PK", "pdf": b"%PDF", "html": b"<!doctype html>"}
    for formato, firma in firmas.items():
        res = client.get(f"{BASE}/reportes/uso/exportar", headers=superadmin, params={"formato": formato, "columnas": ["Empresa", "Plan"]})
        assert res.status_code == 200, (formato, res.text)
        assert res.content.startswith(firma), formato
        assert "plataforma_uso_" in res.headers["content-disposition"]
    html = client.get(f"{BASE}/reportes/empresas/exportar", headers=superadmin, params={"formato": "html"}).text
    assert tienda_nueva["nombre"] in html and "Empresas y suscripciones" in html


def test_sin_correo_configurado_el_envio_avisa_en_vez_de_fallar(superadmin):
    with patch.object(settings, "brevo_api_key", ""), patch.object(settings, "smtp_host", ""):
        res = client.post(f"{BASE}/reportes/empresas/enviar", headers=superadmin, json={"destinatario": "jefe@empresa.com"})
    assert res.status_code == 503 and "no está configurado" in res.json()["detail"]


def test_el_reporte_se_envia_por_correo_con_el_archivo_adjunto(superadmin):
    respuesta = MagicMock(status_code=201, text="")
    with patch.object(settings, "brevo_api_key", "clave-de-prueba"), patch.object(settings, "correo_remitente", "reportes@fashionstore.com"), \
            patch("app.services.correo_service.httpx.post", return_value=respuesta) as post:
        res = client.post(f"{BASE}/reportes/ingresos/enviar", headers=superadmin, json={
            "destinatario": "jefe@empresa.com", "formato": "excel", "columnas": ["Empresa", "Monto (USD)"],
        })
    assert res.status_code == 200, res.text
    cuerpo = post.call_args.kwargs["json"]
    assert cuerpo["to"] == [{"email": "jefe@empresa.com"}] and cuerpo["subject"] == "FashionStore · Plataforma SaaS · Ingresos por suscripciones"
    assert cuerpo["attachment"][0]["name"].endswith(".xlsx") and "<table>" in cuerpo["htmlContent"]


def test_los_indicadores_cuadran_con_las_empresas(superadmin, tienda_nueva):
    ind = client.get(f"{BASE}/indicadores", headers=superadmin).json()
    tiendas = client.get(f"{BASE}/tiendas", headers=superadmin).json()
    assert ind["empresas"] == len(tiendas)
    assert sum(p["cantidad"] for p in ind["empresas_por_plan"]) == len(tiendas)
    assert len(ind["ingresos_por_mes"]) == 6 and ind["ingresos_mes_actual"] >= 20.0
    assert any(v["empresa"] == tienda_nueva["nombre"] for v in ind["ventas_por_empresa"])


# --- Reporte por comando (texto o voz) interpretado por IA ---------------------------------------

from app.services.ia_service import IAServiceError  # noqa: E402


def _ia(respuesta=None, error=False):
    """Simula los proveedores: Mistral siempre caído (su llave venció) y Gemini con la respuesta dada."""
    mistral = patch("app.services.ia_service.llamar_mistral", side_effect=IAServiceError("401"))
    gemini = patch(
        "app.services.ia_service.llamar_gemini_reportes",
        **({"side_effect": IAServiceError("sin cuota")} if error else {"return_value": respuesta}),
    )
    return mistral, gemini


def test_el_superadmin_pide_un_reporte_con_sus_palabras(superadmin, tienda_nueva):
    respuesta = (
        '```json\n{"tipo": "ingresos", "columnas": ["Empresa", "Monto (USD)", "Color"], '
        f'"criterios": [{{"columna": "Empresa", "operador": "igual", "valor": "{tienda_nueva["nombre"]}"}}, '
        '{"columna": "Inventada", "operador": "igual", "valor": "x"}], '
        '"desde": null, "hasta": null, "orden": "Monto (USD)", "descendente": true}\n```'
    )
    mistral, gemini = _ia(respuesta)
    with mistral, gemini as modelo:
        res = client.post(f"{BASE}/reportes/ia", headers=superadmin, json={"pedido": f"cuánto pagó {tienda_nueva['nombre']}"})
    assert res.status_code == 200, res.text
    datos = res.json()
    # Lo que la IA inventó (la columna Color, el criterio sobre Inventada) se descarta
    assert datos["opciones"]["columnas"] == ["Empresa", "Monto (USD)"]
    assert datos["opciones"]["criterios"] == [{"columna": "Empresa", "operador": "igual", "valor": tienda_nueva["nombre"]}]
    assert datos["reporte"]["filas"] == [[tienda_nueva["nombre"], 20.0]]
    assert "Hoy es" in modelo.call_args.kwargs["system_prompt"]


def test_un_pedido_que_no_es_un_reporte_se_explica(superadmin):
    mistral, gemini = _ia('{"tipo": null}')
    with mistral, gemini:
        res = client.post(f"{BASE}/reportes/ia", headers=superadmin, json={"pedido": "borrá todas las empresas"})
    assert res.status_code == 422 and "Probá, por ejemplo" in res.json()["detail"]


def test_sin_ia_disponible_se_ofrece_el_constructor(superadmin):
    mistral, gemini = _ia(error=True)
    with mistral, gemini:
        res = client.post(f"{BASE}/reportes/ia", headers=superadmin, json={"pedido": "ingresos del mes"})
    assert res.status_code == 503 and "constructor" in res.json()["detail"]


def test_el_reporte_por_comando_es_solo_del_superadmin():
    assert client.post(f"{BASE}/reportes/ia", json={"pedido": "ingresos del mes"}).status_code == 401


def test_criterios_de_la_misma_columna_se_combinan_con_o(superadmin, tienda_nueva):
    """«Plan es Básico» y «Plan es Profesional» trae las de los dos planes; con otra columna se suma la condición."""
    ambos = client.get(f"{BASE}/reportes/empresas", headers=superadmin, params={
        "criterio": ["Plan|igual|Básico", "Plan|igual|Profesional"], "columnas": ["Empresa", "Plan"],
    }).json()
    planes = {f[1] for f in ambos["filas"]}
    assert planes <= {"Básico", "Profesional"} and "Básico" in planes
    una = client.get(f"{BASE}/reportes/empresas", headers=superadmin, params={
        "criterio": ["Plan|igual|Básico", "Plan|igual|Profesional", f"Empresa|igual|{tienda_nueva['nombre']}"],
    }).json()
    assert len(una["filas"]) == 1
