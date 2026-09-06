from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.v1.api import api_router
from app.db.session import get_db

app = FastAPI(
    title="FashionStore API",
    description="API REST para Plataforma Inteligente de Comercio Electrónico FashionStore - UAGRM",
    version="1.0.0",
)

# Configuración de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
