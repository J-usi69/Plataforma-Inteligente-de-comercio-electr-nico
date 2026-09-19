"""Los tests corren contra la base de datos real compartida (no una aislada), y varios
crean usuarios/personal/proveedores/sucursales/prendas con nombres unicos por timestamp
para no chocar entre corridas. Este fixture los limpia automaticamente al terminar toda
la suite, usando el mismo criterio (10+ digitos consecutivos = timestamp en ms, patron
que ningun dato real de la plataforma usa) que backend/limpiar_datos_prueba.py.
"""

import pytest
from sqlalchemy import text

from app.db.session import engine


@pytest.fixture(scope="session", autouse=True)
def limpiar_datos_de_prueba():
    yield
    with engine.connect() as conn:
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
