from fastapi import APIRouter, Depends

from app.api.v1.endpoints import (
    auth,
    catalogo_maestro,
    ia,
    inventario,
    notificaciones,
    personal,
    plataforma,
    prendas,
    proveedor_self,
    proveedores,
    reportes,
    reservas,
    roles,
    sincronizacion,
    sucursales,
    temporadas,
    tienda,
    variantes,
    ventas,
    vestidor_ar,
)
from app.services.planes_service import exigir_funcion, exigir_suscripcion_vigente

api_router = APIRouter()

# Operaciones de la tienda: con la suscripción vencida o cancelada se pueden consultar, pero no
# registrar nada (402) hasta renovar. Sesión, marca/plan, plataforma y avisos push quedan libres
# para poder entrar y renovar.
operaciones = [Depends(exigir_suscripcion_vigente)]

api_router.include_router(auth.router, prefix="/auth", tags=["Autenticación (CU-01, CU-02, CU-03)"])
api_router.include_router(roles.router, tags=["Roles y Permisos (CU-04)"], dependencies=operaciones)
api_router.include_router(personal.router, prefix="/personal", tags=["Personal (CU-05)"], dependencies=operaciones)
api_router.include_router(sucursales.router, prefix="/sucursales", tags=["Sucursales (CU-06)"], dependencies=operaciones)
api_router.include_router(proveedores.router, prefix="/proveedores", tags=["Proveedores (CU-07)"], dependencies=operaciones)
api_router.include_router(proveedor_self.router, prefix="/proveedor", tags=["Panel de Proveedor (CU-33, CU-34)"], dependencies=operaciones)
api_router.include_router(prendas.router, prefix="/prendas", tags=["Catálogo de Prendas (CU-08, CU-12)"], dependencies=operaciones)
api_router.include_router(catalogo_maestro.router, prefix="/catalogo-maestro", tags=["Categorías, Tallas y Colores (CU-09)"], dependencies=operaciones)
api_router.include_router(temporadas.router, tags=["Temporadas y Colecciones (CU-10)"], dependencies=operaciones)
api_router.include_router(variantes.router, prefix="/prendas", tags=["Variantes de Prenda (CU-11)"], dependencies=operaciones)
api_router.include_router(vestidor_ar.router, prefix="/vestidor-ar", tags=["Vestidor Virtual RA (CU-14)"], dependencies=operaciones)
api_router.include_router(inventario.router, prefix="/inventario", tags=["Disponibilidad e Inventario por Sucursal (CU-13, CU-26)"], dependencies=operaciones)
api_router.include_router(reservas.router, prefix="/reservas", tags=["Reservas (CU-15, CU-16)"], dependencies=operaciones)
api_router.include_router(ventas.router, prefix="/ventas", tags=["Ventas, Caja y Pagos"], dependencies=operaciones)
api_router.include_router(
    reportes.router, prefix="/reportes", tags=["Reportes e Indicadores (CU-31, CU-32)"],
    dependencies=[Depends(exigir_funcion("reportes"))],
)
api_router.include_router(ia.router, prefix="/ia", tags=["Inteligencia Artificial (CU-28, CU-29, CU-30)"], dependencies=operaciones)
# Con la suscripción vencida, el lote se rechaza entero (402) y el dispositivo lo conserva hasta renovar
api_router.include_router(
    sincronizacion.router, prefix="/sync", tags=["Operación sin conexión y sincronización (PWA y móvil)"],
    dependencies=[*operaciones, Depends(exigir_funcion("operacion_offline"))],
)
api_router.include_router(notificaciones.router, prefix="/notificaciones", tags=["Notificaciones Push"])
api_router.include_router(tienda.router, prefix="/tienda", tags=["SaaS: marca y plan de la tienda"])
api_router.include_router(plataforma.router, prefix="/plataforma", tags=["SaaS: plataforma (alta de tiendas, superadmin)"])

