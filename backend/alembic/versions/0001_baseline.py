"""baseline - esquema inicial FashionStore (ya aplicado manualmente en Supabase)

Revision ID: 0001
Revises:
Create Date: 2026-08-30

Esta migracion documenta el esquema que ya existe en la base de datos
compartida (fue creado ejecutando database/schema.sql directamente).
No se corre su upgrade() en Supabase: se usa "alembic stamp 0001" para
marcar la base como si ya estuviera en esta revision, sin re-ejecutar
el DDL. Cualquier entorno nuevo (por ejemplo, para pruebas locales
desde cero) si puede correr "alembic upgrade head" normalmente.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UPGRADE_SQL = """
CREATE TYPE canal_venta AS ENUM ('web', 'movil', 'presencial');
CREATE TYPE estado_reserva AS ENUM ('pendiente', 'confirmada', 'atendida', 'cancelada', 'expirada');
CREATE TYPE estado_venta AS ENUM ('pendiente', 'pagada', 'anulada');
CREATE TYPE estado_pago AS ENUM ('pendiente', 'aprobado', 'rechazado');
CREATE TYPE tipo_movimiento AS ENUM ('entrada', 'venta', 'reserva', 'devolucion', 'ajuste');

CREATE TABLE rol (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(30) NOT NULL UNIQUE,
    descripcion VARCHAR(100),
    estado BOOLEAN NOT NULL DEFAULT TRUE,
    fecha_eliminacion TIMESTAMPTZ
);

CREATE TABLE permiso (
    id SERIAL PRIMARY KEY,
    codigo VARCHAR(50) NOT NULL UNIQUE,
    descripcion VARCHAR(100),
    modulo VARCHAR(50),
    estado BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE rol_permiso (
    rol_id INTEGER NOT NULL REFERENCES rol(id) ON DELETE CASCADE,
    permiso_id INTEGER NOT NULL REFERENCES permiso(id) ON DELETE CASCADE,
    PRIMARY KEY (rol_id, permiso_id)
);

CREATE TABLE usuario (
    id SERIAL PRIMARY KEY,
    correo VARCHAR(150) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    celular VARCHAR(15),
    estado BOOLEAN NOT NULL DEFAULT TRUE,
    verificado TIMESTAMPTZ,
    fecha_eliminacion TIMESTAMPTZ,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE usuario_rol (
    usuario_id INTEGER NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
    rol_id INTEGER NOT NULL REFERENCES rol(id) ON DELETE CASCADE,
    PRIMARY KEY (usuario_id, rol_id)
);

CREATE TABLE bitacora (
    id SERIAL PRIMARY KEY,
    usuario_id INTEGER NOT NULL REFERENCES usuario(id),
    accion VARCHAR(100) NOT NULL,
    ip VARCHAR(45),
    fecha TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE ciudad (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL UNIQUE,
    estado BOOLEAN NOT NULL DEFAULT TRUE,
    fecha_eliminacion TIMESTAMPTZ
);

CREATE TABLE sucursal (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(150) NOT NULL,
    ciudad_id INTEGER NOT NULL REFERENCES ciudad(id),
    direccion VARCHAR(255) NOT NULL,
    telefono VARCHAR(15),
    hora_inicio TIME,
    hora_fin TIME,
    estado BOOLEAN NOT NULL DEFAULT TRUE,
    fecha_eliminacion TIMESTAMPTZ
);

CREATE TABLE personal (
    id SERIAL PRIMARY KEY,
    usuario_id INTEGER NOT NULL UNIQUE REFERENCES usuario(id) ON DELETE CASCADE,
    sucursal_id INTEGER REFERENCES sucursal(id),
    nombres VARCHAR(60) NOT NULL,
    apellidos VARCHAR(60) NOT NULL,
    cargo VARCHAR(50) NOT NULL,
    estado BOOLEAN NOT NULL DEFAULT TRUE,
    fecha_eliminacion TIMESTAMPTZ
);

CREATE TABLE categoria (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL UNIQUE,
    descripcion VARCHAR(255),
    estado BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE talla (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(20) NOT NULL UNIQUE
);

CREATE TABLE color (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(50) NOT NULL UNIQUE,
    hex VARCHAR(7)
);

CREATE TABLE temporada (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    tipo VARCHAR(50),
    fecha_inicio DATE,
    fecha_fin DATE,
    estado BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE coleccion (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(150) NOT NULL,
    descripcion VARCHAR(255),
    temporada_id INTEGER NOT NULL REFERENCES temporada(id),
    estado BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE proveedor (
    id SERIAL PRIMARY KEY,
    nombre_empresa VARCHAR(150) NOT NULL,
    contacto VARCHAR(150),
    estado BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE prenda (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(150) NOT NULL,
    descripcion TEXT,
    categoria_id INTEGER NOT NULL REFERENCES categoria(id),
    coleccion_id INTEGER REFERENCES coleccion(id),
    proveedor_id INTEGER REFERENCES proveedor(id),
    precio_base NUMERIC(10,2) NOT NULL,
    modelo_3d_url VARCHAR(500),
    estado BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE variante_prenda (
    id SERIAL PRIMARY KEY,
    prenda_id INTEGER NOT NULL REFERENCES prenda(id) ON DELETE CASCADE,
    talla_id INTEGER NOT NULL REFERENCES talla(id),
    color_id INTEGER NOT NULL REFERENCES color(id),
    codigo_barras VARCHAR(50) NOT NULL UNIQUE,
    estado BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE (prenda_id, talla_id, color_id)
);

CREATE TABLE inventario_sucursal (
    id SERIAL PRIMARY KEY,
    variante_id INTEGER NOT NULL REFERENCES variante_prenda(id) ON DELETE CASCADE,
    sucursal_id INTEGER NOT NULL REFERENCES sucursal(id) ON DELETE CASCADE,
    stock_disponible INTEGER NOT NULL DEFAULT 0 CHECK (stock_disponible >= 0),
    stock_reservado INTEGER NOT NULL DEFAULT 0 CHECK (stock_reservado >= 0),
    stock_minimo INTEGER NOT NULL DEFAULT 0,
    stock_maximo INTEGER,
    UNIQUE (variante_id, sucursal_id)
);

CREATE TABLE movimiento_inventario (
    id SERIAL PRIMARY KEY,
    variante_id INTEGER NOT NULL REFERENCES variante_prenda(id),
    sucursal_id INTEGER NOT NULL REFERENCES sucursal(id),
    tipo_movimiento tipo_movimiento NOT NULL,
    cantidad INTEGER NOT NULL,
    referencia_id INTEGER,
    referencia_tipo VARCHAR(50),
    usuario_id INTEGER REFERENCES usuario(id),
    fecha TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE reserva (
    id SERIAL PRIMARY KEY,
    usuario_id INTEGER NOT NULL REFERENCES usuario(id),
    sucursal_id INTEGER NOT NULL REFERENCES sucursal(id),
    personal_id INTEGER REFERENCES personal(id),
    fecha_reserva TIMESTAMPTZ NOT NULL DEFAULT now(),
    horario_atencion TIME,
    estado estado_reserva NOT NULL DEFAULT 'pendiente'
);

CREATE TABLE detalle_reserva (
    id SERIAL PRIMARY KEY,
    reserva_id INTEGER NOT NULL REFERENCES reserva(id) ON DELETE CASCADE,
    variante_id INTEGER NOT NULL REFERENCES variante_prenda(id),
    cantidad INTEGER NOT NULL CHECK (cantidad > 0),
    UNIQUE (reserva_id, variante_id)
);

CREATE TABLE venta (
    id SERIAL PRIMARY KEY,
    usuario_id INTEGER REFERENCES usuario(id),
    personal_id INTEGER REFERENCES personal(id),
    sucursal_id INTEGER NOT NULL REFERENCES sucursal(id),
    reserva_id INTEGER REFERENCES reserva(id),
    tipo_origen canal_venta NOT NULL,
    estado estado_venta NOT NULL DEFAULT 'pendiente',
    total NUMERIC(10,2) NOT NULL DEFAULT 0,
    fecha_venta TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE detalle_venta (
    id SERIAL PRIMARY KEY,
    venta_id INTEGER NOT NULL REFERENCES venta(id) ON DELETE CASCADE,
    variante_id INTEGER NOT NULL REFERENCES variante_prenda(id),
    cantidad INTEGER NOT NULL CHECK (cantidad > 0),
    precio_unitario NUMERIC(10,2) NOT NULL,
    subtotal NUMERIC(10,2) NOT NULL
);

CREATE TABLE pago (
    id SERIAL PRIMARY KEY,
    venta_id INTEGER NOT NULL REFERENCES venta(id) ON DELETE CASCADE,
    metodo_pago VARCHAR(30) NOT NULL,
    pasarela VARCHAR(30),
    estado estado_pago NOT NULL DEFAULT 'pendiente',
    monto NUMERIC(10,2) NOT NULL,
    transaccion_id VARCHAR(100),
    fecha_pago TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE interaccion_ia (
    id SERIAL PRIMARY KEY,
    usuario_id INTEGER NOT NULL REFERENCES usuario(id),
    tipo_consulta VARCHAR(30),
    prompt_consulta TEXT,
    prendas_sugeridas_ids TEXT,
    fecha TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_prenda_categoria ON prenda(categoria_id);
CREATE INDEX idx_prenda_coleccion ON prenda(coleccion_id);
CREATE INDEX idx_coleccion_temporada ON coleccion(temporada_id);
CREATE INDEX idx_variante_prenda ON variante_prenda(prenda_id);
CREATE INDEX idx_inventario_variante_sucursal ON inventario_sucursal(variante_id, sucursal_id);
CREATE INDEX idx_movimiento_variante_sucursal ON movimiento_inventario(variante_id, sucursal_id);
CREATE INDEX idx_reserva_usuario ON reserva(usuario_id);
CREATE INDEX idx_detalle_reserva_reserva ON detalle_reserva(reserva_id);
CREATE INDEX idx_venta_sucursal ON venta(sucursal_id);
CREATE INDEX idx_venta_usuario ON venta(usuario_id);
CREATE INDEX idx_detalle_venta_venta ON detalle_venta(venta_id);
CREATE INDEX idx_bitacora_usuario ON bitacora(usuario_id);
CREATE INDEX idx_interaccion_ia_usuario ON interaccion_ia(usuario_id);
"""

DOWNGRADE_SQL = """
DROP TABLE IF EXISTS interaccion_ia;
DROP TABLE IF EXISTS pago;
DROP TABLE IF EXISTS detalle_venta;
DROP TABLE IF EXISTS venta;
DROP TABLE IF EXISTS detalle_reserva;
DROP TABLE IF EXISTS reserva;
DROP TABLE IF EXISTS movimiento_inventario;
DROP TABLE IF EXISTS inventario_sucursal;
DROP TABLE IF EXISTS variante_prenda;
DROP TABLE IF EXISTS prenda;
DROP TABLE IF EXISTS proveedor;
DROP TABLE IF EXISTS coleccion;
DROP TABLE IF EXISTS temporada;
DROP TABLE IF EXISTS color;
DROP TABLE IF EXISTS talla;
DROP TABLE IF EXISTS categoria;
DROP TABLE IF EXISTS personal;
DROP TABLE IF EXISTS sucursal;
DROP TABLE IF EXISTS ciudad;
DROP TABLE IF EXISTS bitacora;
DROP TABLE IF EXISTS usuario_rol;
DROP TABLE IF EXISTS usuario;
DROP TABLE IF EXISTS rol_permiso;
DROP TABLE IF EXISTS permiso;
DROP TABLE IF EXISTS rol;

DROP TYPE IF EXISTS tipo_movimiento;
DROP TYPE IF EXISTS estado_pago;
DROP TYPE IF EXISTS estado_venta;
DROP TYPE IF EXISTS estado_reserva;
DROP TYPE IF EXISTS canal_venta;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
