"""Carga prendas adicionales con imagen de referencia real, para ampliar el catalogo
y tener mas variedad para probar el Vestidor Virtual (CU-14)."""

from app.db.session import engine
from sqlalchemy import text

# (nombre, categoria_id, coleccion_id, precio_base, imagen_url)
# Categorias: 1 Poleras y Camisetas, 2 Pantalones y Jeans, 3 Vestidos y Faldas,
#             4 Chaquetas y Abrigos, 5 Calzados y Zapatillas
# Colecciones: 1 Coleccion Urbana Santa Cruz (casual), 2 Linea Ejecutiva Vanguardia (elegante)
PRENDAS = [
    ("Camisa de Mezclilla a Lunares", 1, 1, 179.90,
     "https://images.unsplash.com/photo-1596755094514-f87e34085b2c?w=800&q=80"),
    ("Polera Estampada Calavera Negra", 1, 1, 99.90,
     "https://images.unsplash.com/photo-1503341504253-dff4815485f1?w=800&q=80"),
    ("Blusa Blanca Elegante", 1, 2, 149.90,
     "https://images.unsplash.com/photo-1608234807905-4466023792f5?w=800&q=80"),
    ("Jean Skinny Celeste", 2, 1, 229.90,
     "https://images.unsplash.com/photo-1475178626620-a4d074967452?w=800&q=80"),
    ("Pantalon Palazzo Rayado", 2, 2, 199.90,
     "https://images.unsplash.com/photo-1509631179647-0177331693ae?w=800&q=80"),
    ("Jogger Satinado Rosa", 2, 1, 179.90,
     "https://images.unsplash.com/photo-1594633312681-425c7b97ccd1?w=800&q=80"),
    ("Vestido de Gala Rojo", 3, 2, 399.90,
     "https://images.unsplash.com/photo-1550928431-ee0ec6db30d3?w=800&q=80"),
    ("Vestido Floral Playero", 3, 1, 289.90,
     "https://images.unsplash.com/photo-1496747611176-843222e1e57c?w=800&q=80"),
    ("Vestido Blanco Off-Shoulder", 3, 2, 259.90,
     "https://images.unsplash.com/photo-1515372039744-b8f02a3ae446?w=800&q=80"),
    ("Chaqueta Bomber Camel", 4, 1, 329.90,
     "https://images.unsplash.com/photo-1591047139829-d91aecb6caea?w=800&q=80"),
    ("Chaqueta Parka Verde Olivo", 4, 1, 379.90,
     "https://images.unsplash.com/photo-1548883354-94bcfe321cbb?w=800&q=80"),
    ("Chaqueta Shearling Camel", 4, 2, 429.90,
     "https://images.unsplash.com/photo-1608063615781-e2ef8c73d114?w=800&q=80"),
    ("Chaqueta de Cuero Motociclista Negra", 4, 1, 489.90,
     "https://images.unsplash.com/photo-1520975954732-35dd22299614?w=800&q=80"),
    ("Zapatillas Running Rojas", 5, 1, 299.90,
     "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=800&q=80"),
    ("Zapatillas Chunky Multicolor", 5, 1, 349.90,
     "https://images.unsplash.com/photo-1595341888016-a392ef81b7de?w=800&q=80"),
    ("Tacones Florales Azules", 5, 2, 319.90,
     "https://images.unsplash.com/photo-1543163521-1bf539c55dd2?w=800&q=80"),
    ("Zapatillas Blancas y Naranja", 5, 1, 289.90,
     "https://images.unsplash.com/photo-1600185365483-26d7a4cc7519?w=800&q=80"),
]

# (talla_id, color_id) por variante: mismo patron ya usado por las prendas 4-8 (S/Negro, M/Blanco, L/Azul Marino)
VARIANTES = [(2, 1), (3, 2), (4, 3)]

SUCURSALES_STOCK = [1, 2, 3]


def seed():
    with engine.connect() as conn:
        creadas = 0
        for nombre, categoria_id, coleccion_id, precio, imagen_url in PRENDAS:
            existe = conn.execute(
                text("SELECT id FROM prenda WHERE nombre = :n"), {"n": nombre}
            ).scalar()
            if existe:
                print(f"  ya existe: {nombre} (id={existe})")
                continue

            prenda_id = conn.execute(
                text("""
                    INSERT INTO prenda (nombre, descripcion, categoria_id, coleccion_id, proveedor_id, precio_base, imagen_url, estado)
                    VALUES (:nombre, :desc, :cat, :col, NULL, :precio, :img, true)
                    RETURNING id
                """),
                {
                    "nombre": nombre,
                    "desc": f"{nombre}, disponible en varias tallas y colores.",
                    "cat": categoria_id,
                    "col": coleccion_id,
                    "precio": precio,
                    "img": imagen_url,
                },
            ).scalar()

            for talla_id, color_id in VARIANTES:
                variante_id = conn.execute(
                    text("""
                        INSERT INTO variante_prenda (prenda_id, talla_id, color_id, codigo_barras, estado)
                        VALUES (:p, :t, :c, :cb, true)
                        RETURNING id
                    """),
                    {
                        "p": prenda_id,
                        "t": talla_id,
                        "c": color_id,
                        "cb": f"PR{prenda_id}-T{talla_id}-C{color_id}",
                    },
                ).scalar()

                for sucursal_id in SUCURSALES_STOCK:
                    conn.execute(
                        text("""
                            INSERT INTO inventario_sucursal (variante_id, sucursal_id, stock_disponible, stock_reservado, stock_minimo)
                            VALUES (:v, :s, 30, 0, 5)
                            ON CONFLICT (variante_id, sucursal_id) DO NOTHING
                        """),
                        {"v": variante_id, "s": sucursal_id},
                    )

            creadas += 1
            print(f"  creada: {nombre} (id={prenda_id})")

        conn.commit()
        print(f"SEED COMPLETADO: {creadas} prendas nuevas agregadas con imagen y stock.")


if __name__ == "__main__":
    seed()
