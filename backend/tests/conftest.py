"""Los tests corren contra una base Postgres (la desechable del CI o una local, ver
preparar_bd_pruebas.py), y varios crean usuarios/personal/proveedores/sucursales/prendas/tiendas
con nombres unicos por timestamp para no chocar entre corridas. Estos fixtures los limpian al
terminar, usando el mismo criterio (10+ digitos consecutivos = timestamp en ms, patron que
ningun dato real de la plataforma usa) que backend/limpiar_datos_prueba.py.
"""

import pytest
from sqlalchemy import text

from app.api.v1.endpoints import auth, plataforma
from app.db.session import engine
from app.db.tenancy import olvidar_tienda

# Hijas antes que madres, para poder borrar una tienda de prueba con todo lo suyo
TABLAS_DE_TIENDA = [
    "detalle_cambio", "cambio_prenda", "operacion_sync", "rol_permiso", "usuario_rol", "bitacora", "push_token", "interaccion_ia", "pago", "detalle_venta",
    "venta", "detalle_reserva", "reserva", "movimiento_inventario", "inventario_sucursal",
    "disponibilidad_proveedor", "variante_prenda", "prenda", "coleccion", "temporada", "personal",
    "proveedor", "sucursal", "categoria", "talla", "color", "movimiento_suscripcion", "usuario", "rol",
    "suscripcion",
]


def _borrar_tienda(conn, tienda_id: int) -> None:
    for tabla in TABLAS_DE_TIENDA:
        conn.execute(text(f"DELETE FROM {tabla} WHERE tienda_id = :t"), {"t": tienda_id})
    slug = conn.execute(text("DELETE FROM tienda WHERE id = :t RETURNING slug"), {"t": tienda_id}).scalar()
    if slug:
        olvidar_tienda(slug)


@pytest.fixture(scope="session")
def borrar_tienda():
    """Borra una tienda de prueba con todo lo suyo (los tests de SaaS la llaman al terminar)."""
    def borrar(tienda_id: int) -> None:
        with engine.begin() as conn:
            _borrar_tienda(conn, tienda_id)

    return borrar


@pytest.fixture(autouse=True)
def reiniciar_limite_de_intentos():
    # Todos los tests inician sesión desde la misma "IP" del TestClient: sin esto, los fallos
    # adrede de un test bloquearían el inicio de sesión de los siguientes
    auth.intentos_por_cuenta.reiniciar()
    auth.intentos_por_ip.reiniciar()
    plataforma.altas_por_ip.reiniciar()
    plataforma.intentos_superadmin.reiniciar()


@pytest.fixture(scope="session", autouse=True)
def limpiar_datos_de_prueba():
    yield
    with engine.connect() as conn:
        # Tiendas que algún test haya dejado (por ejemplo, si falló antes de limpiar)
        for tienda_id in conn.execute(text("SELECT id FROM tienda WHERE slug ~ '[0-9]{10,}'")).scalars().all():
            _borrar_tienda(conn, tienda_id)
        test_ids = list(
            conn.execute(text("SELECT id FROM usuario WHERE correo ~ '[0-9]{10,}@'")).scalars()
        )
        if test_ids:
            conn.execute(text("DELETE FROM bitacora WHERE usuario_id = ANY(:ids)"), {"ids": test_ids})
            conn.execute(text("DELETE FROM interaccion_ia WHERE usuario_id = ANY(:ids)"), {"ids": test_ids})
            conn.execute(text("DELETE FROM usuario WHERE id = ANY(:ids)"), {"ids": test_ids})
        conn.execute(text("DELETE FROM proveedor WHERE nombre_empresa ~ '[0-9]{10,}'"))
        conn.execute(text("DELETE FROM sucursal WHERE nombre ~ '[0-9]{10,}'"))
        conn.execute(text("DELETE FROM prenda WHERE nombre ~ '[0-9]{10,}'"))
        conn.execute(text("DELETE FROM rol WHERE nombre ~ '^Rol_[0-9]+$'"))
        conn.commit()
