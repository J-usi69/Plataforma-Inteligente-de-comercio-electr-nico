import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Injectable, computed, inject, signal } from '@angular/core';
import { firstValueFrom, timeout } from 'rxjs';
import { FuncionesPlan, TiendaPublica } from '../models/tienda.model';
import { aplicarMarca } from '../utils/marca';

// Misma regla que validar_slug() del backend
const RUTA_DE_EMPRESA = /^\/t\/([a-z0-9](?:[a-z0-9-]{1,38}[a-z0-9]))(?:\/|$)/;

/** Empresa (tenant) de la URL: /t/<slug>/...; sin prefijo, la tienda por defecto del backend. */
export function slugDeLaUrl(ruta: string = window.location.pathname): string | null {
  return RUTA_DE_EMPRESA.exec(ruta)?.[1] ?? null;
}

/** Base del router: con /t/<slug>/ como base, las rutas de siempre (/catalogo, /admin...) quedan
 * dentro de la empresa sin cambiar ningún enlace. Pasar a otra empresa recarga la página. */
export function baseDeLaApp(): string {
  const slug = slugDeLaUrl();
  return slug ? `/t/${slug}/` : '/';
}

/** Clave de localStorage de una empresa: la sesión y la bolsa de una no se mezclan con otra. */
export function claveDeEmpresa(nombre: string, slug: string | null): string {
  return slug ? `${nombre}:${slug}` : nombre;
}

@Injectable({ providedIn: 'root' })
export class TiendaService {
  private readonly http = inject(HttpClient);

  readonly slug = slugDeLaUrl();
  private readonly _tienda = signal<TiendaPublica | null>(null);
  readonly tienda = this._tienda.asReadonly();
  readonly nombre = computed(() => this._tienda()?.nombre ?? 'FashionStore');
  readonly vigente = computed(() => this._tienda()?.suscripcion_vigente ?? true);
  readonly noExiste = signal(false);
  /** Último rechazo del backend por el plan o la suscripción (402): lo muestra el aviso global. */
  readonly avisoPlan = signal<string | null>(null);

  /** Mientras no cargó, se asume que sí: no se ocultan por un instante cosas que el plan incluye. */
  tiene(funcion: keyof FuncionesPlan): boolean {
    return this._tienda()?.funciones[funcion] ?? true;
  }

  clave(nombre: string): string {
    return claveDeEmpresa(nombre, this.slug);
  }

  /** Se llama al arrancar (app.config.ts) y después de cambiar de plan. */
  async cargar(): Promise<void> {
    try {
      const tienda = await firstValueFrom(this.http.get<TiendaPublica>('/api/v1/tienda').pipe(timeout(5000)));
      this._tienda.set(tienda);
      aplicarMarca(tienda.color_primario, tienda.color_acento);
      document.title = tienda.nombre;
    } catch (err) {
      // 404: la dirección no es de ninguna empresa. Otros errores (red, timeout): se sigue con la marca por defecto
      if (err instanceof HttpErrorResponse && err.status === 404) {
        this.noExiste.set(true);
      }
    }
  }
}
