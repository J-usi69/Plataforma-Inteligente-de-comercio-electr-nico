from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth,
    catalogo_maestro,
    ia,
    inventario,
    personal,
    prendas,
    proveedor_self,
    proveedores,
    reportes,
    reservas,
    roles,
    sucursales,
    temporadas,
    variantes,
    ventas,
    vestidor_ar,
)

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Autenticación (CU-01, CU-02, CU-03)"])
api_router.include_router(roles.router, tags=["Roles y Permisos (CU-04)"])
api_router.include_router(personal.router, prefix="/personal", tags=["Personal (CU-05)"])
api_router.include_router(sucursales.router, prefix="/sucursales", tags=["Sucursales (CU-06)"])
api_router.include_router(proveedores.router, prefix="/proveedores", tags=["Proveedores (CU-07)"])
api_router.include_router(proveedor_self.router, prefix="/proveedor", tags=["Panel de Proveedor (CU-33, CU-34)"])
api_router.include_router(prendas.router, prefix="/prendas", tags=["Catálogo de Prendas (CU-08, CU-12)"])
api_router.include_router(catalogo_maestro.router, prefix="/catalogo-maestro", tags=["Categorías, Tallas y Colores (CU-09)"])
api_router.include_router(temporadas.router, tags=["Temporadas y Colecciones (CU-10)"])
api_router.include_router(variantes.router, prefix="/prendas", tags=["Variantes de Prenda (CU-11)"])
api_router.include_router(vestidor_ar.router, prefix="/vestidor-ar", tags=["Vestidor Virtual RA (CU-14)"])
api_router.include_router(inventario.router, prefix="/inventario", tags=["Disponibilidad por Sucursal (CU-13)"])
api_router.include_router(reservas.router, prefix="/reservas", tags=["Reservas (CU-15, CU-16)"])
api_router.include_router(ventas.router, prefix="/ventas", tags=["Ventas, Caja y Pagos"])
api_router.include_router(reportes.router, prefix="/reportes", tags=["Reportes e Indicadores (CU-31, CU-32)"])
api_router.include_router(ia.router, prefix="/ia", tags=["Inteligencia Artificial (CU-28, CU-29, CU-30)"])

