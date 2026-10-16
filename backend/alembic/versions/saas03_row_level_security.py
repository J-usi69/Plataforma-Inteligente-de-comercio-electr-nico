"""SaaS 3/4: Row Level Security, la segunda capa del aislamiento entre tiendas

El usuario con el que se conecta el backend (postgres en Supabase) tiene BYPASSRLS: las
políticas no lo afectarían. Por eso se crea el rol fashionstore_app, sin ese privilegio, y el
backend lo asume en cada transacción (SET LOCAL ROLE) junto con app.tienda_id (ver
app/db/tenancy.py). Las migraciones y la administración de la plataforma siguen como postgres.

Además, hasta ahora ninguna tabla tenía RLS: con la clave anónima de Supabase se podía leer la
base entera por su API REST. Con RLS activo y sin políticas para anon/authenticated, ya no.

Revision ID: saas03
Revises: saas02
Create Date: 2026-10-15
"""
from typing import Sequence, Union

from alembic import op

revision: str = "saas03"
down_revision: Union[str, None] = "saas02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ROL = "fashionstore_app"
TABLAS_DE_TIENDA = [
    "categoria", "talla", "color", "temporada", "coleccion", "proveedor", "prenda",
    "variante_prenda", "disponibilidad_proveedor", "interaccion_ia", "inventario_sucursal",
    "movimiento_inventario", "reserva", "detalle_reserva", "rol", "rol_permiso", "usuario_rol",
    "push_token", "sucursal", "personal", "venta", "detalle_venta", "pago", "usuario", "bitacora",
]
# Globales: la app las lee; las escrituras de tienda/suscripción quedan acotadas a la propia
TABLAS_GLOBALES_LECTURA = ["permiso", "plan"]


def upgrade() -> None:
    op.execute(f"""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{ROL}') THEN
                CREATE ROLE {ROL} NOLOGIN NOBYPASSRLS;
            END IF;
        END $$
    """)
    op.execute(f"GRANT {ROL} TO CURRENT_USER")  # para poder hacer SET ROLE
    op.execute(f"GRANT USAGE ON SCHEMA public TO {ROL}")
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {ROL}")
    op.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {ROL}")
    op.execute(f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {ROL}")
    op.execute(f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO {ROL}")

    op.execute("""
        CREATE OR REPLACE FUNCTION app_tienda_actual() RETURNS integer
        LANGUAGE sql STABLE AS $$ SELECT NULLIF(current_setting('app.tienda_id', true), '')::integer $$
    """)

    for tabla in TABLAS_DE_TIENDA:
        op.execute(f"ALTER TABLE {tabla} ENABLE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY tienda_aislada ON {tabla} TO {ROL}
            USING (tienda_id = app_tienda_actual()) WITH CHECK (tienda_id = app_tienda_actual())
        """)

    for tabla in TABLAS_GLOBALES_LECTURA:
        op.execute(f"ALTER TABLE {tabla} ENABLE ROW LEVEL SECURITY")
        op.execute(f"CREATE POLICY app_lee ON {tabla} FOR SELECT TO {ROL} USING (true)")

    # Ciudades: catálogo geográfico compartido; cualquier tienda puede leer y agregar
    op.execute("ALTER TABLE ciudad ENABLE ROW LEVEL SECURITY")
    op.execute(f"CREATE POLICY app_usa ON ciudad TO {ROL} USING (true) WITH CHECK (true)")

    # Tienda y suscripción: todos ven las tiendas (para resolver el slug), cada una edita la suya
    op.execute("ALTER TABLE tienda ENABLE ROW LEVEL SECURITY")
    op.execute(f"CREATE POLICY app_lee ON tienda FOR SELECT TO {ROL} USING (true)")
    op.execute(f"""
        CREATE POLICY tienda_edita_la_suya ON tienda FOR UPDATE TO {ROL}
        USING (id = app_tienda_actual()) WITH CHECK (id = app_tienda_actual())
    """)
    op.execute("ALTER TABLE suscripcion ENABLE ROW LEVEL SECURITY")
    op.execute(f"CREATE POLICY tienda_aislada ON suscripcion TO {ROL} USING (tienda_id = app_tienda_actual()) WITH CHECK (tienda_id = app_tienda_actual())")

    # Versión de migraciones: solo para postgres (sin políticas, nadie más la ve)
    op.execute("ALTER TABLE alembic_version ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.execute("ALTER TABLE alembic_version DISABLE ROW LEVEL SECURITY")
    for tabla, politicas in [("suscripcion", ["tienda_aislada"]), ("tienda", ["app_lee", "tienda_edita_la_suya"]), ("ciudad", ["app_usa"])]:
        for politica in politicas:
            op.execute(f"DROP POLICY IF EXISTS {politica} ON {tabla}")
        op.execute(f"ALTER TABLE {tabla} DISABLE ROW LEVEL SECURITY")
    for tabla in TABLAS_GLOBALES_LECTURA:
        op.execute(f"DROP POLICY IF EXISTS app_lee ON {tabla}")
        op.execute(f"ALTER TABLE {tabla} DISABLE ROW LEVEL SECURITY")
    for tabla in TABLAS_DE_TIENDA:
        op.execute(f"DROP POLICY IF EXISTS tienda_aislada ON {tabla}")
        op.execute(f"ALTER TABLE {tabla} DISABLE ROW LEVEL SECURITY")
    op.execute("DROP FUNCTION IF EXISTS app_tienda_actual()")
    # El rol queda (puede tener privilegios por defecto asignados); no molesta sin políticas
