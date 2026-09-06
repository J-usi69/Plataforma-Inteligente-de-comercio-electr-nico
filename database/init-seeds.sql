-- ============================================================
-- FashionStore - Datos Semilla Iniciales
-- ============================================================

-- 1. Roles iniciales
INSERT INTO rol (id, nombre, descripcion, estado) VALUES
(1, 'Administrador', 'Acceso total y configuración del sistema', true),
(2, 'Cliente', 'Usuario final para navegación, reservas y compras', true),
(3, 'Encargado', 'Encargado de atención en sucursal e inventario', true),
(4, 'Cajero', 'Registro de ventas y cobros en punto de venta', true)
ON CONFLICT (id) DO NOTHING;

SELECT setval('rol_id_seq', (SELECT MAX(id) FROM rol));

-- 2. Permisos del sistema
INSERT INTO permiso (id, codigo, descripcion, modulo, estado) VALUES
-- Módulo Seguridad
(1, 'seguridad:roles:ver', 'Ver roles del sistema', 'seguridad', true),
(2, 'seguridad:roles:crear', 'Crear nuevos roles', 'seguridad', true),
(3, 'seguridad:roles:editar', 'Editar roles existentes', 'seguridad', true),
(4, 'seguridad:roles:eliminar', 'Eliminar o desactivar roles', 'seguridad', true),
(5, 'seguridad:permisos:ver', 'Listar permisos disponibles', 'seguridad', true),
(6, 'seguridad:permisos:asignar', 'Asignar permisos a roles', 'seguridad', true),
(7, 'seguridad:bitacora:ver', 'Consultar bitácora de eventos', 'seguridad', true),
-- Módulo Personal
(8, 'personal:ver', 'Ver lista de empleados', 'personal', true),
(9, 'personal:crear', 'Registrar nuevo empleado', 'personal', true),
(10, 'personal:editar', 'Modificar datos de empleado', 'personal', true),
(11, 'personal:eliminar', 'Desactivar empleado', 'personal', true),
-- Módulo Sucursales
(12, 'sucursales:ver', 'Consultar sucursales y ciudades', 'sucursales', true),
(13, 'sucursales:crear', 'Crear nueva sucursal', 'sucursales', true),
(14, 'sucursales:editar', 'Editar sucursal', 'sucursales', true),
(15, 'sucursales:eliminar', 'Desactivar sucursal', 'sucursales', true),
-- Módulo Proveedores
(16, 'proveedores:ver', 'Consultar proveedores', 'proveedores', true),
(17, 'proveedores:crear', 'Registrar nuevo proveedor', 'proveedores', true),
(18, 'proveedores:editar', 'Editar datos de proveedor', 'proveedores', true),
(19, 'proveedores:eliminar', 'Desactivar proveedor', 'proveedores', true),
-- Módulo Catálogo
(20, 'catalogo:ver', 'Ver catálogo y prendas', 'catalogo', true),
(21, 'catalogo:crear', 'Registrar prendas y variantes', 'catalogo', true),
(22, 'catalogo:editar', 'Editar prendas y variantes', 'catalogo', true),
(23, 'catalogo:eliminar', 'Desactivar prendas del catálogo', 'catalogo', true)
ON CONFLICT (id) DO NOTHING;

SELECT setval('permiso_id_seq', (SELECT MAX(id) FROM permiso));

-- 3. Asignar todos los permisos al rol Administrador (rol_id = 1)
INSERT INTO rol_permiso (rol_id, permiso_id)
SELECT 1, id FROM permiso
ON CONFLICT (rol_id, permiso_id) DO NOTHING;

-- 4. Usuario Administrador por defecto (admin@fashionstore.com / Admin123*)
INSERT INTO usuario (id, correo, password_hash, celular, estado, verificado, creado_en) VALUES
(1, 'admin@fashionstore.com', '$2b$12$2ngu5eef65b3Ul0NG2AQbuGJDvTOHxD9HZkBbxVJrSQ4A1PBWi4qW', '70012345', true, now(), now())
ON CONFLICT (correo) DO NOTHING;

SELECT setval('usuario_id_seq', (SELECT MAX(id) FROM usuario));

-- Asignar rol Administrador al usuario 1
INSERT INTO usuario_rol (usuario_id, rol_id) VALUES
(1, 1)
ON CONFLICT (usuario_id, rol_id) DO NOTHING;

-- 5. Ciudades iniciales
INSERT INTO ciudad (id, nombre, estado) VALUES
(1, 'Santa Cruz de la Sierra', true),
(2, 'La Paz', true),
(3, 'Cochabamba', true)
ON CONFLICT (id) DO NOTHING;

SELECT setval('ciudad_id_seq', (SELECT MAX(id) FROM ciudad));

-- 6. Sucursal inicial
INSERT INTO sucursal (id, nombre, ciudad_id, direccion, telefono, hora_inicio, hora_fin, estado) VALUES
(1, 'Sucursal Central Equipetrol', 1, 'Av. San Martín #450, Barrio Equipetrol', '33456789', '09:00:00', '21:00:00', true),
(2, 'Sucursal Ventura Mall', 1, '4to Anillo esq. Av. San Martín, Local 105', '33987654', '10:00:00', '22:00:00', true),
(3, 'Sucursal Calacoto', 2, 'Av. Ballivián #1250, Calacoto', '22789012', '09:30:00', '20:30:00', true)
ON CONFLICT (id) DO NOTHING;

SELECT setval('sucursal_id_seq', (SELECT MAX(id) FROM sucursal));

-- 7. Categorías
INSERT INTO categoria (id, nombre, descripcion, estado) VALUES
(1, 'Poleras y Camisetas', 'Poleras básicas, estampadas y tipo polo', true),
(2, 'Pantalones y Jeans', 'Pantalones casuales, formales y jeans denim', true),
(3, 'Vestidos y Faldas', 'Vestidos de fiesta, casuales y faldas', true),
(4, 'Chaquetas y Abrigos', 'Chaquetas de cuero, abrigos de invierno y blazers', true),
(5, 'Calzados y Zapatillas', 'Calzado urbano, deportivo y formal', true)
ON CONFLICT (id) DO NOTHING;

SELECT setval('categoria_id_seq', (SELECT MAX(id) FROM categoria));

-- 8. Tallas
INSERT INTO talla (id, nombre) VALUES
(1, 'XS'), (2, 'S'), (3, 'M'), (4, 'L'), (5, 'XL')
ON CONFLICT (id) DO NOTHING;

SELECT setval('talla_id_seq', (SELECT MAX(id) FROM talla));

-- 9. Colores
INSERT INTO color (id, nombre, hex) VALUES
(1, 'Negro', '#000000'),
(2, 'Blanco', '#FFFFFF'),
(3, 'Azul Marino', '#001F3F'),
(4, 'Rojo Borgoña', '#800020'),
(5, 'Verde Oliva', '#556B2F')
ON CONFLICT (id) DO NOTHING;

SELECT setval('color_id_seq', (SELECT MAX(id) FROM color));

-- 10. Temporadas y Colecciones
INSERT INTO temporada (id, nombre, tipo, fecha_inicio, fecha_fin, estado) VALUES
(1, 'Primavera - Verano 2026', 'Verano', '2026-09-01', '2027-02-28', true),
(2, 'Otoño - Invierno 2026', 'Invierno', '2026-03-01', '2026-08-31', true)
ON CONFLICT (id) DO NOTHING;

SELECT setval('temporada_id_seq', (SELECT MAX(id) FROM temporada));

INSERT INTO coleccion (id, nombre, descripcion, temporada_id, estado) VALUES
(1, 'Colección Urbana Santa Cruz', 'Prendas frescas y modernas para el clima tropical', 1, true),
(2, 'Línea Ejecutiva Vanguardia', 'Prendas formales para oficina y eventos de gala', 1, true)
ON CONFLICT (id) DO NOTHING;

SELECT setval('coleccion_id_seq', (SELECT MAX(id) FROM coleccion));

-- 11. Proveedores
INSERT INTO proveedor (id, nombre_empresa, contacto, estado) VALUES
(1, 'Textil Santa Cruz S.R.L.', 'ventas@textilscz.com - Cel: 71098765', true),
(2, 'Confecciones del Valle', 'contacto@confeccionesvalle.com - Cel: 72034567', true)
ON CONFLICT (id) DO NOTHING;

SELECT setval('proveedor_id_seq', (SELECT MAX(id) FROM proveedor));

