"""Respaldo y restauración (característica 6), bitácora (característica 3) y reportes
personalizables de cada empresa (característica 5).

El administrador de cada empresa respalda y restaura los datos de su empresa y ve su bitácora;
el superadmin respalda y restaura cualquier empresa o el sistema completo y ve la bitácora de
todas las empresas y de la plataforma."""
import gzip
import json
import time
from datetime import date
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.security import get_password_hash
from app.db.session import engine
from app.main import app
from app.services import empresa_reportes_service
from app.services.ia_service import IAServiceError

client = TestClient(app)
PASSWORD = "ClaveSegura123*"
BASE = "/api/v1/plataforma"


def _registrar(nombre: str) -> dict:
    ts = int(time.time() * 1000)
    correo = f"dueno{ts}@respaldo.com"
    res = client.post(f"{BASE}/registro", json={
        "nombre_tienda": f"{nombre} {ts}", "slug": f"resp-{ts}", "correo": correo, "password": PASSWORD,
    })
    assert res.status_code == 201, res.text
    datos = res.json()
    with engine.connect() as conn:
        tienda_id = conn.execute(text("SELECT id FROM tienda WHERE slug = :s"), {"s": datos["slug"]}).scalar()
    headers = {"X-Tienda": datos["slug"], "Authorization": f"Bearer {datos['access_token']}"}
    return {"id": tienda_id, "slug": datos["slug"], "nombre": f"{nombre} {ts}", "correo": correo, "headers": headers}


@pytest.fixture
def tienda_nueva(borrar_tienda):
    tienda = _registrar("Respaldo")
    yield tienda
    borrar_tienda(tienda["id"])


@pytest.fixture
def otra_tienda(borrar_tienda):
    tienda = _registrar("Otra")
    yield tienda
    borrar_tienda(tienda["id"])


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


def _abrir(contenido: bytes) -> dict:
    return json.loads(gzip.decompress(contenido))


def _cerrar(datos: dict) -> bytes:
    return gzip.compress(json.dumps(datos).encode("utf-8"))


def _subir(url: str, contenido: bytes, headers: dict, simular: bool = False):
    return client.post(
        url, headers=headers, data={"simular": "true" if simular else "false"},
        files={"archivo": ("respaldo.json.gz", contenido, "application/gzip")},
    )


def _respaldo(tienda: dict) -> bytes:
    res = client.get("/api/v1/respaldo", headers=tienda["headers"])
    assert res.status_code == 200, res.text
    assert res.headers["content-disposition"].startswith(f'attachment; filename="respaldo_{tienda["slug"]}_')
    return res.content


def _filas(datos: dict, tabla: str) -> list[dict]:
    t = datos["tablas"][tabla]
    return [dict(zip(t["columnas"], fila)) for fila in t["filas"]]


def _acciones(tienda_id: int) -> list[str]:
    with engine.connect() as conn:
        return list(conn.execute(text("SELECT accion FROM bitacora WHERE tienda_id = :t ORDER BY id"), {"t": tienda_id}).scalars())


# --- Respaldo y restauración de una empresa ---------------------------------------------------

def test_el_respaldo_es_solo_del_administrador(tienda_nueva):
    assert client.get("/api/v1/respaldo", headers={"X-Tienda": tienda_nueva["slug"]}).status_code == 401
    slug = tienda_nueva["slug"]
    correo = f"cli{int(time.time() * 1000)}@resp.com"
    assert client.post("/api/v1/auth/register", json={"correo": correo, "password": PASSWORD}, headers={"X-Tienda": slug}).status_code == 201
    token = client.post("/api/v1/auth/login", json={"login": correo, "password": PASSWORD}, headers={"X-Tienda": slug}).json()["access_token"]
    cliente = {"X-Tienda": slug, "Authorization": f"Bearer {token}"}
    assert client.get("/api/v1/respaldo", headers=cliente).status_code == 403
    assert _subir("/api/v1/respaldo/restaurar", b"x", cliente).status_code == 403


def test_el_respaldo_trae_todos_los_datos_de_la_empresa_y_ninguno_de_otra(tienda_nueva, otra_tienda):
    datos = _abrir(_respaldo(tienda_nueva))
    assert datos["formato"] == "fashionstore-respaldo" and datos["alcance"] == "empresa"
    assert datos["tienda"]["id"] == tienda_nueva["id"]
    assert {"usuario", "rol", "rol_permiso", "usuario_rol", "bitacora", "venta", "prenda"} <= set(datos["tablas"])
    # La suscripción y el plan no son de la empresa (no se pueden restaurar) y los tokens push no se respaldan
    assert not {"suscripcion", "movimiento_suscripcion", "plan", "tienda", "push_token"} & set(datos["tablas"])
    for tabla in datos["tablas"]:
        assert all(f["tienda_id"] == tienda_nueva["id"] for f in _filas(datos, tabla)), tabla
    assert [u["correo"] for u in _filas(datos, "usuario")] == [tienda_nueva["correo"]]
    assert "Respaldo de la empresa descargado" in _acciones(tienda_nueva["id"])[-1]


def test_restaurar_vuelve_los_datos_al_respaldo_y_conserva_la_bitacora(tienda_nueva):
    contenido = _respaldo(tienda_nueva)
    ts = int(time.time() * 1000)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO categoria (tienda_id, nombre, estado) VALUES (:t, 'Creada después', true)"), {"t": tienda_nueva["id"]})
        nuevo = conn.execute(text(
            "INSERT INTO usuario (tienda_id, correo, password_hash, estado, es_superadmin, creado_en) "
            "VALUES (:t, :c, 'x', true, false, now()) RETURNING id"
        ), {"t": tienda_nueva["id"], "c": f"nuevo{ts}@respaldo.com"}).scalar()
        conn.execute(text("INSERT INTO bitacora (tienda_id, usuario_id, accion, fecha) VALUES (:t, :u, 'Acción posterior', now())"),
                     {"t": tienda_nueva["id"], "u": nuevo})

    def categorias() -> list[str]:
        with engine.connect() as conn:
            return list(conn.execute(text("SELECT nombre FROM categoria WHERE tienda_id = :t"), {"t": tienda_nueva["id"]}).scalars())

    simulado = _subir("/api/v1/respaldo/restaurar", contenido, tienda_nueva["headers"], simular=True)
    assert simulado.status_code == 200, simulado.text
    assert simulado.json()["simulado"] is True and simulado.json()["usuarios_desactivados"] == 1
    assert "Creada después" in categorias()  # simular no cambia nada

    res = _subir("/api/v1/respaldo/restaurar", contenido, tienda_nueva["headers"])
    assert res.status_code == 200, res.text
    resultado = res.json()
    assert resultado["simulado"] is False and resultado["alcance"] == "empresa" and resultado["usuarios_desactivados"] == 1
    assert "Creada después" not in categorias()
    with engine.connect() as conn:
        estados = dict(conn.execute(text("SELECT correo, estado FROM usuario WHERE tienda_id = :t"), {"t": tienda_nueva["id"]}).all())
    assert estados == {tienda_nueva["correo"]: True, f"nuevo{ts}@respaldo.com": False}
    acciones = _acciones(tienda_nueva["id"])
    # La bitácora no vuelve atrás: queda lo anterior, lo posterior al respaldo y la restauración
    assert "Acción posterior" in acciones and any("Respaldo de la empresa descargado" in a for a in acciones)
    assert acciones[-1].startswith("Empresa restaurada desde el respaldo del")
    # Con los datos restaurados, la empresa sigue funcionando
    assert client.get("/api/v1/auth/me", headers=tienda_nueva["headers"]).status_code == 200


def test_no_se_restaura_un_respaldo_de_otra_empresa_ni_uno_adulterado(tienda_nueva, otra_tienda):
    url = "/api/v1/respaldo/restaurar"
    propio = _abrir(_respaldo(tienda_nueva))
    ajeno = _respaldo(otra_tienda)
    assert "otra empresa" in _subir(url, ajeno, tienda_nueva["headers"]).json()["detail"]
    assert _subir(url, b"no es un respaldo", tienda_nueva["headers"]).status_code == 422

    # Filas de otra empresa dentro del respaldo propio
    adulterado = json.loads(json.dumps(propio))
    columnas = adulterado["tablas"]["rol"]["columnas"]
    adulterado["tablas"]["rol"]["filas"][0][columnas.index("tienda_id")] = otra_tienda["id"]
    assert "filas de otra empresa" in _subir(url, _cerrar(adulterado), tienda_nueva["headers"]).json()["detail"]

    # Una cuenta de superadmin colada en el respaldo de una empresa
    adulterado = json.loads(json.dumps(propio))
    columnas = adulterado["tablas"]["usuario"]["columnas"]
    adulterado["tablas"]["usuario"]["filas"][0][columnas.index("es_superadmin")] = True
    assert "cuentas de la plataforma" in _subir(url, _cerrar(adulterado), tienda_nueva["headers"]).json()["detail"]

    # Un rol de otra empresa asignado a una cuenta propia
    with engine.connect() as conn:
        rol_ajeno = conn.execute(text("SELECT id FROM rol WHERE tienda_id = :t LIMIT 1"), {"t": otra_tienda["id"]}).scalar()
    adulterado = json.loads(json.dumps(propio))
    columnas = adulterado["tablas"]["usuario_rol"]["columnas"]
    adulterado["tablas"]["usuario_rol"]["filas"][0][columnas.index("rol_id")] = rol_ajeno
    res = _subir(url, _cerrar(adulterado), tienda_nueva["headers"])
    assert res.status_code == 422 and "no es de esta empresa" in res.json()["detail"]

    # Restaurar el sistema es solo del superadmin
    assert _subir(f"{BASE}/respaldo/restaurar", _cerrar(propio), {}).status_code == 401


# --- Superadmin: respaldo de empresas y del sistema ---------------------------------------------

def test_el_superadmin_respalda_y_restaura_empresas_y_el_sistema(superadmin, tienda_nueva):
    res = client.get(f"{BASE}/tiendas/{tienda_nueva['id']}/respaldo", headers=superadmin)
    assert res.status_code == 200, res.text
    assert _abrir(res.content)["tienda"]["id"] == tienda_nueva["id"]
    restaurada = _subir(f"{BASE}/tiendas/{tienda_nueva['id']}/respaldo/restaurar", res.content, superadmin)
    assert restaurada.status_code == 200, restaurada.text
    assert restaurada.json()["empresa"] == tienda_nueva["nombre"]

    sistema = client.get(f"{BASE}/respaldo", headers=superadmin)
    assert sistema.status_code == 200, sistema.text
    datos = _abrir(sistema.content)
    assert datos["alcance"] == "sistema" and {"tienda", "plan", "suscripcion", "usuario", "bitacora"} <= set(datos["tablas"])
    assert tienda_nueva["slug"] in [t["slug"] for t in _filas(datos, "tienda")]

    simulado = _subir(f"{BASE}/respaldo/restaurar", sistema.content, superadmin, simular=True)
    assert simulado.status_code == 200, simulado.text
    assert simulado.json()["simulado"] is True and simulado.json()["empresas_suspendidas"] == 0
    # Uno de empresa no sirve para el sistema, ni el del sistema para una empresa
    assert "una empresa" in _subir(f"{BASE}/respaldo/restaurar", res.content, superadmin).json()["detail"]
    assert "sistema completo" in _subir(f"{BASE}/tiendas/{tienda_nueva['id']}/respaldo/restaurar", sistema.content, superadmin).json()["detail"]
    assert client.get(f"{BASE}/respaldo").status_code == 401


# --- Bitácora -----------------------------------------------------------------------------------

def test_el_superadmin_ve_la_bitacora_de_la_plataforma_y_de_todas_las_empresas(superadmin, tienda_nueva):
    client.post("/api/v1/auth/login", json={"login": tienda_nueva["correo"], "password": PASSWORD}, headers={"X-Tienda": tienda_nueva["slug"]})
    plataforma = client.get(f"{BASE}/reportes/bitacora", headers=superadmin, params={
        "criterio": ["Empresa|igual|Plataforma", "Acción|contiene|inicio de sesion en la plataforma"],
    })
    assert plataforma.status_code == 200, plataforma.text
    reporte = plataforma.json()
    assert reporte["columnas"] == ["Fecha", "Empresa", "Usuario", "Rol", "IP", "Acción"]
    assert reporte["filas"] and all(f[3] == "Superadmin" for f in reporte["filas"])

    empresa = client.get(f"{BASE}/reportes/bitacora", headers=superadmin, params={
        "criterio": f"Empresa|igual|{tienda_nueva['nombre']}", "columnas": ["Usuario", "Rol", "Acción"],
    }).json()
    assert [tienda_nueva["correo"], "Administrador", "Inicio de sesión"] in empresa["filas"]


def test_cada_administrador_ve_solo_la_bitacora_de_su_empresa(tienda_nueva, otra_tienda):
    for tienda in (tienda_nueva, otra_tienda):
        client.post("/api/v1/auth/login", json={"login": tienda["correo"], "password": PASSWORD}, headers={"X-Tienda": tienda["slug"]})
    res = client.get("/api/v1/reportes/personalizados/bitacora", headers=tienda_nueva["headers"])
    assert res.status_code == 200, res.text
    reporte = res.json()
    assert reporte["columnas"] == ["Fecha", "Usuario", "Rol", "IP", "Acción"]
    assert {f[1] for f in reporte["filas"]} == {tienda_nueva["correo"]}
    pdf = client.get("/api/v1/reportes/personalizados/bitacora/exportar", headers=tienda_nueva["headers"], params={"formato": "pdf"})
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")


def test_la_bitacora_es_de_los_administradores_no_del_encargado():
    assert "bitacora" in empresa_reportes_service.reportes_para(["Administrador"])
    assert "bitacora" not in empresa_reportes_service.reportes_para(["Encargado"])
    assert "ventas" in empresa_reportes_service.reportes_para(["Encargado"])


# --- Reportes personalizables de la empresa -----------------------------------------------------

def test_el_administrador_arma_y_exporta_los_reportes_de_su_empresa(tienda_nueva):
    headers = tienda_nueva["headers"]
    catalogo = {r["tipo"]: r for r in client.get("/api/v1/reportes/personalizados", headers=headers).json()}
    assert set(catalogo) == {"ventas", "prendas", "inventario", "reservas", "personal", "movimientos", "bitacora"}
    for tipo in catalogo:
        res = client.get(f"/api/v1/reportes/personalizados/{tipo}", headers=headers)
        assert res.status_code == 200, (tipo, res.text)
        assert res.json()["columnas"] == catalogo[tipo]["columnas"]
    elegido = client.get("/api/v1/reportes/personalizados/personal", headers=headers, params={
        "columnas": ["Correo", "Ventas"], "criterio": "Ventas|menor|1", "orden": "Correo",
    })
    assert elegido.status_code == 200, elegido.text
    assert elegido.json()["columnas"] == ["Correo", "Ventas"]
    for formato, firma in (("excel", b"PK"), ("pdf", b"%PDF"), ("html", b"<!doctype html>")):
        archivo = client.get("/api/v1/reportes/personalizados/ventas/exportar", headers=headers, params={"formato": formato})
        assert archivo.status_code == 200 and archivo.content.startswith(firma), formato
    assert any(a.startswith("Reporte exportado: Ventas") for a in _acciones(tienda_nueva["id"]))
    assert client.get("/api/v1/reportes/personalizados/no-existe", headers=headers).status_code == 404


def test_los_valores_que_inventa_la_ia_se_corrigen_o_se_descartan():
    # «Agotado» no existe (vaciaría el reporte): se descarta; los parecidos se escriben como el real
    opciones = empresa_reportes_service.opciones_desde_ia(["Administrador"], {"tipo": "inventario", "criterios": [
        {"columna": "Estado", "operador": "igual", "valor": "Agotado"},
        {"columna": "Estado", "operador": "igual", "valor": "bajo el minimo"},
        {"columna": "Estado", "operador": "igual", "valor": "SIN STOCK"},
        {"columna": "Prenda", "operador": "contiene", "valor": "Polera"},  # sin valores fijos: queda igual
    ]})
    assert [(c.columna, c.valor) for c in opciones["criterios"]] == [
        ("Estado", "Bajo el mínimo"), ("Estado", "Sin stock"), ("Prenda", "Polera"),
    ]
    assert "Bajo el mínimo" in empresa_reportes_service.motor.prompt_interpretacion(
        empresa_reportes_service.REPORTES, date.today(), "x",
    )


def test_el_reporte_con_ia_de_la_empresa_es_del_plan_profesional(tienda_nueva):
    pedido = {"pedido": "prendas sin stock"}
    assert client.post("/api/v1/reportes/personalizados/ia", headers=tienda_nueva["headers"], json=pedido).status_code == 402
    assert client.post("/api/v1/tienda/plan", json={"plan_codigo": "profesional"}, headers=tienda_nueva["headers"]).status_code == 200
    respuesta = '```json\n{"tipo": "inventario", "criterios": [{"columna": "Estado", "operador": "igual", "valor": "Sin stock"}]}\n```'
    with patch("app.services.ia_service.llamar_mistral", side_effect=IAServiceError("401")), \
            patch("app.services.ia_service.llamar_gemini_reportes", return_value=respuesta):
        res = client.post("/api/v1/reportes/personalizados/ia", headers=tienda_nueva["headers"], json=pedido)
    assert res.status_code == 200, res.text
    assert res.json()["opciones"]["tipo"] == "inventario"
    assert res.json()["opciones"]["criterios"] == [{"columna": "Estado", "operador": "igual", "valor": "Sin stock"}]
