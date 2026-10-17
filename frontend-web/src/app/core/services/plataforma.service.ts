import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Injectable, computed, inject, signal } from '@angular/core';
import { Observable, firstValueFrom, tap } from 'rxjs';
import { Usuario } from '../models/user.model';
import { Plan, RegistroTienda, TiendaAdmin } from '../models/tienda.model';
import { claveDeEmpresa } from './tienda.service';

const CLAVE_TOKEN = 'fs_plataforma_token';

export interface AltaEmpresa {
  nombre_tienda: string;
  slug: string;
  correo: string;
  password: string;
  plan_codigo: string;
}

/** La plataforma SaaS (no una empresa): alta pública de empresas y la sesión del superadmin. */
@Injectable({ providedIn: 'root' })
export class PlataformaService {
  private readonly http = inject(HttpClient);
  private readonly base = '/api/v1/plataforma';

  private readonly _token = signal<string | null>(localStorage.getItem(CLAVE_TOKEN));
  readonly token = this._token.asReadonly();
  readonly conSesion = computed(() => !!this._token());

  // --- Público ---
  planes(): Observable<Plan[]> {
    return this.http.get<Plan[]>(`${this.base}/planes`);
  }

  disponible(slug: string): Observable<{ disponible: boolean; motivo: string | null }> {
    return this.http.get<{ disponible: boolean; motivo: string | null }>(`${this.base}/disponible/${encodeURIComponent(slug)}`);
  }

  registrar(datos: AltaEmpresa): Observable<RegistroTienda> {
    return this.http.post<RegistroTienda>(`${this.base}/registro`, datos);
  }

  /** Deja iniciada la sesión del administrador en su empresa nueva, para que al abrir
   * /t/<slug>/ ya entre como administrador (su token solo vale en esa empresa). */
  async abrirSesionEnEmpresa(registro: RegistroTienda): Promise<void> {
    const headers = new HttpHeaders({ 'X-Tienda': registro.slug, Authorization: `Bearer ${registro.access_token}` });
    const usuario = await firstValueFrom(this.http.get<Usuario>('/api/v1/auth/me', { headers }));
    localStorage.setItem(claveDeEmpresa('fs_token', registro.slug), registro.access_token);
    localStorage.setItem(claveDeEmpresa('fs_user', registro.slug), JSON.stringify(usuario));
  }

  // --- Superadmin ---
  login(correo: string, password: string): Observable<{ access_token: string }> {
    return this.http.post<{ access_token: string }>(`${this.base}/login`, { correo, password }).pipe(
      tap((res) => {
        this._token.set(res.access_token);
        localStorage.setItem(CLAVE_TOKEN, res.access_token);
      }),
    );
  }

  salir(): void {
    this._token.set(null);
    localStorage.removeItem(CLAVE_TOKEN);
  }

  tiendas(): Observable<TiendaAdmin[]> {
    return this.http.get<TiendaAdmin[]>(`${this.base}/tiendas`);
  }

  crearTienda(datos: AltaEmpresa): Observable<TiendaAdmin> {
    return this.http.post<TiendaAdmin>(`${this.base}/tiendas`, datos);
  }

  actualizarTienda(
    id: number,
    cambios: Partial<{ estado: string; plan_codigo: string; estado_suscripcion: string; fecha_vencimiento: string }>,
  ): Observable<TiendaAdmin> {
    return this.http.patch<TiendaAdmin>(`${this.base}/tiendas/${id}`, cambios);
  }

  renovar(id: number, meses: number): Observable<TiendaAdmin> {
    return this.http.post<TiendaAdmin>(`${this.base}/tiendas/${id}/renovar`, { meses });
  }

  configurarPlan(codigo: string, cambios: Partial<Plan>): Observable<Plan> {
    return this.http.put<Plan>(`${this.base}/planes/${codigo}`, cambios);
  }
}
