"""CU-04: completar la matriz de permisos de Encargado, Cajero y Cliente segun
la logica de negocio real de una tienda de ropa (y de retail en general):

- Cliente: solo necesita visibilidad del catalogo (sus acciones de compra/reserva
  son sobre sus propios datos, no requieren "permiso" sobre el sistema).
- Encargado de sucursal: gestiona el inventario de SU sucursal (CU-26) y las
  reservas que le llegan (CU-15/17-20), y necesita ver el catalogo, su sucursal
  y los proveedores para reponer stock. No administra personal, otras
  sucursales, ni el catalogo maestro (eso es exclusivo del Administrador).
- Cajero: registra ventas y cobros en caja (CU-17-24) y necesita ver las
  reservas para completarlas en una venta, ademas de consultar el catalogo.
- Proveedor: registra sus propios productos (CU-33) e informa su disponibilidad
  y fecha estimada de reposicion (CU-34); solo sobre lo suyo, no administra el
  catalogo maestro ni ve datos de otros proveedores.

De paso, desactiva los roles dinamicos que quedaron de pruebas automatizadas
anteriores (aparecen como "Rol dinamico de prueba" y solo ensucian el listado).
"""

from app.db.session import engine
from sqlalchemy import text

# (codigo, modulo, descripcion)
NUEVOS_PERMISOS = [
    ("inventario:ver", "inventario", "Consultar stock e inventario de la sucursal"),
    ("inventario:registrar", "inventario", "Registrar movimientos de inventario (ingreso, devolucion, merma, ajuste)"),
    ("reservas:ver", "reservas", "Consultar reservas de clientes"),
    ("reservas:gestionar", "reservas", "Atender, marcar y cancelar reservas de clientes"),
    ("ventas:ver", "ventas", "Consultar ventas y comprobantes"),
    ("ventas:crear", "ventas", "Registrar ventas y cobros en caja"),
    ("productos:ver", "productos", "Consultar los productos propios registrados"),
    ("productos:crear", "productos", "Registrar nuevos productos propios"),
    ("disponibilidad:ver", "disponibilidad", "Consultar el historial de disponibilidad informada"),
    ("disponibilidad:informar", "disponibilidad", "Informar disponibilidad y fecha estimada de reposición"),
]

# nombre del rol -> lista de codigos de permiso que le corresponden
PERMISOS_POR_ROL = {
    "Cliente": ["catalogo:ver"],
    "Encargado": [
        "catalogo:ver",
        "sucursales:ver",
        "proveedores:ver",
        "inventario:ver",
        "inventario:registrar",
        "reservas:ver",
        "reservas:gestionar",
    ],
    "Cajero": [
        "catalogo:ver",
        "ventas:ver",
        "ventas:crear",
        "reservas:ver",
    ],
    "Proveedor": [
        "catalogo:ver",
        "productos:ver",
        "productos:crear",
        "disponibilidad:ver",
        "disponibilidad:informar",
    ],
}


def seed():
    with engine.connect() as conn:
        for codigo, modulo, descripcion in NUEVOS_PERMISOS:
            existe = conn.execute(text("SELECT id FROM permiso WHERE codigo = :c"), {"c": codigo}).scalar()
            if existe:
                print(f"  permiso ya existe: {codigo}")
                continue
            conn.execute(
                text("INSERT INTO permiso (codigo, descripcion, modulo, estado) VALUES (:c, :d, :m, true)"),
                {"c": codigo, "d": descripcion, "m": modulo},
            )
            print(f"  permiso creado: {codigo}")

        for rol_nombre, codigos in PERMISOS_POR_ROL.items():
            rol_id = conn.execute(text("SELECT id FROM rol WHERE nombre = :n"), {"n": rol_nombre}).scalar()
            if not rol_id:
                print(f"  ADVERTENCIA: no se encontro el rol '{rol_nombre}'")
                continue
            for codigo in codigos:
                permiso_id = conn.execute(text("SELECT id FROM permiso WHERE codigo = :c"), {"c": codigo}).scalar()
                if not permiso_id:
                    print(f"  ADVERTENCIA: no se encontro el permiso '{codigo}'")
                    continue
                conn.execute(
                    text("""
                        INSERT INTO rol_permiso (rol_id, permiso_id)
                        VALUES (:r, :p)
                        ON CONFLICT DO NOTHING
                    """),
                    {"r": rol_id, "p": permiso_id},
                )
            print(f"  permisos asignados a {rol_nombre}: {', '.join(codigos)}")

        # Limpieza: desactivar roles dinamicos de prueba que quedaron de corridas anteriores
        desactivados = conn.execute(
            text("""
                UPDATE rol SET estado = false
                WHERE nombre ~ '^Rol_[0-9]+$' AND estado = true
                RETURNING nombre
            """)
        ).fetchall()
        for (nombre,) in desactivados:
            print(f"  rol de prueba desactivado: {nombre}")

        conn.commit()
        print("SEED COMPLETADO: permisos de tienda asignados y roles de prueba limpiados.")


if __name__ == "__main__":
    seed()
