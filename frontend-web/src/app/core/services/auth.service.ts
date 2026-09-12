import { HttpClient } from '@angular/common/http';
import { Injectable, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { Observable, tap } from 'rxjs';
import { TokenResponse, Usuario } from '../models/user.model';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly http = inject(HttpClient);
  private readonly router = inject(Router);
  private readonly baseUrl = '/api/v1/auth';

  private readonly _currentUser = signal<Usuario | null>(null);
  private readonly _token = signal<string | null>(null);

  readonly currentUser = this._currentUser.asReadonly();
  readonly token = this._token.asReadonly();
  readonly isLoggedIn = computed(() => !!this._currentUser());
  readonly isAdmin = computed(() => this._currentUser()?.roles.includes('Administrador') ?? false);
  readonly isEncargado = computed(() => {
    const u = this._currentUser();
    return u?.roles.includes('Encargado') || u?.personal?.cargo === 'Encargado';
  });
  readonly isCajero = computed(() => {
    const u = this._currentUser();
    return u?.roles.includes('Cajero') || u?.personal?.cargo === 'Cajero';
  });
  readonly sucursalId = computed(() => {
    return this._currentUser()?.personal?.sucursal_id ?? 1;
  });

  constructor() {
    this.initSession();
  }

  private initSession(): void {
    const savedToken = localStorage.getItem('fs_token');
    const savedUser = localStorage.getItem('fs_user');
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
        localStorage.setItem('fs_token', res.access_token);
        localStorage.setItem('fs_user', JSON.stringify(res.usuario));
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
    localStorage.removeItem('fs_token');
    localStorage.removeItem('fs_user');
    this.router.navigate(['/login']);
  }

  updateProfile(data: { celular?: string; estado?: boolean }): Observable<Usuario> {
    return this.http.put<Usuario>(`${this.baseUrl}/me`, data).pipe(
      tap((updated) => {
        this._currentUser.set(updated);
        localStorage.setItem('fs_user', JSON.stringify(updated));
      })
    );
  }
}

