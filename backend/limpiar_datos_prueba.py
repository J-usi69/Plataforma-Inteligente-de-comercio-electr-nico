"""Limpieza de todos los datos que quedaron acumulados en la base compartida por
correr la suite de pytest contra la base de datos real (no una de prueba aislada):
cada corrida crea usuarios, personal, proveedores, sucursales y prendas con nombres
unicos basados en timestamp (ej. "cajero_1789839682594@fashionstore.com",
"Chaqueta Denim Modelo 1789839705378") y nunca los borra.

Se identifican por el patron de 10+ digitos consecutivos (timestamp en ms) en el
nombre/correo, que ningun dato real de la plataforma usa. Antes de borrar se
verifico que ninguno de estos registros esta referenciado por ventas, reservas
ni inventario reales (todas las FK relevantes ya tenian cascade o count() = 0).

No toca las cuentas demo reales (admin/cliente/encargado/cajero/proveedor
@fashionstore.com) mas que para corregir el nombre visible de Encargado y
Cajero, que habian quedado con el apellido "De Prueba" de una carga manual
anterior a seed_users.py.
"""

from app.db.session import engine
from sqlalchemy import text

TIMESTAMP_EMAIL = "[0-9]{10,}@"
TIMESTAMP_TEXTO = "[0-9]{10,}"


def limpiar():
    with engine.connect() as conn:
        # Corregir el nombre de las cuentas demo reales que habian quedado con "De Prueba"
        conn.execute(text("UPDATE personal SET nombres = 'Carlos', apellidos = 'Mendoza' WHERE id = 1 AND apellidos = 'De Prueba'"))
        conn.execute(text("UPDATE personal SET nombres = 'Laura', apellidos = 'Paz' WHERE id = 2 AND apellidos = 'De Prueba'"))

        test_ids = list(
            conn.execute(text(f"SELECT id FROM usuario WHERE correo ~ '{TIMESTAMP_EMAIL}'")).scalars()
        )
        print(f"Usuarios de prueba detectados: {len(test_ids)}")

        if test_ids:
            b = conn.execute(text("DELETE FROM bitacora WHERE usuario_id = ANY(:ids)"), {"ids": test_ids}).rowcount
            i = conn.execute(text("DELETE FROM interaccion_ia WHERE usuario_id = ANY(:ids)"), {"ids": test_ids}).rowcount
            print(f"  bitacora eliminada: {b}, interaccion_ia eliminada: {i}")
            u = conn.execute(text("DELETE FROM usuario WHERE id = ANY(:ids)"), {"ids": test_ids}).rowcount
            print(f"  usuarios eliminados (cascada: personal, usuario_rol, push_token): {u}")

        p = conn.execute(text(f"DELETE FROM proveedor WHERE nombre_empresa ~ '{TIMESTAMP_TEXTO}'")).rowcount
        print(f"Proveedores de prueba eliminados: {p}")

        s = conn.execute(text(f"DELETE FROM sucursal WHERE nombre ~ '{TIMESTAMP_TEXTO}'")).rowcount
        print(f"Sucursales de prueba eliminadas: {s}")

        pr = conn.execute(text(f"DELETE FROM prenda WHERE nombre ~ '{TIMESTAMP_TEXTO}'")).rowcount
        print(f"Prendas de prueba eliminadas (cascada: variantes, inventario): {pr}")

        r = conn.execute(text("DELETE FROM rol WHERE nombre ~ '^Rol_[0-9]+$'")).rowcount
        print(f"Roles dinamicos de prueba eliminados: {r}")

        conn.commit()
        print("LIMPIEZA COMPLETADA.")


if __name__ == "__main__":
    limpiar()
