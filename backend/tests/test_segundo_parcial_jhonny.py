"""Pruebas automatizadas del Segundo Examen Parcial (Grupo 7 - Jhonny Durán Marín).

- CU-14: Resolver conflictos de sincronización (CP-10, CP-11)
- CU-16: Generar reporte mediante lenguaje natural (CP-12, CP-14)
- CU-17: Exportar reporte a Excel y PDF (CP-13)
- CU-18: Dashboard de analítica con Machine Learning (CP-15, CP-16)

Se crean dos empresas desechables: A con plan Profesional (dos sucursales, cajero y encargado en la
Central) y B con plan Básico (una sucursal). Al terminar se borran con todo lo suyo.
"""
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.security import get_password_hash
from app.db.session import SessionLocal
from app.db.tenancy import CLAVE_TIENDA
from app.main import app
from app.models.catalogo import Categoria, Color, Prenda, Talla, VariantePrenda
from app.models.inventario import InventarioSucursal
from app.models.seguridad import Bitacora, Rol, Usuario, UsuarioRol
from app.models.sucursal import Ciudad, Personal, Sucursal
from app.services.tiendas_service import crear_tienda

client = TestClient(app)
PASSWORD = "ClaveSegura123*"
PRECIO = 250.0


def _token(correo: str, slug: str) -> str:
    res = client.post("/api/v1/auth/login", json={"login": correo, "password": PASSWORD}, headers={"X-Tienda": slug})
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


@pytest.fixture(scope="module")
def entorno(borrar_tienda):
    marca = int(time.time() * 1000)
    e = {"slug_a": f"empresa-a-{marca}", "slug_b": f"empresa-b-{marca}"}
    admin_a, admin_b = f"admin_a_{marca}@moda.com", f"admin_b_{marca}@moda.com"
    with SessionLocal() as db:
        e["id_a"] = crear_tienda(
            db, slug=e["slug_a"], nombre="Boutique Elegance", correo_admin=admin_a, password_admin=PASSWORD,
            plan_codigo="profesional",
        ).id
    with SessionLocal() as db:
        e["id_b"] = crear_tienda(
            db, slug=e["slug_b"], nombre="Ropa Casual Express", correo_admin=admin_b, password_admin=PASSWORD
        ).id

    ahora = datetime.now(timezone.utc)
    with SessionLocal(info={CLAVE_TIENDA: e["id_a"]}) as db:
        ciudad = db.scalars(select(Ciudad).order_by(Ciudad.id)).first()
        central = Sucursal(nombre=f"Central {marca}", ciudad_id=ciudad.id, direccion="Av. San Martín 100", estado=True)
        norte = Sucursal(nombre=f"Norte {marca}", ciudad_id=ciudad.id, direccion="Av. Banzer 200", estado=True)
        db.add_all([central, norte])
        db.flush()
        roles = {r.nombre: r for r in db.scalars(select(Rol))}
        for clave, rol in (("cajero", "Cajero"), ("encargado", "Encargado")):
            usuario = Usuario(correo=f"{clave}_a_{marca}@moda.com", password_hash=get_password_hash(PASSWORD), estado=True, creado_en=ahora)
            db.add(usuario)
            db.flush()
            db.add(UsuarioRol(usuario_id=usuario.id, rol_id=roles[rol].id))
            db.add(Personal(usuario_id=usuario.id, sucursal_id=central.id, nombres=clave.title(), apellidos="Prueba", cargo=rol, estado=True))
            e[clave] = usuario.correo

        categoria, talla, color = Categoria(nombre="Vestidos", estado=True), Talla(nombre="M"), Color(nombre="Azul", hex="#0000FF")
        db.add_all([categoria, talla, color])
        db.flush()
        prenda = Prenda(nombre="Vestido de fiesta", categoria_id=categoria.id, precio_base=PRECIO, estado=True)
        db.add(prenda)
        db.flush()
        variante = VariantePrenda(prenda_id=prenda.id, talla_id=talla.id, color_id=color.id, codigo_barras=f"J{marca}", estado=True)
        db.add(variante)
        db.flush()
        e.update(central=central.id, norte=norte.id, variante=variante.id)
        db.commit()

    with SessionLocal(info={CLAVE_TIENDA: e["id_b"]}) as db:
        ciudad = db.scalars(select(Ciudad).order_by(Ciudad.id)).first()
        unica = Sucursal(nombre=f"Única {marca}", ciudad_id=ciudad.id, direccion="Calle 3", estado=True)
        db.add(unica)
        db.flush()
        e["sucursal_b"] = unica.id
        db.commit()

    e["tokens"] = {
        "admin": _token(admin_a, e["slug_a"]),
        "cajero": _token(e["cajero"], e["slug_a"]),
        "encargado": _token(e["encargado"], e["slug_a"]),
        "admin_b": _token(admin_b, e["slug_b"]),
    }
    yield e
    borrar_tienda(e["id_a"])
    borrar_tienda(e["id_b"])


def _en(e: dict, rol: str) -> dict:
    return {"Authorization": f"Bearer {e['tokens'][rol]}", "X-Tienda": e["slug_b"] if rol == "admin_b" else e["slug_a"]}


def _poner_stock(e: dict, sucursal: int, cantidad: int) -> None:
    with SessionLocal(info={CLAVE_TIENDA: e["id_a"]}) as db:
        fila = db.scalars(
            select(InventarioSucursal).where(InventarioSucursal.variante_id == e["variante"], InventarioSucursal.sucursal_id == sucursal)
        ).first()
        if fila is None:
            fila = InventarioSucursal(variante_id=e["variante"], sucursal_id=sucursal, stock_minimo=0)
            db.add(fila)
        fila.stock_disponible, fila.stock_reservado = cantidad, 0
        db.commit()


def _stock(e: dict, sucursal: int) -> int:
    with SessionLocal(info={CLAVE_TIENDA: e["id_a"]}) as db:
        fila = db.scalars(
            select(InventarioSucursal).where(InventarioSucursal.variante_id == e["variante"], InventarioSucursal.sucursal_id == sucursal)
        ).first()
        return fila.stock_disponible if fila else 0


def _vender_sin_conexion(e: dict, cantidad: int) -> dict:
    """Venta de contado que el cajero de la Central registró sin conexión y sube al volver."""
    op = {
        "id": str(uuid4()),
        "tipo": "venta",
        "tienda": e["slug_a"],
        "sucursal_id": e["central"],
        "registrada_en": (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat(),
        "dispositivo": "pytest",
        "datos": {
            "detalles": [{"variante_id": e["variante"], "cantidad": cantidad, "precio_unitario": PRECIO}],
            "total": PRECIO * cantidad,
        },
    }
    res = client.post("/api/v1/sync/operaciones", json={"operaciones": [op]}, headers=_en(e, "cajero"))
    assert res.status_code == 200, res.text
    return res.json()["resultados"][0]


def _venta_en_conflicto(e: dict, cantidad: int = 3) -> str:
    """El cajero vendió más de lo que el sistema tiene en la Central (1 unidad)."""
    _poner_stock(e, e["central"], 1)
    resultado = _vender_sin_conexion(e, cantidad)
    assert (resultado["estado"], resultado["codigo"]) == ("conflicto", "sin_stock"), resultado
    return resultado["id"]


def _resolver(e: dict, op_id: str, rol: str = "admin", **cuerpo):
    return client.post(f"/api/v1/sync/operaciones/{op_id}/resolver", json=cuerpo, headers=_en(e, rol))


def _bitacora(e: dict, op_id: str) -> list[str]:
    with SessionLocal(info={CLAVE_TIENDA: e["id_a"]}) as db:
        return list(db.scalars(select(Bitacora.accion).where(Bitacora.accion.like(f"%{op_id}%"))))


# ==============================================================================
# CU-14: RESOLVER CONFLICTOS DE SINCRONIZACIÓN (CP-10, CP-11)
# ==============================================================================
def test_cp10_venta_offline_sin_stock_queda_en_conflicto(entorno):
    """CP-10: si el stock del sistema no alcanza, la venta no se confirma: espera la decisión."""
    op_id = _venta_en_conflicto(entorno)
    conflictos = client.get("/api/v1/sync/operaciones", params={"estado": "conflicto"}, headers=_en(entorno, "admin")).json()
    assert op_id in [c["id"] for c in conflictos]
    assert _stock(entorno, entorno["central"]) == 1  # mientras espera no se toca el inventario


def test_cp11_el_administrador_acepta_el_conflicto_con_ajuste(entorno):
    """CP-11 (aceptar): se registra la venta y el faltante queda en el kardex; queda en bitácora."""
    op_id = _venta_en_conflicto(entorno)
    res = _resolver(entorno, op_id, accion="aceptar", nota="Aprobado con ajuste de kardex")
    assert res.status_code == 200, res.text
    body = res.json()
    assert (body["estado"], body["sucursal_id"], body["referencia_tipo"]) == ("confirmada", entorno["central"], "venta")
    assert body["nota_resolucion"] == "Aprobado con ajuste de kardex"
    assert _bitacora(entorno, op_id) == [f"Sincronización: operación {op_id} aceptada"]
    assert _resolver(entorno, op_id, accion="aceptar").status_code == 409  # ya resuelta


def test_cp11_el_administrador_anula_el_conflicto(entorno):
    """CP-11 (anular): no se registra la venta ni se toca el inventario."""
    op_id = _venta_en_conflicto(entorno)
    res = _resolver(entorno, op_id, accion="anular", nota="Inconsistencia de inventario")
    assert res.status_code == 200, res.text
    assert (res.json()["estado"], res.json()["referencia_id"]) == ("rechazada", None)
    assert _stock(entorno, entorno["central"]) == 1
    assert _bitacora(entorno, op_id) == [f"Sincronización: operación {op_id} anulada"]


def test_cp11_reasignar_descuenta_de_la_sucursal_elegida(entorno):
    """CP-11 (reasignar): la vendió un cajero de la Central, pero la prenda salió del Norte."""
    _poner_stock(entorno, entorno["norte"], 5)
    op_id = _venta_en_conflicto(entorno, cantidad=3)
    res = _resolver(entorno, op_id, accion="reasignar", nueva_sucursal_id=entorno["norte"], nota="Se entregó desde el Norte")
    assert res.status_code == 200, res.text
    body = res.json()
    assert (body["estado"], body["sucursal_id"], body["referencia_tipo"]) == ("confirmada", entorno["norte"], "venta")
    assert body["datos"]["sucursal_id"] == entorno["central"]  # lo que subió el dispositivo queda como llegó
    assert (_stock(entorno, entorno["norte"]), _stock(entorno, entorno["central"])) == (2, 1)
    assert _bitacora(entorno, op_id) == [f"Sincronización: operación {op_id} reasignada a sucursal #{entorno['norte']}"]


def test_cp11_reasignar_exige_sucursal_propia_y_solo_lo_hace_el_administrador(entorno):
    op_id = _venta_en_conflicto(entorno)
    assert _resolver(entorno, op_id, accion="reasignar").status_code == 422  # falta la sucursal de destino
    assert _resolver(entorno, op_id, rol="encargado", accion="reasignar", nueva_sucursal_id=entorno["norte"]).status_code == 403
    # Una sucursal de otra empresa no existe para esta
    ajena = _resolver(entorno, op_id, accion="reasignar", nueva_sucursal_id=entorno["sucursal_b"])
    assert ajena.status_code == 409, ajena.text
    assert "no existe en esta empresa" in ajena.json()["detail"]
    # Nada de lo anterior la resolvió: sigue esperando la decisión
    assert _resolver(entorno, op_id, accion="rechazar").json()["estado"] == "rechazada"


# ==============================================================================
# CU-16: REPORTES MEDIANTE LENGUAJE NATURAL (CP-12, CP-14)
# ==============================================================================
def _reporte_ia(e: dict, rol: str, interpretacion: str, prompt: str):
    # La IA solo traduce el pedido a un JSON; se simula para no depender del proveedor externo
    with patch("app.api.v1.endpoints.ia.llamar_mistral", return_value=interpretacion):
        return client.post("/api/v1/ia/reportes", json={"prompt": prompt}, headers=_en(e, rol))


def test_cp12_reporte_en_lenguaje_natural_con_narrativa(entorno):
    """CP-12: interpreta el pedido, consulta los datos y devuelve narrativa y tipo de gráfico."""
    res = _reporte_ia(entorno, "admin", '{"tipo": "ventas", "desde": null, "hasta": null, "sucursal_id": null}', "Mostrame las ventas por sucursal")
    assert res.status_code == 200, res.text
    body = res.json()
    assert (body["tipo"], body["tipo_grafico"]) == ("ventas", "barras")
    assert isinstance(body["datos"], list)
    assert body["narrativa_ia"].startswith("Se registraron Bs.")


def test_cp12_el_encargado_pide_el_rendimiento_por_categoria(entorno):
    """RF21: cuarto tipo de reporte (rendimiento por categoría), también para el encargado."""
    res = _reporte_ia(
        entorno, "encargado", '{"tipo": "rendimiento_categorias", "desde": null, "hasta": null, "sucursal_id": null}',
        "¿Cuál es el rendimiento de ventas por categoría?",
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert (body["tipo"], body["tipo_grafico"]) == ("rendimiento_categorias", "pastel")
    assert isinstance(body["datos"], list)


def test_cp14_cada_empresa_ve_solo_sus_reportes(entorno):
    """CP-14 (RN02 / RN09): los reportes se limitan a la empresa autenticada."""
    _poner_stock(entorno, entorno["central"], 5)
    assert _vender_sin_conexion(entorno, 1)["estado"] == "confirmada"

    ventas_a = client.get("/api/v1/reportes/ventas", headers=_en(entorno, "admin"))
    assert ventas_a.status_code == 200, ventas_a.text
    assert entorno["central"] in [v["sucursal_id"] for v in ventas_a.json()]

    ventas_b = client.get("/api/v1/reportes/ventas", headers=_en(entorno, "admin_b"))
    assert ventas_b.status_code == 200, ventas_b.text
    assert not {entorno["central"], entorno["norte"]} & {v["sucursal_id"] for v in ventas_b.json()}


# ==============================================================================
# CU-17: EXPORTAR REPORTE (CP-13)
# ==============================================================================
def test_cp13_exportar_reporte_excel(entorno):
    """CP-13: archivo XLSX válido (un ZIP: empieza con PK) descargable."""
    res = client.post(
        "/api/v1/reportes/exportar/excel",
        json={"tipo": "ventas", "formato": "excel", "titulo": "Reporte de Ventas por Sucursal"},
        headers=_en(entorno, "admin"),
    )
    assert res.status_code == 200, res.text
    assert res.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert "attachment; filename=" in res.headers["content-disposition"]
    assert len(res.content) > 1000
    assert res.content[:2] == b"PK"


def test_cp13_exportar_reporte_pdf(entorno):
    """CP-13: documento PDF válido descargable."""
    res = client.post(
        "/api/v1/reportes/exportar/pdf",
        json={"tipo": "rendimiento_categorias", "formato": "pdf", "titulo": "Rendimiento por Categoría"},
        headers=_en(entorno, "admin"),
    )
    assert res.status_code == 200, res.text
    assert res.headers["content-type"] == "application/pdf"
    assert "attachment; filename=" in res.headers["content-disposition"]
    assert res.content.startswith(b"%PDF")


# ==============================================================================
# CU-18: DASHBOARD DE ANALÍTICA CON MACHINE LEARNING (CP-15, CP-16)
# ==============================================================================
def test_cp15_dashboard_analitica_ml_con_plan_profesional(entorno):
    """CP-15 (RF24): predicción de demanda (supervisado), segmentos de clientes (no supervisado)
    y sus métricas (R², MAE, silueta)."""
    res = client.get("/api/v1/reportes/analitica-ml", headers=_en(entorno, "admin"))
    assert res.status_code == 200, res.text
    data = res.json()

    metricas = data["metricas"]
    assert metricas["r2_score"] >= 0.70, metricas
    assert metricas["mae"] > 0
    assert metricas["silhouette_score"] > 0.40, metricas

    predicciones = data["predicciones_demanda"]
    assert len(predicciones) == 4
    for p in predicciones:
        assert p["ventas_proyectadas"] > 0
        assert p["limite_superior"] >= p["ventas_proyectadas"] >= p["limite_inferior"]

    segmentos = data["segmentacion_clientes"]
    assert len(segmentos) == 4
    assert 99.0 <= sum(s["porcentaje"] for s in segmentos) <= 101.0

    # El dashboard de ML es del administrador
    assert client.get("/api/v1/reportes/analitica-ml", headers=_en(entorno, "encargado")).status_code == 403


def test_cp16_plan_basico_no_accede_a_ml_ni_a_reportes_ia(entorno):
    """CP-16 (RF05 / RN03): la función reportes_ia no está en el plan Básico."""
    assert client.get("/api/v1/reportes/analitica-ml", headers=_en(entorno, "admin_b")).status_code == 402
    res_ia = _reporte_ia(entorno, "admin_b", '{"tipo": "ventas"}', "Ventas del mes")
    assert res_ia.status_code == 402
