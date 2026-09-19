"""Corrige el stock reservado "fantasma": el endpoint de /reservas/{id}/atender
marcaba la reserva como atendida pero nunca liberaba stock_reservado (bug
corregido en reservas.py), asi que las unidades de reservas ya atendidas
quedaron atascadas en stock_reservado para siempre, drenando stock_disponible
en visitas repetidas de los tests contra la base compartida.

Este script recalcula, por variante/sucursal, cuanto stock_reservado deberia
haber realmente (solo el de reservas en estado pendiente/confirmada) y libera
el resto.
"""

from app.db.session import engine
from sqlalchemy import text


def reconciliar():
    with engine.connect() as conn:
        filas = conn.execute(text("""
            SELECT inv.variante_id, inv.sucursal_id, inv.stock_reservado,
                   COALESCE(activo.total, 0) AS reservado_real
            FROM inventario_sucursal inv
            LEFT JOIN (
                SELECT dr.variante_id, r.sucursal_id, SUM(dr.cantidad) AS total
                FROM reserva r
                JOIN detalle_reserva dr ON dr.reserva_id = r.id
                WHERE r.estado IN ('pendiente', 'confirmada')
                GROUP BY dr.variante_id, r.sucursal_id
            ) activo ON activo.variante_id = inv.variante_id AND activo.sucursal_id = inv.sucursal_id
            WHERE inv.stock_reservado <> COALESCE(activo.total, 0)
        """)).fetchall()

        if not filas:
            print("Nada que reconciliar: stock_reservado ya coincide con las reservas activas.")
            return

        for variante_id, sucursal_id, reservado_actual, reservado_real in filas:
            liberar = reservado_actual - reservado_real
            conn.execute(
                text("""
                    UPDATE inventario_sucursal
                    SET stock_disponible = stock_disponible + :liberar,
                        stock_reservado = :real
                    WHERE variante_id = :v AND sucursal_id = :s
                """),
                {"liberar": liberar, "real": reservado_real, "v": variante_id, "s": sucursal_id},
            )
            print(f"  variante={variante_id} sucursal={sucursal_id}: "
                  f"reservado {reservado_actual} -> {reservado_real}, disponible +{liberar}")

        conn.commit()
        print(f"RECONCILIACION COMPLETADA: {len(filas)} fila(s) corregidas.")


if __name__ == "__main__":
    reconciliar()
