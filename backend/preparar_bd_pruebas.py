"""Arma desde cero una base de datos local para correr los tests (en el CI o en tu máquina),
sin tocar la base compartida de Supabase.

    docker run -d --name fs-pg-pruebas -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=fashionstore \
        -p 54329:5432 postgres:16-alpine
    DATABASE_URL=postgresql://postgres:postgres@localhost:54329/fashionstore python preparar_bd_pruebas.py
    DATABASE_URL=postgresql://postgres:postgres@localhost:54329/fashionstore pytest

Orden: la migración base (esquema), los datos semilla y después el resto de las migraciones. Si
se corrieran todas las migraciones primero, la que agrega el rol "Proveedor" le ganaría el id 1
al rol "Administrador" de los datos semilla.
"""
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

from alembic import command
from alembic.config import Config

HOSTS_PERMITIDOS = {"localhost", "127.0.0.1", "postgres"}  # "postgres": el servicio del CI
RAIZ = Path(__file__).resolve().parent


def _verificar_que_es_local() -> None:
    url = os.environ.get("DATABASE_URL", "")
    host = urlparse(url).hostname
    if host not in HOSTS_PERMITIDOS:
        sys.exit(
            f"DATABASE_URL apunta a '{host}'. Este script borra y siembra datos: solo corre contra "
            f"una base local ({', '.join(sorted(HOSTS_PERMITIDOS))}), nunca contra Supabase."
        )


def main() -> None:
    _verificar_que_es_local()
    # Recién acá: app.core.config lee DATABASE_URL al importarse
    from sqlalchemy import text

    import seed_permisos_tienda
    import seed_prendas_demo
    import seed_users
    from app.db.session import engine

    alembic = Config(str(RAIZ / "alembic.ini"))
    alembic.set_main_option("script_location", str(RAIZ / "alembic"))

    command.upgrade(alembic, "0001")
    with engine.begin() as conn:
        conn.exec_driver_sql((RAIZ.parent / "database" / "init-seeds.sql").read_text(encoding="utf-8"))
    # Los seeds en Python insertan sin tienda_id: corren mientras la columna todavía tiene DEFAULT 1
    # (todo queda en la tienda "fashionstore"); saas04 lo quita al final
    command.upgrade(alembic, "saas03")

    seed_users.seed()
    seed_permisos_tienda.seed()
    seed_prendas_demo.seed()
    # Los tests venden de verdad (descuentan stock): con 30 unidades alcanza para pocas corridas
    with engine.begin() as conn:
        conn.execute(text("UPDATE inventario_sucursal SET stock_disponible = 1000"))

    command.upgrade(alembic, "head")

    with engine.connect() as conn:
        resumen = conn.execute(text(
            "SELECT (SELECT count(*) FROM usuario), (SELECT count(*) FROM prenda), "
            "(SELECT count(*) FROM inventario_sucursal)"
        )).one()
    print(f"Base de pruebas lista: {resumen[0]} usuarios, {resumen[1]} prendas, {resumen[2]} filas de inventario")


if __name__ == "__main__":
    main()
