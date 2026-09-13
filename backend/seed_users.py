from app.db.session import engine
from sqlalchemy import text
from app.core.security import get_password_hash

def seed():
    with engine.connect() as conn:
        # 1. Cliente
        h_cliente = get_password_hash("Cliente123*")
        conn.execute(text("""
            INSERT INTO usuario (correo, password_hash, celular, estado, verificado, creado_en)
            VALUES ('cliente@fashionstore.com', :h, '71234567', true, now(), now())
            ON CONFLICT (correo) DO UPDATE SET password_hash = :h;
        """), {"h": h_cliente})
        u_c = conn.execute(text("SELECT id FROM usuario WHERE correo = 'cliente@fashionstore.com'")).scalar()
        conn.execute(text("INSERT INTO usuario_rol (usuario_id, rol_id) VALUES (:u, 2) ON CONFLICT DO NOTHING"), {"u": u_c})

        # 2. Encargado
        h_enc = get_password_hash("Encargado123*")
        conn.execute(text("""
            INSERT INTO usuario (correo, password_hash, celular, estado, verificado, creado_en)
            VALUES ('encargado@fashionstore.com', :h, '72345678', true, now(), now())
            ON CONFLICT (correo) DO UPDATE SET password_hash = :h;
        """), {"h": h_enc})
        u_e = conn.execute(text("SELECT id FROM usuario WHERE correo = 'encargado@fashionstore.com'")).scalar()
        conn.execute(text("INSERT INTO usuario_rol (usuario_id, rol_id) VALUES (:u, 3) ON CONFLICT DO NOTHING"), {"u": u_e})
        conn.execute(text("""
            INSERT INTO personal (usuario_id, sucursal_id, nombres, apellidos, cargo, estado)
            VALUES (:u, 1, 'Carlos', 'Mendoza', 'Encargado de Sucursal', true)
            ON CONFLICT (usuario_id) DO UPDATE SET sucursal_id = 1, cargo = 'Encargado de Sucursal';
        """), {"u": u_e})

        # 3. Cajero
        h_caj = get_password_hash("Cajero123*")
        conn.execute(text("""
            INSERT INTO usuario (correo, password_hash, celular, estado, verificado, creado_en)
            VALUES ('cajero@fashionstore.com', :h, '73456789', true, now(), now())
            ON CONFLICT (correo) DO UPDATE SET password_hash = :h;
        """), {"h": h_caj})
        u_k = conn.execute(text("SELECT id FROM usuario WHERE correo = 'cajero@fashionstore.com'")).scalar()
        conn.execute(text("INSERT INTO usuario_rol (usuario_id, rol_id) VALUES (:u, 4) ON CONFLICT DO NOTHING"), {"u": u_k})
        conn.execute(text("""
            INSERT INTO personal (usuario_id, sucursal_id, nombres, apellidos, cargo, estado)
            VALUES (:u, 1, 'Laura', 'Paz', 'Cajero de Sucursal', true)
            ON CONFLICT (usuario_id) DO UPDATE SET sucursal_id = 1, cargo = 'Cajero de Sucursal';
        """), {"u": u_k})

        # Asegurar stock en inventario para variantes de prueba
        conn.execute(text("""
            INSERT INTO inventario_sucursal (variante_id, sucursal_id, stock_disponible, stock_reservado, stock_minimo)
            SELECT v.id, 1, 50, 0, 5
            FROM variante_prenda v
            ON CONFLICT (variante_id, sucursal_id) DO UPDATE
            SET stock_disponible = GREATEST(inventario_sucursal.stock_disponible, 20);
        """))

        conn.commit()
        print("SEED COMPLETADO: Usuarios y stock listos para pruebas.")

if __name__ == "__main__":
    seed()
