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
  DisponibilidadSucursal,
  Permiso,
  Personal,
  Prenda,
  Proveedor,
  Reserva,
  Rol,
  Sucursal,
  Talla,
  VariantePrenda,
  Venta,
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

  createProveedor(proveedor: { nombre_empresa: string; contacto?: string }): Observable<Proveedor> {
    return this.http.post<Proveedor>(`${this.apiBase}/proveedores`, proveedor);
  }

  updateProveedor(id: number, proveedor: { nombre_empresa?: string; contacto?: string; estado?: boolean }): Observable<Proveedor> {
    return this.http.put<Proveedor>(`${this.apiBase}/proveedores/${id}`, proveedor);
  }

  deleteProveedor(id: number): Observable<{ message: string }> {
    return this.http.delete<{ message: string }>(`${this.apiBase}/proveedores/${id}`);
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
    datos: { metodo_pago: string; pasarela?: string; numero_tarjeta_simulada?: string; stripe_payment_intent_id?: string }
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
}
