from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.v1.api import api_router
from app.core.config import settings
from app.core.observabilidad import configurar_logging, registrar_pedido
from app.core.security import clave_jwt
from app.db.session import get_db

configurar_logging()


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Mejor no arrancar que arrancar sin poder firmar sesiones (se valida al levantar el
    # servidor y no al importar, para que el CI pueda importar la app sin secretos)
    clave_jwt()
    yield


app = FastAPI(
    title="FashionStore API",
    description="API REST para Plataforma Inteligente de Comercio Electrónico FashionStore - UAGRM",
    version="1.0.0",
    lifespan=lifespan,
)

# Log de cada pedido con su id y respuesta genérica ante errores inesperados. Se agrega antes que
# CORS para que CORS quede por fuera y también un 500 llegue al navegador con sus cabeceras.
app.middleware("http")(registrar_pedido)

# Configuración de CORS: solo la web publicada y localhost (desarrollo). La web en producción
# llega por el proxy de nginx (mismo origen) y la app móvil no pasa por CORS.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origenes_cors,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Incluir rutas v1
app.include_router(api_router, prefix="/api/v1")


@app.get("/health", tags=["Salud del Sistema"])
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok", "message": "FashionStore backend y base de datos operativos"}
