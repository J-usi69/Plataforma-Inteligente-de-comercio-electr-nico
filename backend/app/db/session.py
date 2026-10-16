from fastapi import Request
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db(request: Request):
    """Sesión de la tienda del pedido: todo lo que se consulta o guarda queda en esa tienda."""
    from app.db.tenancy import CLAVE_TIENDA, tienda_de_la_peticion

    tienda = tienda_de_la_peticion(request)
    db = SessionLocal(info={CLAVE_TIENDA: tienda.id})
    try:
        yield db
    finally:
        db.close()


def get_db_plataforma():
    """Sesión sin tienda, para la administración de la plataforma (superadmin, alta de tiendas)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Registra los eventos que filtran por tienda y activan el RLS (ver app/db/tenancy.py)
import app.db.tenancy  # noqa: E402,F401
