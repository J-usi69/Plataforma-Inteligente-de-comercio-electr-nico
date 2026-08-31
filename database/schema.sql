-- ============================================================
-- FashionStore - Esquema de base de datos (PostgreSQL 16)
-- Basado en la propuesta de diagrama de clases del equipo, con
-- 4 ajustes acordados:
--   1. Se agrega movimiento_inventario (faltaba, RF22 la exige).
--   2. Talla y color se normalizan en catálogos propios (RF05).
--   3. Temporada y coleccion quedan separadas (no fusionadas).
--   4. rol_permiso queda como tabla N:M correcta (rol_id + permiso_id).
--
-- No existe tabla "carrito": la propia reserva cumple ese rol
-- (se arma agregando/quitando ítems antes de confirmarla), y una
-- venta puede generarse con o sin reserva previa según el canal.
-- ============================================================

-- Tipos enumerados
CREATE TYPE canal_venta AS ENUM ('web', 'movil', 'presencial');
CREATE TYPE estado_reserva AS ENUM ('pendiente', 'confirmada', 'atendida', 'cancelada', 'expirada');
CREATE TYPE estado_venta AS ENUM ('pendiente', 'pagada', 'anulada');
CREATE TYPE estado_pago AS ENUM ('pendiente', 'aprobado', 'rechazado');
CREATE TYPE tipo_movimiento AS ENUM ('entrada', 'venta', 'reserva', 'devolucion', 'ajuste');

-- ============================================================
-- 1. Seguridad: usuarios, personal, roles y permisos
-- ============================================================
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

-- Ajuste #4: tabla N:M correcta entre rol y permiso
CREATE TABLE rol_permiso (
    rol_id INTEGER NOT NULL REFERENCES rol(id) ON DELETE CASCADE,
    permiso_id INTEGER NOT NULL REFERENCES permiso(id) ON DELETE CASCADE,
    PRIMARY KEY (rol_id, permiso_id)
);

-- Cuenta base (login) tanto para clientes como para personal
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

-- Auditoría general de acciones en el sistema
CREATE TABLE bitacora (
    id SERIAL PRIMARY KEY,
    usuario_id INTEGER NOT NULL REFERENCES usuario(id),
    accion VARCHAR(100) NOT NULL,
    ip VARCHAR(45),
    fecha TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- 2. Sucursales y personal
-- ============================================================
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

-- Empleados (cajero, encargado de sucursal, admin, etc.): extiende usuario
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

-- ============================================================
-- 3. Catálogo
-- ============================================================
CREATE TABLE categoria (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL UNIQUE,
    descripcion VARCHAR(255),
    estado BOOLEAN NOT NULL DEFAULT TRUE
);

-- Ajuste #2: talla y color como catálogos propios (antes eran varchar sueltos)
CREATE TABLE talla (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(20) NOT NULL UNIQUE
);

CREATE TABLE color (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(50) NOT NULL UNIQUE,
    hex VARCHAR(7)
);

-- Ajuste #3: temporada y coleccion separadas (antes era una sola tabla)
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

-- ============================================================
-- 4. Inventario
-- ============================================================
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

-- Ajuste #1: tabla que faltaba para cumplir RF22 (registrar movimientos)
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

-- ============================================================
-- 5. Reservas (la reserva funciona también como "carrito" del cliente)
-- ============================================================
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

-- ============================================================
-- 6. Ventas
-- ============================================================
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

-- ============================================================
-- 7. Pagos
-- ============================================================
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

-- ============================================================
-- 8. Inteligencia artificial
-- ============================================================
CREATE TABLE interaccion_ia (
    id SERIAL PRIMARY KEY,
    usuario_id INTEGER NOT NULL REFERENCES usuario(id),
    tipo_consulta VARCHAR(30),
    prompt_consulta TEXT,
    prendas_sugeridas_ids TEXT,
    fecha TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- Índices recomendados
-- ============================================================
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
