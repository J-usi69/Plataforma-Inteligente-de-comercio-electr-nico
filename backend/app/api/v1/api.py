from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth,
    personal,
    prendas,
    proveedores,
    roles,
    sucursales,
)

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Autenticación (CU-01, CU-02, CU-03)"])
api_router.include_router(roles.router, tags=["Roles y Permisos (CU-04)"])
api_router.include_router(personal.router, prefix="/personal", tags=["Personal (CU-05)"])
api_router.include_router(sucursales.router, prefix="/sucursales", tags=["Sucursales (CU-06)"])
api_router.include_router(proveedores.router, prefix="/proveedores", tags=["Proveedores (CU-07)"])
api_router.include_router(prendas.router, prefix="/prendas", tags=["Catálogo de Prendas (CU-08)"])

