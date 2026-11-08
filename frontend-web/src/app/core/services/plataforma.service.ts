import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Injectable, computed, inject, signal } from '@angular/core';
import { Observable, firstValueFrom, tap } from 'rxjs';
import { Usuario } from '../models/user.model';
import { IndicadoresPlataforma, NuevoPlan, Plan, PlanAdmin, RegistroTienda, TiendaAdmin } from '../models/tienda.model';
import { FuenteReportes, FuenteRespaldo, reportesHttp, respaldoHttp } from './fuentes';
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

  /** Todos los planes, también los desactivados, con cuántas empresas tiene cada uno. */
  planesAdmin(): Observable<PlanAdmin[]> {
    return this.http.get<PlanAdmin[]>(`${this.base}/planes/todos`);
  }

  crearPlan(datos: NuevoPlan): Observable<PlanAdmin> {
    return this.http.post<PlanAdmin>(`${this.base}/planes`, datos);
  }

  configurarPlan(codigo: string, cambios: Partial<PlanAdmin>): Observable<PlanAdmin> {
    return this.http.put<PlanAdmin>(`${this.base}/planes/${codigo}`, cambios);
  }

  /** Solo se elimina un plan que nunca se contrató; si no, 409 y se ofrece desactivarlo. */
  eliminarPlan(codigo: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/planes/${codigo}`);
  }

  // --- Reportes e indicadores ---
  indicadores(): Observable<IndicadoresPlataforma> {
    return this.http.get<IndicadoresPlataforma>(`${this.base}/indicadores`);
  }

  /** Reportes personalizables de todas las empresas (incluida la bitácora de la plataforma). */
  readonly reportes: FuenteReportes = reportesHttp(this.http, `${this.base}/reportes`);

  // --- Respaldo y restauración ---
  readonly respaldoSistema: FuenteRespaldo = respaldoHttp(this.http, `${this.base}/respaldo`);

  respaldoDeEmpresa(tiendaId: number): FuenteRespaldo {
    return respaldoHttp(this.http, `${this.base}/tiendas/${tiendaId}/respaldo`);
  }
}
