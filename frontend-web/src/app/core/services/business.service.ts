import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import {
  Bitacora,
  Categoria,
  Ciudad,
  Coleccion,
  Color,
  ComprobanteVenta,
  DashboardReporte,
  DisponibilidadProveedor,
  DisponibilidadSucursal,
  InventarioGlobalItem,
  InventarioVariante,
  MovimientoManual,
  Permiso,
  Personal,
  Prenda,
  PrendaVendida,
  Proveedor,
  QuiebreStock,
  Reserva,
  Rol,
  Sucursal,
  Talla,
  Temporada,
  VariantePrenda,
  Venta,
  VentaPorSucursal,
  VestidorCapabilities,
  VestidorJob,
} from '../models/user.model';

@Injectable({ providedIn: 'root' })
export class BusinessService {
  private readonly http = inject(HttpClient);
  private readonly apiBase = '/api/v1';

  // --- CU-04: Roles y Permisos ---
  getRoles(): Observable<Rol[]> {
    return this.http.get<Rol[]>(`${this.apiBase}/roles`);
  }

  getPermisos(): Observable<Permiso[]> {
    return this.http.get<Permiso[]>(`${this.apiBase}/permisos`);
  }

  createRol(rol: { nombre: string; descripcion?: string; permiso_ids?: number[] }): Observable<Rol> {
    return this.http.post<Rol>(`${this.apiBase}/roles`, rol);
  }

  updateRol(id: number, rol: { nombre?: string; descripcion?: string; estado?: boolean; permiso_ids?: number[] }): Observable<Rol> {
    return this.http.put<Rol>(`${this.apiBase}/roles/${id}`, rol);
  }

  deleteRol(id: number): Observable<{ message: string }> {
    return this.http.delete<{ message: string }>(`${this.apiBase}/roles/${id}`);
  }

  // --- CU-05: Personal ---
  getPersonal(): Observable<Personal[]> {
    return this.http.get<Personal[]>(`${this.apiBase}/personal`);
  }

  createPersonal(personal: {
    nombres: string;
    apellidos: string;
    cargo: string;
    sucursal_id?: number | null;
    correo: string;
    celular?: string;
    password: string;
  }): Observable<Personal> {
    return this.http.post<Personal>(`${this.apiBase}/personal`, personal);
  }

  updatePersonal(id: number, personal: {
    nombres?: string;
    apellidos?: string;
    cargo?: string;
    sucursal_id?: number | null;
    estado?: boolean;
    celular?: string;
  }): Observable<Personal> {
    return this.http.put<Personal>(`${this.apiBase}/personal/${id}`, personal);
  }

  deletePersonal(id: number): Observable<{ message: string }> {
    return this.http.delete<{ message: string }>(`${this.apiBase}/personal/${id}`);
  }

  // --- CU-06: Sucursales y Ciudades ---
  getSucursales(): Observable<Sucursal[]> {
    return this.http.get<Sucursal[]>(`${this.apiBase}/sucursales`);
  }

  getCiudades(): Observable<Ciudad[]> {
    return this.http.get<Ciudad[]>(`${this.apiBase}/sucursales/ciudades`);
  }

  createCiudad(nombre: string): Observable<Ciudad> {
    return this.http.post<Ciudad>(`${this.apiBase}/sucursales/ciudades`, { nombre });
  }

  createSucursal(sucursal: {
    nombre: string;
    ciudad_id: number;
    direccion: string;
    telefono?: string;
    hora_inicio?: string;
    hora_fin?: string;
  }): Observable<Sucursal> {
    return this.http.post<Sucursal>(`${this.apiBase}/sucursales`, sucursal);
  }

  updateSucursal(id: number, sucursal: {
    nombre?: string;
    ciudad_id?: number;
    direccion?: string;
    telefono?: string;
    hora_inicio?: string;
    hora_fin?: string;
    estado?: boolean;
  }): Observable<Sucursal> {
    return this.http.put<Sucursal>(`${this.apiBase}/sucursales/${id}`, sucursal);
  }

  deleteSucursal(id: number): Observable<{ message: string }> {
    return this.http.delete<{ message: string }>(`${this.apiBase}/sucursales/${id}`);
  }

  // --- CU-07: Proveedores ---
  getProveedores(): Observable<Proveedor[]> {
    return this.http.get<Proveedor[]>(`${this.apiBase}/proveedores`);
  }

  createProveedor(proveedor: { nombre_empresa: string; contacto?: string; correo?: string; password?: string }): Observable<Proveedor> {
    return this.http.post<Proveedor>(`${this.apiBase}/proveedores`, proveedor);
  }

  updateProveedor(id: number, proveedor: { nombre_empresa?: string; contacto?: string; estado?: boolean }): Observable<Proveedor> {
    return this.http.put<Proveedor>(`${this.apiBase}/proveedores/${id}`, proveedor);
  }

  deleteProveedor(id: number): Observable<{ message: string }> {
    return this.http.delete<{ message: string }>(`${this.apiBase}/proveedores/${id}`);
  }

  getDisponibilidadProveedor(proveedorId: number): Observable<DisponibilidadProveedor[]> {
    return this.http.get<DisponibilidadProveedor[]>(`${this.apiBase}/proveedores/${proveedorId}/disponibilidad`);
  }

  // --- CU-33 / CU-34: Panel de Proveedor (self-service) ---
  getMisProductosProveedor(): Observable<Prenda[]> {
    return this.http.get<Prenda[]>(`${this.apiBase}/proveedor/prendas`);
  }

  registrarProductoProveedor(datos: {
    nombre: string;
    descripcion?: string;
    categoria_id: number;
    precio_base: number;
    modelo_3d_url?: string;
    forzar?: boolean;
  }): Observable<Prenda> {
    return this.http.post<Prenda>(`${this.apiBase}/proveedor/prendas`, datos);
  }

  informarDisponibilidad(prendaId: number, datos: { cantidad: number; fecha_estimada: string }): Observable<DisponibilidadProveedor> {
    return this.http.post<DisponibilidadProveedor>(`${this.apiBase}/proveedor/prendas/${prendaId}/disponibilidad`, datos);
  }

  getMiDisponibilidad(): Observable<DisponibilidadProveedor[]> {
    return this.http.get<DisponibilidadProveedor[]>(`${this.apiBase}/proveedor/disponibilidad`);
  }

  // --- CU-10: Temporadas y Colecciones (administración) ---
  // Nota: getColecciones() (más abajo) apunta a /prendas/colecciones (listado simple,
  // solo activas, usado por el combo del formulario de Prenda) y NO debe tocarse.
  // Estos métodos administran el CRUD completo vía /temporadas y /colecciones.
  listarTemporadas(): Observable<Temporada[]> {
    return this.http.get<Temporada[]>(`${this.apiBase}/temporadas`);
  }

  crearTemporada(datos: { nombre: string; tipo?: string; fecha_inicio?: string; fecha_fin?: string }): Observable<Temporada> {
    return this.http.post<Temporada>(`${this.apiBase}/temporadas`, datos);
  }

  actualizarTemporada(id: number, datos: {
    nombre?: string;
    tipo?: string;
    fecha_inicio?: string;
    fecha_fin?: string;
    estado?: boolean;
  }): Observable<Temporada> {
    return this.http.put<Temporada>(`${this.apiBase}/temporadas/${id}`, datos);
  }

  listarColeccionesAdmin(temporadaId?: number): Observable<Coleccion[]> {
    const params: any = {};
    if (temporadaId) params.temporada_id = temporadaId;
    return this.http.get<Coleccion[]>(`${this.apiBase}/colecciones`, { params });
  }

  crearColeccionAdmin(datos: { nombre: string; descripcion?: string; temporada_id: number }): Observable<Coleccion> {
    return this.http.post<Coleccion>(`${this.apiBase}/colecciones`, datos);
  }

  actualizarColeccionAdmin(id: number, datos: {
    nombre?: string;
    descripcion?: string;
    temporada_id?: number;
    estado?: boolean;
  }): Observable<Coleccion> {
    return this.http.put<Coleccion>(`${this.apiBase}/colecciones/${id}`, datos);
  }

  // --- CU-08 / CU-12: Catálogo de Prendas, Categorías y Colecciones ---
  getPrendas(filtros?: {
    categoriaId?: number;
    coleccionId?: number;
    temporadaId?: number;
    tallaId?: number;
    colorId?: number;
    buscar?: string;
  }): Observable<Prenda[]> {
    const params = new URLSearchParams();
    if (filtros?.categoriaId) params.set('categoria_id', String(filtros.categoriaId));
    if (filtros?.coleccionId) params.set('coleccion_id', String(filtros.coleccionId));
    if (filtros?.temporadaId) params.set('temporada_id', String(filtros.temporadaId));
    if (filtros?.tallaId) params.set('talla_id', String(filtros.tallaId));
    if (filtros?.colorId) params.set('color_id', String(filtros.colorId));
    if (filtros?.buscar) params.set('buscar', filtros.buscar);
    const query = params.toString();
    return this.http.get<Prenda[]>(`${this.apiBase}/prendas${query ? '?' + query : ''}`);
  }

  // CU-33: prendas registradas por un Proveedor que el catalogo publico (arriba)
  // no muestra porque tienen estado=false hasta que el Admin las activa.
  getPrendasPendientesValidacion(): Observable<Prenda[]> {
    return this.http.get<Prenda[]>(`${this.apiBase}/prendas/pendientes-validacion`);
  }

  getCategorias(): Observable<Categoria[]> {
    return this.http.get<Categoria[]>(`${this.apiBase}/prendas/categorias`);
  }

  getColecciones(): Observable<Coleccion[]> {
    return this.http.get<Coleccion[]>(`${this.apiBase}/prendas/colecciones`);
  }

  // --- CU-09: Catálogos maestros (Categorías, Tallas y Colores) ---
  createCategoria(datos: { nombre: string; descripcion?: string | null }): Observable<Categoria> {
    return this.http.post<Categoria>(`${this.apiBase}/catalogo-maestro/categorias`, datos);
  }

  updateCategoria(id: number, datos: { nombre?: string; descripcion?: string | null; estado?: boolean }): Observable<Categoria> {
    return this.http.put<Categoria>(`${this.apiBase}/catalogo-maestro/categorias/${id}`, datos);
  }

  getTallas(): Observable<Talla[]> {
    return this.http.get<Talla[]>(`${this.apiBase}/catalogo-maestro/tallas`);
  }

  createTalla(nombre: string): Observable<Talla> {
    return this.http.post<Talla>(`${this.apiBase}/catalogo-maestro/tallas`, { nombre });
  }

  updateTalla(id: number, nombre: string): Observable<Talla> {
    return this.http.put<Talla>(`${this.apiBase}/catalogo-maestro/tallas/${id}`, { nombre });
  }

  deleteTalla(id: number): Observable<{ message: string }> {
    return this.http.delete<{ message: string }>(`${this.apiBase}/catalogo-maestro/tallas/${id}`);
  }

  getColores(): Observable<Color[]> {
    return this.http.get<Color[]>(`${this.apiBase}/catalogo-maestro/colores`);
  }

  createColor(datos: { nombre: string; hex?: string | null }): Observable<Color> {
    return this.http.post<Color>(`${this.apiBase}/catalogo-maestro/colores`, datos);
  }

  updateColor(id: number, datos: { nombre?: string; hex?: string | null }): Observable<Color> {
    return this.http.put<Color>(`${this.apiBase}/catalogo-maestro/colores/${id}`, datos);
  }

  deleteColor(id: number): Observable<{ message: string }> {
    return this.http.delete<{ message: string }>(`${this.apiBase}/catalogo-maestro/colores/${id}`);
  }

  // --- CU-11: Variantes de prenda ---
  getVariantes(prendaId: number): Observable<VariantePrenda[]> {
    return this.http.get<VariantePrenda[]>(`${this.apiBase}/prendas/${prendaId}/variantes`);
  }

  createVariante(prendaId: number, datos: { talla_id: number; color_id: number }): Observable<VariantePrenda> {
    return this.http.post<VariantePrenda>(`${this.apiBase}/prendas/${prendaId}/variantes`, datos);
  }

  deleteVariante(prendaId: number, varianteId: number): Observable<{ message: string }> {
    return this.http.delete<{ message: string }>(`${this.apiBase}/prendas/${prendaId}/variantes/${varianteId}`);
  }

  // --- CU-13: Disponibilidad por sucursal ---
  getDisponibilidad(varianteId: number): Observable<DisponibilidadSucursal[]> {
    return this.http.get<DisponibilidadSucursal[]>(`${this.apiBase}/inventario/disponibilidad/${varianteId}`);
  }

  // --- CU-26: Registro manual de movimientos de inventario (Encargado) ---
  getInventarioEncargado(): Observable<InventarioVariante[]> {
    return this.http.get<InventarioVariante[]>(`${this.apiBase}/inventario/encargado/variantes`);
  }

  registrarMovimientoInventario(datos: { variante_id: number; tipo: string; cantidad: number }): Observable<MovimientoManual> {
    return this.http.post<MovimientoManual>(`${this.apiBase}/inventario/encargado/movimientos`, datos);
  }

  // --- CU-15 / CU-16: Reservas ---
  getMisReservas(): Observable<Reserva[]> {
    return this.http.get<Reserva[]>(`${this.apiBase}/reservas`);
  }

  crearReserva(datos: {
    sucursal_id: number;
    horario_atencion?: string;
    detalles: { variante_id: number; cantidad: number }[];
  }): Observable<Reserva> {
    return this.http.post<Reserva>(`${this.apiBase}/reservas`, datos);
  }

  cancelarReserva(id: number): Observable<Reserva> {
    return this.http.post<Reserva>(`${this.apiBase}/reservas/${id}/cancelar`, {});
  }

  createPrenda(prenda: {
    nombre: string;
    descripcion?: string;
    categoria_id: number;
    coleccion_id?: number | null;
    proveedor_id?: number | null;
    precio_base: number;
    modelo_3d_url?: string;
  }): Observable<Prenda> {
    return this.http.post<Prenda>(`${this.apiBase}/prendas`, prenda);
  }

  updatePrenda(id: number, prenda: {
    nombre?: string;
    descripcion?: string;
    categoria_id?: number;
    coleccion_id?: number | null;
    proveedor_id?: number | null;
    precio_base?: number;
    modelo_3d_url?: string;
    estado?: boolean;
  }): Observable<Prenda> {
    return this.http.put<Prenda>(`${this.apiBase}/prendas/${id}`, prenda);
  }

  deletePrenda(id: number): Observable<{ message: string }> {
    return this.http.delete<{ message: string }>(`${this.apiBase}/prendas/${id}`);
  }

  // --- Gestión de reservas por sucursal (Encargado) ---
  getReservasSucursal(sucursalId: number, estado?: string): Observable<Reserva[]> {
    const params: any = {};
    if (estado) params.estado = estado;
    return this.http.get<Reserva[]>(`${this.apiBase}/reservas/sucursal/${sucursalId}`, { params });
  }

  confirmarPreparacionReserva(reservaId: number): Observable<Reserva> {
    return this.http.post<Reserva>(`${this.apiBase}/reservas/${reservaId}/confirmar`, {});
  }

  confirmarRecepcionCliente(reservaId: number): Observable<Reserva> {
    return this.http.post<Reserva>(`${this.apiBase}/reservas/${reservaId}/atender`, {});
  }

  marcarReservaNoShow(reservaId: number): Observable<Reserva> {
    return this.http.post<Reserva>(`${this.apiBase}/reservas/${reservaId}/no-show`, {});
  }

  // --- Ventas presenciales y cobro en caja (Cajero) ---
  registrarVentaPresencial(datos: {
    sucursal_id?: number;
    reserva_id?: number | null;
    cliente_id?: number | null;
    detalles: { variante_id: number; cantidad: number; precio_unitario?: number }[];
  }): Observable<Venta> {
    return this.http.post<Venta>(`${this.apiBase}/ventas/presencial`, datos);
  }

  cobrarEnCaja(ventaId: number, datos: { metodo_pago: string; monto_recibido?: number }): Observable<Venta> {
    return this.http.post<Venta>(`${this.apiBase}/ventas/${ventaId}/cobrar-caja`, datos);
  }

  getVentasSucursal(sucursalId: number): Observable<Venta[]> {
    return this.http.get<Venta[]>(`${this.apiBase}/ventas/sucursal/${sucursalId}`);
  }

  // --- Compra digital y pasarela de pago (Cliente) ---
  crearVentaDigital(datos: {
    sucursal_id: number;
    detalles: { variante_id: number; cantidad: number }[];
  }): Observable<Venta> {
    return this.http.post<Venta>(`${this.apiBase}/ventas/digital`, datos);
  }

  pagarVentaDigital(
    ventaId: number,
    datos: { metodo_pago: string; stripe_payment_intent_id?: string }
  ): Observable<Venta> {
    return this.http.post<Venta>(`${this.apiBase}/ventas/${ventaId}/pagar-digital`, datos);
  }

  crearIntentoPagoStripe(ventaId: number): Observable<{ client_secret: string }> {
    return this.http.post<{ client_secret: string }>(`${this.apiBase}/ventas/${ventaId}/crear-intento-pago`, {});
  }

  // --- Comprobante oficial de venta ---
  getComprobanteVenta(ventaId: number): Observable<ComprobanteVenta> {
    return this.http.get<ComprobanteVenta>(`${this.apiBase}/ventas/comprobante/${ventaId}`);
  }

  // --- Historial de compras del cliente ---
  getMisCompras(): Observable<Venta[]> {
    return this.http.get<Venta[]>(`${this.apiBase}/ventas/mis-compras`);
  }

  // --- Bitácora de Auditoría ---
  getBitacora(): Observable<Bitacora[]> {
    return this.http.get<Bitacora[]>(`${this.apiBase}/auth/bitacora`);
  }

  // --- CU-31 / CU-32: Reportes e Indicadores ---
  getDashboard(filtros?: { sucursalId?: number; ciudadId?: number; desde?: string; hasta?: string }): Observable<DashboardReporte> {
    const params: any = {};
    if (filtros?.sucursalId) params.sucursal_id = filtros.sucursalId;
    if (filtros?.ciudadId) params.ciudad_id = filtros.ciudadId;
    if (filtros?.desde) params.desde = filtros.desde;
    if (filtros?.hasta) params.hasta = filtros.hasta;
    return this.http.get<DashboardReporte>(`${this.apiBase}/reportes/dashboard`, { params });
  }

  getReporteVentas(filtros?: { desde?: string; hasta?: string }): Observable<VentaPorSucursal[]> {
    const params: any = {};
    if (filtros?.desde) params.desde = filtros.desde;
    if (filtros?.hasta) params.hasta = filtros.hasta;
    return this.http.get<VentaPorSucursal[]>(`${this.apiBase}/reportes/ventas`, { params });
  }

  getPrendasMasVendidas(filtros?: { desde?: string; hasta?: string; limit?: number }): Observable<PrendaVendida[]> {
    const params: any = {};
    if (filtros?.desde) params.desde = filtros.desde;
    if (filtros?.hasta) params.hasta = filtros.hasta;
    if (filtros?.limit) params.limit = filtros.limit;
    return this.http.get<PrendaVendida[]>(`${this.apiBase}/reportes/prendas-mas-vendidas`, { params });
  }

  getReporteInventario(sucursalId?: number): Observable<QuiebreStock[]> {
    const params: any = {};
    if (sucursalId) params.sucursal_id = sucursalId;
    return this.http.get<QuiebreStock[]>(`${this.apiBase}/reportes/inventario`, { params });
  }

  // --- CU-27: Consulta de inventario global (todas las sucursales) ---
  getInventarioGlobal(filtros?: { ciudadId?: number | null; categoriaId?: number | null }): Observable<InventarioGlobalItem[]> {
    const params: any = {};
    if (filtros?.ciudadId) params.ciudad_id = filtros.ciudadId;
    if (filtros?.categoriaId) params.categoria_id = filtros.categoriaId;
    return this.http.get<InventarioGlobalItem[]>(`${this.apiBase}/reportes/inventario-global`, { params });
  }

  // --- CU-28 / CU-29 / CU-30: Inteligencia Artificial ---
  getRecomendaciones(): Observable<{ prendas: Prenda[]; fuente: string }> {
    return this.http.post<{ prendas: Prenda[]; fuente: string }>(`${this.apiBase}/ia/recomendaciones`, {});
  }

  enviarMensajeChat(mensaje: string, historial?: { rol: 'user' | 'asistente'; contenido: string }[]): Observable<{ respuesta: string }> {
    return this.http.post<{ respuesta: string }>(`${this.apiBase}/ia/chat`, { mensaje, historial });
  }

  generarReporteIA(prompt: string): Observable<{ tipo: string; parametros: any; datos: any }> {
    return this.http.post<{ tipo: string; parametros: any; datos: any }>(`${this.apiBase}/ia/reportes`, { prompt });
  }

  // --- CU-14: Vestidor virtual (probarse una prenda con una foto, generado con IA) ---
  getVestidorCapabilities(): Observable<VestidorCapabilities> {
    return this.http.get<VestidorCapabilities>(`${this.apiBase}/vestidor-ar/capabilities`);
  }

  crearVestidorJob(prendaId: number, foto: Blob): Observable<VestidorJob> {
    const form = new FormData();
    form.append('prenda_id', String(prendaId));
    form.append('persona', foto, 'persona.jpg');
    return this.http.post<VestidorJob>(`${this.apiBase}/vestidor-ar/jobs`, form);
  }

  getVestidorJob(jobId: string): Observable<VestidorJob> {
    return this.http.get<VestidorJob>(`${this.apiBase}/vestidor-ar/jobs/${jobId}`);
  }
}
