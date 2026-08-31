# Modelo de Datos Lógico — FashionStore

Corresponde 1:1 con [`database/schema.sql`](../database/schema.sql).

> Base: propuesta de diagrama de clases del equipo, con 4 ajustes:
> 1. Se agregó `movimiento_inventario` (faltaba, RF22 la exige).
> 2. `talla` y `color` se normalizaron como catálogos propios (antes eran varchar sueltos en `variante_prenda`).
> 3. `temporada` y `coleccion` quedaron separadas (antes fusionadas en una sola tabla).
> 4. `rol_permiso` quedó como tabla N:M correcta (antes solo tenía una relación de dependencia suelta hacia `permiso`).
>
> No existe tabla `carrito`: la propia `reserva` cumple ese rol (se arma agregando/quitando ítems antes de confirmarla), y una `venta` puede generarse con o sin `reserva` previa según el canal.

## 1. Seguridad: usuarios, personal, roles y permisos

### rol
| Columna | Tipo | Llave |
|---|---|---|
| id | SERIAL | PK |
| nombre | VARCHAR(30) | UNIQUE |
| descripcion | VARCHAR(100) | |
| estado | BOOLEAN | |
| fecha_eliminacion | TIMESTAMPTZ | (nullable) |

### permiso
| Columna | Tipo | Llave |
|---|---|---|
| id | SERIAL | PK |
| codigo | VARCHAR(50) | UNIQUE |
| descripcion | VARCHAR(100) | |
| modulo | VARCHAR(50) | |
| estado | BOOLEAN | |

### rol_permiso *(ajuste #4)*
| Columna | Tipo | Llave |
|---|---|---|
| rol_id | INTEGER | PK, FK → rol.id |
| permiso_id | INTEGER | PK, FK → permiso.id |

### usuario
| Columna | Tipo | Llave |
|---|---|---|
| id | SERIAL | PK |
| correo | VARCHAR(150) | UNIQUE |
| password_hash | VARCHAR(255) | |
| celular | VARCHAR(15) | |
| estado | BOOLEAN | |
| verificado | TIMESTAMPTZ | (nullable) |
| fecha_eliminacion | TIMESTAMPTZ | (nullable) |
| creado_en | TIMESTAMPTZ | |

### usuario_rol
| Columna | Tipo | Llave |
|---|---|---|
| usuario_id | INTEGER | PK, FK → usuario.id |
| rol_id | INTEGER | PK, FK → rol.id |

### bitacora
| Columna | Tipo | Llave |
|---|---|---|
| id | SERIAL | PK |
| usuario_id | INTEGER | FK → usuario.id |
| accion | VARCHAR(100) | |
| ip | VARCHAR(45) | |
| fecha | TIMESTAMPTZ | |

## 2. Sucursales y personal

### ciudad
| Columna | Tipo | Llave |
|---|---|---|
| id | SERIAL | PK |
| nombre | VARCHAR(100) | UNIQUE |
| estado | BOOLEAN | |
| fecha_eliminacion | TIMESTAMPTZ | (nullable) |

### sucursal
| Columna | Tipo | Llave |
|---|---|---|
| id | SERIAL | PK |
| nombre | VARCHAR(150) | |
| ciudad_id | INTEGER | FK → ciudad.id |
| direccion | VARCHAR(255) | |
| telefono | VARCHAR(15) | |
| hora_inicio | TIME | |
| hora_fin | TIME | |
| estado | BOOLEAN | |
| fecha_eliminacion | TIMESTAMPTZ | (nullable) |

### personal
| Columna | Tipo | Llave |
|---|---|---|
| id | SERIAL | PK |
| usuario_id | INTEGER | UNIQUE, FK → usuario.id |
| sucursal_id | INTEGER | FK → sucursal.id (nullable) |
| nombres | VARCHAR(60) | |
| apellidos | VARCHAR(60) | |
| cargo | VARCHAR(50) | |
| estado | BOOLEAN | |
| fecha_eliminacion | TIMESTAMPTZ | (nullable) |

## 3. Catálogo

### categoria
| Columna | Tipo | Llave |
|---|---|---|
| id | SERIAL | PK |
| nombre | VARCHAR(100) | UNIQUE |
| descripcion | VARCHAR(255) | |
| estado | BOOLEAN | |

### talla *(ajuste #2 — antes varchar suelto)*
| Columna | Tipo | Llave |
|---|---|---|
| id | SERIAL | PK |
| nombre | VARCHAR(20) | UNIQUE |

### color *(ajuste #2 — antes varchar suelto)*
| Columna | Tipo | Llave |
|---|---|---|
| id | SERIAL | PK |
| nombre | VARCHAR(50) | UNIQUE |
| hex | VARCHAR(7) | |

### temporada *(ajuste #3 — separada de coleccion)*
| Columna | Tipo | Llave |
|---|---|---|
| id | SERIAL | PK |
| nombre | VARCHAR(100) | |
| tipo | VARCHAR(50) | |
| fecha_inicio | DATE | |
| fecha_fin | DATE | |
| estado | BOOLEAN | |

### coleccion *(ajuste #3 — separada de temporada)*
| Columna | Tipo | Llave |
|---|---|---|
| id | SERIAL | PK |
| nombre | VARCHAR(150) | |
| descripcion | VARCHAR(255) | |
| temporada_id | INTEGER | FK → temporada.id |
| estado | BOOLEAN | |

### proveedor
| Columna | Tipo | Llave |
|---|---|---|
| id | SERIAL | PK |
| nombre_empresa | VARCHAR(150) | |
| contacto | VARCHAR(150) | |
| estado | BOOLEAN | |

### prenda
| Columna | Tipo | Llave |
|---|---|---|
| id | SERIAL | PK |
| nombre | VARCHAR(150) | |
| descripcion | TEXT | |
| categoria_id | INTEGER | FK → categoria.id |
| coleccion_id | INTEGER | FK → coleccion.id (nullable) |
| proveedor_id | INTEGER | FK → proveedor.id (nullable) |
| precio_base | NUMERIC(10,2) | |
| modelo_3d_url | VARCHAR(500) | (para el vestidor virtual AR) |
| estado | BOOLEAN | |

### variante_prenda
| Columna | Tipo | Llave |
|---|---|---|
| id | SERIAL | PK |
| prenda_id | INTEGER | FK → prenda.id |
| talla_id | INTEGER | FK → talla.id |
| color_id | INTEGER | FK → color.id |
| codigo_barras | VARCHAR(50) | UNIQUE |
| estado | BOOLEAN | |

> UNIQUE compuesto: `prenda_id` + `talla_id` + `color_id`

## 4. Inventario

### inventario_sucursal
| Columna | Tipo | Llave |
|---|---|---|
| id | SERIAL | PK |
| variante_id | INTEGER | FK → variante_prenda.id |
| sucursal_id | INTEGER | FK → sucursal.id |
| stock_disponible | INTEGER | |
| stock_reservado | INTEGER | |
| stock_minimo | INTEGER | |
| stock_maximo | INTEGER | |

> UNIQUE compuesto: `variante_id` + `sucursal_id`

### movimiento_inventario *(ajuste #1 — tabla nueva)*
| Columna | Tipo | Llave |
|---|---|---|
| id | SERIAL | PK |
| variante_id | INTEGER | FK → variante_prenda.id |
| sucursal_id | INTEGER | FK → sucursal.id |
| tipo_movimiento | ENUM (entrada / venta / reserva / devolucion / ajuste) | |
| cantidad | INTEGER | |
| referencia_id | INTEGER | |
| referencia_tipo | VARCHAR(50) | |
| usuario_id | INTEGER | FK → usuario.id (nullable) |
| fecha | TIMESTAMPTZ | |

## 5. Reservas

### reserva
| Columna | Tipo | Llave |
|---|---|---|
| id | SERIAL | PK |
| usuario_id | INTEGER | FK → usuario.id |
| sucursal_id | INTEGER | FK → sucursal.id |
| personal_id | INTEGER | FK → personal.id (nullable) |
| fecha_reserva | TIMESTAMPTZ | |
| horario_atencion | TIME | |
| estado | ENUM (pendiente / confirmada / atendida / cancelada / expirada) | |

### detalle_reserva
| Columna | Tipo | Llave |
|---|---|---|
| id | SERIAL | PK |
| reserva_id | INTEGER | FK → reserva.id |
| variante_id | INTEGER | FK → variante_prenda.id |
| cantidad | INTEGER | |

## 6. Ventas

### venta
| Columna | Tipo | Llave |
|---|---|---|
| id | SERIAL | PK |
| usuario_id | INTEGER | FK → usuario.id (nullable) |
| personal_id | INTEGER | FK → personal.id (nullable) |
| sucursal_id | INTEGER | FK → sucursal.id |
| reserva_id | INTEGER | FK → reserva.id (nullable) |
| tipo_origen | ENUM (web / movil / presencial) | |
| estado | ENUM (pendiente / pagada / anulada) | |
| total | NUMERIC(10,2) | |
| fecha_venta | TIMESTAMPTZ | |

### detalle_venta
| Columna | Tipo | Llave |
|---|---|---|
| id | SERIAL | PK |
| venta_id | INTEGER | FK → venta.id |
| variante_id | INTEGER | FK → variante_prenda.id |
| cantidad | INTEGER | |
| precio_unitario | NUMERIC(10,2) | |
| subtotal | NUMERIC(10,2) | |

## 7. Pagos

### pago
| Columna | Tipo | Llave |
|---|---|---|
| id | SERIAL | PK |
| venta_id | INTEGER | FK → venta.id |
| metodo_pago | VARCHAR(30) | |
| pasarela | VARCHAR(30) | |
| estado | ENUM (pendiente / aprobado / rechazado) | |
| monto | NUMERIC(10,2) | |
| transaccion_id | VARCHAR(100) | |
| fecha_pago | TIMESTAMPTZ | |

## 8. Inteligencia artificial

### interaccion_ia
| Columna | Tipo | Llave |
|---|---|---|
| id | SERIAL | PK |
| usuario_id | INTEGER | FK → usuario.id |
| tipo_consulta | VARCHAR(30) | |
| prompt_consulta | TEXT | |
| prendas_sugeridas_ids | TEXT | |
| fecha | TIMESTAMPTZ | |

---

## Pendiente a discutir con el equipo

- **Promociones**: el actor Administrador tiene "gestionar promociones" en el enunciado, pero no aparece en el diagrama del compañero ni se agregó aquí (fuera del alcance de los 4 ajustes pedidos). Si lo necesitan, se puede sumar `promocion` + `promocion_prenda` (N:M) sin tocar el resto del esquema.
