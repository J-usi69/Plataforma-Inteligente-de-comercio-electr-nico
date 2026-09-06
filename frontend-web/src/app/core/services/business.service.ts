import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import {
  Bitacora,
  Categoria,
  Ciudad,
  Coleccion,
  Permiso,
  Personal,
  Prenda,
  Proveedor,
  Rol,
  Sucursal,
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

  // --- CU-08: Catálogo de Prendas, Categorías y Colecciones ---
  getPrendas(categoriaId?: number): Observable<Prenda[]> {
    const url = categoriaId ? `${this.apiBase}/prendas?categoria_id=${categoriaId}` : `${this.apiBase}/prendas`;
    return this.http.get<Prenda[]>(url);
  }

  getCategorias(): Observable<Categoria[]> {
    return this.http.get<Categoria[]>(`${this.apiBase}/prendas/categorias`);
  }

  getColecciones(): Observable<Coleccion[]> {
    return this.http.get<Coleccion[]>(`${this.apiBase}/prendas/colecciones`);
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

  // --- Bitácora de Auditoría ---
  getBitacora(): Observable<Bitacora[]> {
    return this.http.get<Bitacora[]>(`${this.apiBase}/auth/bitacora`);
  }
}
