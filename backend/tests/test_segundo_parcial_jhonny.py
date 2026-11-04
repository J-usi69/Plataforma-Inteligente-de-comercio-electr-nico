"""Pruebas automatizadas del Segundo Examen Parcial (Grupo 7 - Jhonny Durán Marín)
Cubre los casos de uso:
- CU-14: Resolver conflictos de sincronización (CP-10, CP-11)
- CU-16: Generar reporte mediante lenguaje natural (CP-12, CP-14)
- CU-17: Exportar reporte a Excel y PDF (CP-13)
- CU-18: Generar dashboard de analítica con Machine Learning (CP-15, CP-16)
"""
from datetime import datetime, timezone
import time
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
from app.models.sincronizacion import OperacionSync
from app.models.sucursal import Ciudad, Personal, Sucursal
from app.models.tienda import Tienda, Plan
from app.services.sincronizacion_service import CONFLICTO, RECHAZADA
from app.services.tiendas_service import crear_tienda

client = TestClient(app)
PASSWORD = "ClaveSegura123*"


def _token(correo: str, slug: str) -> str:
    res = client.post("/api/v1/auth/login", json={"login": correo, "password": PASSWORD}, headers={"X-Tienda": slug})
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


@pytest.fixture(scope="module")
def entorno_pruebas(borrar_tienda):
    """Crea dos tiendas independientes (Empresa A con plan Profesional, Empresa B con plan Básico)
    para verificar multitenancy (RN02) y restricciones por plan (RN03, RF05)."""
    marca = int(time.time() * 1000)

    # 1. Crear Empresa A (Plan Profesional con reportes_ia y analítica ML)
    slug_a = f"empresa-a-{marca}"
    admin_a = f"admin_a_{marca}@moda.com"
    encargado_a = f"encargado_a_{marca}@moda.com"

    with SessionLocal() as db:
        tienda_a = crear_tienda(db, slug=slug_a, nombre="Boutique Elegance", correo_admin=admin_a, password_admin=PASSWORD)
        plan_pro = db.scalars(select(Plan).where(Plan.nombre == "Profesional")).first()
        if plan_pro:
            tienda_a.plan_id = plan_pro.id
        db.commit()
        id_a = tienda_a.id

    # 2. Crear Empresa B (Plan Básico, sin reportes_ia)
    slug_b = f"empresa-b-{marca}"
    admin_b = f"admin_b_{marca}@tienda.com"

    with SessionLocal() as db:
        tienda_b = crear_tienda(db, slug=slug_b, nombre="Ropa Casual Express", correo_admin=admin_b, password_admin=PASSWORD)
        plan_basico = db.scalars(select(Plan).where(Plan.nombre == "Básico")).first()
        if plan_basico:
            tienda_b.plan_id = plan_basico.id
        db.commit()
        id_b = tienda_b.id

    # Datos iniciales para Empresa A
    ahora = datetime.now(timezone.utc)
    with SessionLocal(info={CLAVE_TIENDA: id_a}) as db:
        ciudad = db.scalars(select(Ciudad).order_by(Ciudad.id)).first()
        suc_1 = Sucursal(nombre=f"Sucursal Central {marca}", ciudad_id=ciudad.id, direccion="Av. San Martín 100", estado=True)
        suc_2 = Sucursal(nombre=f"Sucursal Norte {marca}", ciudad_id=ciudad.id, direccion="Av. Banzer 200", estado=True)
        db.add_all([suc_1, suc_2])
        db.flush()

        cat = Categoria(nombre=f"Vestidos {marca}", estado=True)
        talla = Talla(nombre=f"M-{marca}")
        color = Color(nombre=f"Azul-{marca}", codigo_hex="#0000FF")
        db.add_all([cat, talla, color])
        db.flush()

        prenda = Prenda(nombre=f"Vestido de Fiesta {marca}", precio_base=250.0, categoria_id=cat.id, estado=True)
        db.add(prenda)
        db.flush()

        variante = VariantePrenda(prenda_id=prenda.id, talla_id=talla.id, color_id=color.id, sku=f"SKU-{marca}", precio=250.0)
        db.add(variante)
        db.flush()

        # Inventario limitado en sucursal 1 (stock = 1)
        inv = InventarioSucursal(sucursal_id=suc_1.id, variante_id=variante.id, stock_disponible=1, stock_minimo=2)
        db.add(inv)

        # Usuario Encargado
        rol_encargado = db.scalars(select(Rol).where(Rol.nombre == "Encargado")).first()
        u_enc = Usuario(correo=encargado_a, password_hash=get_password_hash(PASSWORD), estado=True, creado_en=ahora)
        db.add(u_enc)
        db.flush()
        db.add(UsuarioRol(usuario_id=u_enc.id, rol_id=rol_encargado.id))
        db.add(Personal(usuario_id=u_enc.id, sucursal_id=suc_1.id, nombres="Carlos", apellidos="Encargado", cargo="Encargado", estado=True))
        db.commit()

        variante_id = variante.id
        sucursal_1_id = suc_1.id
        sucursal_2_id = suc_2.id

    yield {
        "id_a": id_a,
        "slug_a": slug_a,
        "token_admin_a": _token(admin_a, slug_a),
        "token_encargado_a": _token(encargado_a, slug_a),
        "id_b": id_b,
        "slug_b": slug_b,
        "token_admin_b": _token(admin_b, slug_b),
        "variante_id": variante_id,
        "sucursal_1_id": sucursal_1_id,
        "sucursal_2_id": sucursal_2_id,
    }


# ==============================================================================
# CU-14: RESOLVER CONFLICTOS DE SINCRONIZACIÓN (CP-10, CP-11)
# ==============================================================================

def test_cp10_sincronizar_venta_sin_stock_genera_conflicto(entorno_pruebas):
    """CP-10: Sincronizar una venta offline cuando el stock central no alcanza
    debe dejar la operación en estado 'conflicto' en lugar de confirmarla."""
    token = entorno_pruebas["token_encargado_a"]
    slug = entorno_pruebas["slug_a"]
    op_uuid = str(uuid4())

    payload = {
        "operaciones": [
            {
                "id": op_uuid,
                "tipo": "venta",
                "datos": {
                    "sucursal_id": entorno_pruebas["sucursal_1_id"],
                    "lineas": [
                        {"variante_id": entorno_pruebas["variante_id"], "cantidad": 5, "precio": 250.0}
                    ],
                    "total": 1250.0,
                    "forma_pago": "efectivo",
                    "registrada_en": datetime.now(timezone.utc).isoformat(),
                },
            }
        ]
    }

    res = client.post(
        "/api/v1/sync/operaciones",
        json=payload,
        headers={"Authorization": f"Bearer {token}", "X-Tienda": slug},
    )
    assert res.status_code == 200, res.text
    resultados = res.json()["resultados"]
    assert len(resultados) == 1
    assert resultados[0]["estado"] == "conflicto"
    assert resultados[0]["codigo"] == "sin_stock"


def test_cp11_resolver_conflicto_como_administrador(entorno_pruebas):
    """CP-11: El Administrador de Empresa lista los conflictos de su tenant,
    selecciona uno y lo resuelve (aceptar con ajuste o anular), registrándose en bitácora."""
    token_admin = entorno_pruebas["token_admin_a"]
    slug = entorno_pruebas["slug_a"]

    # 1. Listar operaciones en conflicto
    res_list = client.get(
        "/api/v1/sync/operaciones?estado=conflicto",
        headers={"Authorization": f"Bearer {token_admin}", "X-Tienda": slug},
    )
    assert res_list.status_code == 200
    conflictos = res_list.json()
    assert len(conflictos) >= 1
    conflicto = conflictos[0]
    op_id = conflicto["id"]

    # 2. Resolver conflicto con 'aceptar' (ajuste de stock con faltante en kardex)
    res_resolve = client.post(
        f"/api/v1/sync/operaciones/{op_id}/resolver",
        json={"accion": "aceptar", "nota": "Aprobado por el Administrador con ajuste de kardex"},
        headers={"Authorization": f"Bearer {token_admin}", "X-Tienda": slug},
    )
    assert res_resolve.status_code == 200
    resultado = res_resolve.json()
    assert resultado["estado"] == "confirmada"
    assert resultado["nota_resolucion"] == "Aprobado por el Administrador con ajuste de kardex"

    # 3. Verificar que quedó registrado en la bitácora
    with SessionLocal(info={CLAVE_TIENDA: entorno_pruebas["id_a"]}) as db:
        bit = db.scalars(
            select(Bitacora).where(Bitacora.accion.like(f"%{op_id}%")).order_by(Bitacora.id.desc())
        ).first()
        assert bit is not None
        assert "aceptada" in bit.accion


def test_cp11_anular_conflicto(entorno_pruebas):
    """CP-11 (variante anular): Resolver un conflicto rechazándolo / anulándolo."""
    token_enc = entorno_pruebas["token_encargado_a"]
    token_admin = entorno_pruebas["token_admin_a"]
    slug = entorno_pruebas["slug_a"]
    op_uuid = str(uuid4())

    # Crear otro conflicto
    client.post(
        "/api/v1/sync/operaciones",
        json={
            "operaciones": [
                {
                    "id": op_uuid,
                    "tipo": "venta",
                    "datos": {
                        "sucursal_id": entorno_pruebas["sucursal_1_id"],
                        "lineas": [{"variante_id": entorno_pruebas["variante_id"], "cantidad": 10, "precio": 250.0}],
                        "total": 2500.0,
                        "forma_pago": "efectivo",
                        "registrada_en": datetime.now(timezone.utc).isoformat(),
                    },
                }
            ]
        },
        headers={"Authorization": f"Bearer {token_enc}", "X-Tienda": slug},
    )

    # Anular como admin
    res_anular = client.post(
        f"/api/v1/sync/operaciones/{op_uuid}/resolver",
        json={"accion": "anular", "nota": "Anulación por inconsistencia total de inventario"},
        headers={"Authorization": f"Bearer {token_admin}", "X-Tienda": slug},
    )
    assert res_anular.status_code == 200
    assert res_anular.json()["estado"] == "rechazada"


# ==============================================================================
# CU-16: REPORTES MEDIANTE LENGUAJE NATURAL (CP-12, CP-14)
# ==============================================================================

def test_cp12_generar_reporte_ia_lenguaje_natural(entorno_pruebas, monkeypatch):
    """CP-12: El Administrador o Encargado solicita un reporte en lenguaje natural,
    el sistema interpreta la solicitud, ejecuta la query y devuelve datos + narrativa IA."""
    token = entorno_pruebas["token_admin_a"]
    slug = entorno_pruebas["slug_a"]

    # Simular respuesta estructurada del LLM
    from app.services import ia_service
    monkeypatch.setattr(
        ia_service,
        "llamar_mistral",
        lambda **kwargs: '{"tipo": "ventas", "desde": null, "hasta": null, "sucursal_id": null}',
    )

    res = client.post(
        "/api/v1/ia/reportes",
        json={"prompt": "Mostrame las ventas consolidadas por sucursal"},
        headers={"Authorization": f"Bearer {token}", "X-Tienda": slug},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["tipo"] == "ventas"
    assert "narrativa_ia" in body and body["narrativa_ia"] is not None
    assert body["tipo_grafico"] == "barras"
    assert isinstance(body["datos"], list)


def test_cp12_cuarto_tipo_reporte_rendimiento_categorias(entorno_pruebas, monkeypatch):
    """RF21: Generar el cuarto tipo de reporte (rendimiento por categoría) con IA."""
    token = entorno_pruebas["token_encargado_a"]
    slug = entorno_pruebas["slug_a"]

    from app.services import ia_service
    monkeypatch.setattr(
        ia_service,
        "llamar_mistral",
        lambda **kwargs: '{"tipo": "rendimiento_categorias", "desde": null, "hasta": null, "sucursal_id": null}',
    )

    res = client.post(
        "/api/v1/ia/reportes",
        json={"prompt": "Cuál es el rendimiento de ventas por categoría textil?"},
        headers={"Authorization": f"Bearer {token}", "X-Tienda": slug},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["tipo"] == "rendimiento_categorias"
    assert body["tipo_grafico"] == "pastel"
    assert isinstance(body["datos"], list)


def test_cp14_aislamiento_multitenant_en_reportes(entorno_pruebas):
    """CP-14 (RN02 / RN09): La consulta de reportes se restringe estrictamente
    al tenant autenticado y no expone datos de otra empresa."""
    token_b = entorno_pruebas["token_admin_b"]
    slug_b = entorno_pruebas["slug_b"]

    # Empresa B intenta consultar las ventas: solo ve sus ventas (vacías), nunca las de Empresa A
    res = client.get(
        "/api/v1/reportes/ventas",
        headers={"Authorization": f"Bearer {token_b}", "X-Tienda": slug_b},
    )
    assert res.status_code == 200
    ventas_b = res.json()
    sucursales_b_ids = [v["sucursal_id"] for v in ventas_b]
    # No puede aparecer ninguna sucursal de Empresa A
    assert entorno_pruebas["sucursal_1_id"] not in sucursales_b_ids
    assert entorno_pruebas["sucursal_2_id"] not in sucursales_b_ids


# ==============================================================================
# CU-17: EXPORTAR REPORTE (CP-13)
# ==============================================================================

def test_cp13_exportar_reporte_excel(entorno_pruebas):
    """CP-13: Exporta el reporte generado a un archivo Excel XLSX válido con encabezados corporativos."""
    token = entorno_pruebas["token_admin_a"]
    slug = entorno_pruebas["slug_a"]

    res = client.post(
        "/api/v1/reportes/exportar/excel",
        json={"tipo": "ventas", "formato": "excel", "titulo": "Reporte de Ventas por Sucursal"},
        headers={"Authorization": f"Bearer {token}", "X-Tienda": slug},
    )
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert "attachment; filename=" in res.headers["content-disposition"]
    # El archivo no debe estar vacío y debe ser un ZIP/XLSX válido (inicia con PK)
    assert len(res.content) > 1000
    assert res.content[:2] == b"PK"


def test_cp13_exportar_reporte_pdf(entorno_pruebas):
    """CP-13: Exporta el reporte generado a un archivo PDF corporativo con membrete."""
    token = entorno_pruebas["token_admin_a"]
    slug = entorno_pruebas["slug_a"]

    res = client.post(
        "/api/v1/reportes/exportar/pdf",
        json={"tipo": "rendimiento_categorias", "formato": "pdf", "titulo": "Rendimiento por Categoría"},
        headers={"Authorization": f"Bearer {token}", "X-Tienda": slug},
    )
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert "attachment; filename=" in res.headers["content-disposition"]
    # Cabecera estándar de PDF: %PDF
    assert res.content.startswith(b"%PDF")


# ==============================================================================
# CU-18: DASHBOARD DE ANALÍTICA CON MACHINE LEARNING (CP-15, CP-16)
# ==============================================================================

def test_cp15_consultar_dashboard_analitica_ml_plan_profesional(entorno_pruebas):
    """CP-15 (RF24 / CU-18): Consultar el dashboard de analítica ML con plan Profesional
    habilitado presenta predicciones de demanda, clusters y métricas formales R² y Silueta."""
    token = entorno_pruebas["token_admin_a"]
    slug = entorno_pruebas["slug_a"]

    res = client.get(
        "/api/v1/reportes/analitica-ml",
        headers={"Authorization": f"Bearer {token}", "X-Tienda": slug},
    )
    assert res.status_code == 200, res.text
    data = res.json()

    # Métricas del modelo
    metricas = data["metricas"]
    assert metricas["r2_score"] >= 0.70, f"R² esperado >= 0.70, obtenido: {metricas['r2_score']}"
    assert metricas["mae"] > 0
    assert metricas["silhouette_score"] > 0.40, f"Silueta esperada > 0.40, obtenida: {metricas['silhouette_score']}"

    # Predicciones supervisadas
    predicciones = data["predicciones_demanda"]
    assert len(predicciones) == 4
    for p in predicciones:
        assert p["ventas_proyectadas"] > 0
        assert p["limite_superior"] >= p["ventas_proyectadas"] >= p["limite_inferior"]

    # Segmentación no supervisada (clusters)
    segmentos = data["segmentacion_clientes"]
    assert len(segmentos) == 4
    total_pct = sum(s["porcentaje"] for s in segmentos)
    assert 99.0 <= total_pct <= 101.0, f"Suma de porcentajes esperada ~100%, obtenida: {total_pct}"


def test_cp16_intentar_acceder_dashboard_ia_con_plan_basico(entorno_pruebas):
    """CP-16 (RF05 / RN03 / CU-18): Intentar acceder al dashboard de analítica ML
    o reportes IA desde una empresa con Plan Básico debe ser denegado por el backend."""
    token_b = entorno_pruebas["token_admin_b"]
    slug_b = entorno_pruebas["slug_b"]

    # 1. Acceso a Analítica ML
    res_ml = client.get(
        "/api/v1/reportes/analitica-ml",
        headers={"Authorization": f"Bearer {token_b}", "X-Tienda": slug_b},
    )
    # Debe ser denegado por falta de suscripción a la función reportes_ia (402 o 403)
    assert res_ml.status_code in (402, 403), f"Se esperaba 402/403, obtenido: {res_ml.status_code}"

    # 2. Acceso a Reportes IA
    res_ia = client.post(
        "/api/v1/ia/reportes",
        json={"prompt": "Ventas del mes"},
        headers={"Authorization": f"Bearer {token_b}", "X-Tienda": slug_b},
    )
    assert res_ia.status_code in (402, 403), f"Se esperaba 402/403, obtenido: {res_ia.status_code}"
