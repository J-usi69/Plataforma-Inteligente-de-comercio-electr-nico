import { HttpClient } from '@angular/common/http';
import { Injectable, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { Observable, tap } from 'rxjs';
import { TokenResponse, Usuario } from '../models/user.model';
import { TiendaService } from './tienda.service';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly http = inject(HttpClient);
  private readonly router = inject(Router);
  private readonly baseUrl = '/api/v1/auth';
  // Cada empresa guarda su propia sesión: un token solo vale en la empresa que lo emitió
  private readonly claveToken = inject(TiendaService).clave('fs_token');
  private readonly claveUsuario = inject(TiendaService).clave('fs_user');

  private readonly _currentUser = signal<Usuario | null>(null);
  private readonly _token = signal<string | null>(null);

  readonly currentUser = this._currentUser.asReadonly();
  readonly token = this._token.asReadonly();
  readonly isLoggedIn = computed(() => !!this._currentUser());
  readonly isAdmin = computed(() => this._currentUser()?.roles.includes('Administrador') ?? false);
  readonly isCliente = computed(() => this._currentUser()?.roles.includes('Cliente') ?? false);
  readonly isEncargado = computed(() => {
    const u = this._currentUser();
    return u?.roles.includes('Encargado') || u?.personal?.cargo === 'Encargado';
  });
  readonly isCajero = computed(() => {
    const u = this._currentUser();
    return u?.roles.includes('Cajero') || u?.personal?.cargo === 'Cajero';
  });
  readonly isProveedor = computed(() => this._currentUser()?.roles.includes('Proveedor') ?? false);
  readonly sucursalId = computed(() => {
    return this._currentUser()?.personal?.sucursal_id ?? 1;
  });

  constructor() {
    this.initSession();
  }

  private initSession(): void {
    const savedToken = localStorage.getItem(this.claveToken);
    const savedUser = localStorage.getItem(this.claveUsuario);
    if (savedToken && savedUser) {
      try {
        this._token.set(savedToken);
        this._currentUser.set(JSON.parse(savedUser));
      } catch {
        this.clearSession();
      }
    }
  }

  login(credentials: { login: string; password: string }): Observable<TokenResponse> {
    return this.http.post<TokenResponse>(`${this.baseUrl}/login`, credentials).pipe(
      tap((res) => {
        this._token.set(res.access_token);
        this._currentUser.set(res.usuario);
        localStorage.setItem(this.claveToken, res.access_token);
        localStorage.setItem(this.claveUsuario, JSON.stringify(res.usuario));
      })
    );
  }

  register(userData: { correo: string; password: string; celular?: string }): Observable<Usuario> {
    return this.http.post<Usuario>(`${this.baseUrl}/register`, userData);
  }

  logout(): void {
    if (this._token()) {
      this.http.post(`${this.baseUrl}/logout`, {}).subscribe({
        complete: () => this.clearSession(),
        error: () => this.clearSession(),
      });
    } else {
      this.clearSession();
    }
  }

  private clearSession(): void {
    this._token.set(null);
    this._currentUser.set(null);
    localStorage.removeItem(this.claveToken);
    localStorage.removeItem(this.claveUsuario);
    this.router.navigate(['/login']);
  }

  updateProfile(data: { celular?: string; estado?: boolean }): Observable<Usuario> {
    return this.http.put<Usuario>(`${this.baseUrl}/me`, data).pipe(
      tap((updated) => {
        this._currentUser.set(updated);
        localStorage.setItem(this.claveUsuario, JSON.stringify(updated));
      })
    );
  }
}

