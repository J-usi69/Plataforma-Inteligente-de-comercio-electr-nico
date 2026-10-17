"""Segunda empresa de prueba del SaaS (el enunciado pide al menos dos independientes):
"Moda Andina", con el plan Básico y su propio catálogo, sucursales, personal, clientes,
inventario y ventas de los últimos meses.

Todo lo de la tienda se carga con la sesión de esa tienda, así que pasa por las mismas dos capas
de aislamiento que la app (filtro del ORM y Row Level Security): la tienda FashionStore no ve
nada de esto ni Moda Andina ve lo de FashionStore.

    python seed_empresa_demo.py              # base local
    python seed_empresa_demo.py --en-remoto  # base remota (Supabase): pide el flag a propósito

Si la tienda ya existe no hace nada, así que se puede correr más de una vez.
"""
import random
import sys
from datetime import date, datetime, time, timedelta, timezone
from urllib.parse import urlparse

from sqlalchemy import select

from app.core.config import settings
from app.core.security import get_password_hash
from app.db.session import SessionLocal
from app.db.tenancy import CLAVE_TIENDA
from app.models.catalogo import Categoria, Coleccion, Color, Prenda, Talla, Temporada, VariantePrenda
from app.models.enums import CanalVenta, EstadoPago, EstadoVenta, TipoMovimiento
from app.models.inventario import InventarioSucursal, MovimientoInventario
from app.models.seguridad import Rol, Usuario, UsuarioRol
from app.models.sucursal import Ciudad, Personal, Sucursal
from app.models.tienda import Tienda
from app.models.venta import DetalleVenta, Pago, Venta
from app.services.tiendas_service import crear_tienda

SLUG = "moda-andina"
NOMBRE = "Moda Andina"
DOMINIO = "modaandina.com"
# Mismas contraseñas de demostración que las cuentas de FashionStore (ver README)
CUENTAS = {
    "admin": ("Admin123*", None),
    "encargado": ("Encargado123*", "Encargado"),
    "cajero": ("Cajero123*", "Cajero"),
    "cliente": ("Cliente123*", "Cliente"),
}
SUCURSALES = [
    ("Moda Andina Centro", "La Paz", "Calle Comercio #820, Centro", "22401122", time(9, 0), time(20, 0)),
    ("Moda Andina Cochabamba", "Cochabamba", "Av. Heroínas #455", "44250033", time(9, 30), time(20, 30)),
]
CATEGORIAS = ["Camisas y Blusas", "Pantalones", "Vestidos", "Camperas", "Calzado"]
TALLAS_ROPA = ["S", "M", "L", "XL"]
TALLAS_CALZADO = ["37", "38", "39", "40"]
COLORES = {
    "Negro": "#111827", "Blanco": "#F9FAFB", "Beige": "#D6C3A3",
    "Verde Oliva": "#6B7A3A", "Terracota": "#C2593B", "Celeste": "#93C5FD",
}
# (nombre, categoría, precio en Bs, imagen, colores de sus variantes)
PRENDAS = [
    ("Camisa Denim Andina", "Camisas y Blusas", 159.00,
     "https://images.unsplash.com/photo-1596755094514-f87e34085b2c?w=800&q=80", ["Celeste", "Negro"]),
    ("Blusa de Lino Blanca", "Camisas y Blusas", 139.00,
     "https://images.unsplash.com/photo-1608234807905-4466023792f5?w=800&q=80", ["Blanco", "Beige"]),
    ("Jean Recto Celeste", "Pantalones", 210.00,
     "https://images.unsplash.com/photo-1475178626620-a4d074967452?w=800&q=80", ["Celeste"]),
    ("Palazzo de Algodón Rayado", "Pantalones", 185.00,
     "https://images.unsplash.com/photo-1509631179647-0177331693ae?w=800&q=80", ["Beige", "Negro"]),
    ("Vestido Floral de Verano", "Vestidos", 265.00,
     "https://images.unsplash.com/photo-1496747611176-843222e1e57c?w=800&q=80", ["Terracota", "Celeste"]),
    ("Vestido Blanco Hombros Descubiertos", "Vestidos", 240.00,
     "https://images.unsplash.com/photo-1515372039744-b8f02a3ae446?w=800&q=80", ["Blanco"]),
    ("Campera Bomber Camel", "Camperas", 310.00,
     "https://images.unsplash.com/photo-1591047139829-d91aecb6caea?w=800&q=80", ["Beige", "Verde Oliva"]),
    ("Campera de Corderito", "Camperas", 420.00,
     "https://images.unsplash.com/photo-1572149913824-3e2005fe09fb?w=800&q=80", ["Beige"]),
    ("Zapatillas Urbanas Blancas", "Calzado", 275.00,
     "https://images.unsplash.com/photo-1600185365483-26d7a4cc7519?w=800&q=80", ["Blanco"]),
    ("Sandalias Florales", "Calzado", 295.00,
     "https://images.unsplash.com/photo-1543163521-1bf539c55dd2?w=800&q=80", ["Celeste", "Terracota"]),
]
VENTAS_HISTORICAS = 30
DIAS_DE_HISTORIA = 90


def _usuario(db, clave: str, ahora: datetime, rol: Rol | None) -> Usuario:
    password, _ = CUENTAS[clave]
    usuario = Usuario(
        correo=f"{clave}@{DOMINIO}", password_hash=get_password_hash(password),
        estado=True, verificado=ahora, creado_en=ahora,
    )
    db.add(usuario)
    db.flush()
    if rol:
        db.add(UsuarioRol(usuario_id=usuario.id, rol_id=rol.id))
    return usuario


def _ciudad(db, nombre: str) -> Ciudad:
    ciudad = db.scalars(select(Ciudad).where(Ciudad.nombre == nombre)).first()
    if not ciudad:
        ciudad = Ciudad(nombre=nombre, estado=True)
        db.add(ciudad)
        db.flush()
    return ciudad


def _catalogo(db, ahora: datetime, rng: random.Random, sucursales: list[Sucursal], admin: Usuario) -> list[tuple[VariantePrenda, float]]:
    categorias = {nombre: Categoria(nombre=nombre, descripcion=f"{nombre} de {NOMBRE}", estado=True) for nombre in CATEGORIAS}
    tallas = {nombre: Talla(nombre=nombre) for nombre in TALLAS_ROPA + TALLAS_CALZADO}
    colores = {nombre: Color(nombre=nombre, hex=hex_) for nombre, hex_ in COLORES.items()}
    db.add_all([*categorias.values(), *tallas.values(), *colores.values()])
    temporada = Temporada(nombre="Primavera 2026", tipo="primavera", fecha_inicio=date(2026, 9, 21), fecha_fin=date(2026, 12, 20), estado=True)
    db.add(temporada)
    db.flush()
    coleccion = Coleccion(nombre="Raíces Andinas", descripcion="Textiles y cortes inspirados en el altiplano", temporada_id=temporada.id, estado=True)
    db.add(coleccion)
    db.flush()

    variantes = []
    for nombre, categoria, precio, imagen, nombres_colores in PRENDAS:
        prenda = Prenda(
            nombre=nombre, descripcion=f"{nombre}, de la colección Raíces Andinas.", categoria_id=categorias[categoria].id,
            coleccion_id=coleccion.id, precio_base=precio, imagen_url=imagen, estado=True,
        )
        db.add(prenda)
        db.flush()
        nombres_tallas = TALLAS_CALZADO if categoria == "Calzado" else TALLAS_ROPA
        for nombre_color in nombres_colores:
            for nombre_talla in nombres_tallas[:3]:
                variante = VariantePrenda(
                    prenda_id=prenda.id, talla_id=tallas[nombre_talla].id, color_id=colores[nombre_color].id,
                    codigo_barras=f"MA-{prenda.id}-{nombre_talla}-{nombre_color[:3].upper()}", estado=True,
                )
                db.add(variante)
                db.flush()
                variantes.append((variante, precio))
                for sucursal in sucursales:
                    # Algunas variantes con poco stock, para que el reporte de existencias tenga algo que mostrar
                    stock = rng.choice([2, 3]) if rng.random() < 0.15 else rng.randint(10, 25)
                    db.add(InventarioSucursal(variante_id=variante.id, sucursal_id=sucursal.id, stock_disponible=stock, stock_reservado=0, stock_minimo=4))
                    db.add(MovimientoInventario(
                        variante_id=variante.id, sucursal_id=sucursal.id, tipo_movimiento=TipoMovimiento.entrada, cantidad=stock,
                        referencia_tipo="carga_inicial", usuario_id=admin.id, fecha=ahora - timedelta(days=DIAS_DE_HISTORIA + 1),
                    ))
    db.flush()
    return variantes


def _ventas(db, ahora: datetime, rng: random.Random, sucursales: list[Sucursal], variantes, cajero: Personal, cliente: Usuario) -> int:
    """Ventas de contado de los últimos meses, cerradas igual que en caja: descuentan stock y
    dejan su movimiento de kardex y su pago aprobado."""
    creadas = 0
    for _ in range(VENTAS_HISTORICAS):
        sucursal = rng.choice(sucursales)
        fecha = ahora - timedelta(days=rng.randint(1, DIAS_DE_HISTORIA), hours=rng.randint(0, 8), minutes=rng.randint(0, 59))
        lineas = []
        for variante, precio in rng.sample(variantes, rng.randint(1, 3)):
            inventario = db.scalars(select(InventarioSucursal).where(
                InventarioSucursal.variante_id == variante.id, InventarioSucursal.sucursal_id == sucursal.id,
            )).one()
            cantidad = min(rng.randint(1, 2), inventario.stock_disponible - 1)  # nunca la deja en cero
            if cantidad > 0:
                lineas.append((variante, precio, cantidad, inventario))
        if not lineas:
            continue

        venta = Venta(
            usuario_id=cliente.id if rng.random() < 0.4 else None, personal_id=cajero.id, sucursal_id=sucursal.id,
            tipo_origen=CanalVenta.presencial, estado=EstadoVenta.pagada,
            total=sum(precio * cantidad for _, precio, cantidad, _ in lineas), fecha_venta=fecha,
        )
        db.add(venta)
        db.flush()
        for variante, precio, cantidad, inventario in lineas:
            db.add(DetalleVenta(venta_id=venta.id, variante_id=variante.id, cantidad=cantidad, precio_unitario=precio, subtotal=precio * cantidad))
            inventario.stock_disponible -= cantidad
            db.add(MovimientoInventario(
                variante_id=variante.id, sucursal_id=sucursal.id, tipo_movimiento=TipoMovimiento.venta, cantidad=cantidad,
                referencia_id=venta.id, referencia_tipo="venta_presencial", usuario_id=cajero.usuario_id, fecha=fecha,
            ))
        db.add(Pago(venta_id=venta.id, metodo_pago="efectivo", estado=EstadoPago.aprobado, monto=venta.total, fecha_pago=fecha))
        creadas += 1
    return creadas


def seed() -> int:
    """Crea la empresa con todos sus datos y devuelve su id (o el de la que ya existía)."""
    with SessionLocal() as plataforma:  # sesión sin tienda: el alta es de la plataforma
        existente = plataforma.scalars(select(Tienda).where(Tienda.slug == SLUG)).first()
        if existente:
            print(f"La tienda '{SLUG}' ya existe (id {existente.id}): no se cambió nada.")
            return existente.id
        tienda = crear_tienda(
            plataforma, slug=SLUG, nombre=NOMBRE, correo_admin=f"admin@{DOMINIO}",
            password_admin=CUENTAS["admin"][0], plan_codigo="basico", origen="plataforma",
        )
        tienda.color_primario, tienda.color_acento = "#0F766E", "#F59E0B"
        plataforma.commit()
        tienda_id = tienda.id

    rng = random.Random(2026)  # siempre los mismos datos
    ahora = datetime.now(timezone.utc)
    with SessionLocal(info={CLAVE_TIENDA: tienda_id}) as db:
        roles = {rol.nombre: rol for rol in db.scalars(select(Rol)).all()}
        admin = db.scalars(select(Usuario).where(Usuario.correo == f"admin@{DOMINIO}")).one()

        sucursales = []
        for nombre, ciudad, direccion, telefono, abre, cierra in SUCURSALES:
            sucursal = Sucursal(
                nombre=nombre, ciudad_id=_ciudad(db, ciudad).id, direccion=direccion, telefono=telefono,
                hora_inicio=abre, hora_fin=cierra, estado=True,
            )
            db.add(sucursal)
            sucursales.append(sucursal)
        db.flush()

        encargado = _usuario(db, "encargado", ahora, roles["Encargado"])
        cajero_usuario = _usuario(db, "cajero", ahora, roles["Cajero"])
        cliente = _usuario(db, "cliente", ahora, roles["Cliente"])
        db.add(Personal(usuario_id=encargado.id, sucursal_id=sucursales[0].id, nombres="Rocío", apellidos="Quispe", cargo="Encargado de Sucursal", estado=True))
        cajero = Personal(usuario_id=cajero_usuario.id, sucursal_id=sucursales[0].id, nombres="Marco", apellidos="Mamani", cargo="Cajero de Sucursal", estado=True)
        db.add(cajero)
        db.flush()

        variantes = _catalogo(db, ahora, rng, sucursales, admin)
        ventas = _ventas(db, ahora, rng, sucursales, variantes, cajero, cliente)
        db.commit()

    print(f"Empresa '{NOMBRE}' creada (id {tienda_id}, plan Básico): {len(SUCURSALES)} sucursales, {len(PRENDAS)} prendas, "
          f"{len(variantes)} variantes y {ventas} ventas.")
    print(f"Cuentas: {', '.join(f'{c}@{DOMINIO} / {p}' for c, (p, _) in CUENTAS.items())}")
    return tienda_id


def main() -> None:
    host = urlparse(settings.database_url).hostname
    if host not in {"localhost", "127.0.0.1", "postgres"} and "--en-remoto" not in sys.argv:
        sys.exit(f"DATABASE_URL apunta a '{host}'. Para crear la empresa de prueba en esa base, corré con --en-remoto.")
    seed()


if __name__ == "__main__":
    main()
