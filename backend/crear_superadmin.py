"""Crea (o reactiva) una cuenta de superadmin de la plataforma SaaS: administra todas las
tiendas desde /plataforma. La contraseña se pide por consola para que no quede en el historial.

    python crear_superadmin.py tu-correo@ejemplo.com
"""
import getpass
import sys
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.security import get_password_hash
from app.db.session import SessionLocal
from app.models.seguridad import Usuario


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    correo = sys.argv[1].strip().lower()
    password = getpass.getpass("Contraseña (mínimo 10 caracteres): ")
    if len(password) < 10 or password != getpass.getpass("Repetila: "):
        sys.exit("Las contraseñas no coinciden o son muy cortas.")

    with SessionLocal() as db:  # sesión de la plataforma: la cuenta no es de ninguna tienda
        usuario = db.scalars(select(Usuario).where(Usuario.tienda_id.is_(None), Usuario.correo == correo)).first()
        if usuario is None:
            usuario = Usuario(tienda_id=None, correo=correo, creado_en=datetime.now(timezone.utc))
            db.add(usuario)
        usuario.password_hash = get_password_hash(password)
        usuario.es_superadmin = True
        usuario.estado = True
        db.commit()
    print(f"Superadmin listo: {correo}. Entrá en /plataforma de la web.")


if __name__ == "__main__":
    main()
