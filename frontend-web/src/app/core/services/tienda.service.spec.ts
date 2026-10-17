import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { authInterceptor } from '../interceptors/auth.interceptor';
import { tiendaInterceptor } from '../interceptors/tienda.interceptor';
import { aplicarMarca } from '../utils/marca';
import { AuthService } from './auth.service';
import { PlataformaService } from './plataforma.service';
import { TiendaService, claveDeEmpresa, slugDeLaUrl } from './tienda.service';

describe('Empresa de la URL', () => {
  it('sale del prefijo /t/<slug>/ y sin prefijo es la tienda por defecto', () => {
    expect(slugDeLaUrl('/t/moda-andina/catalogo')).toBe('moda-andina');
    expect(slugDeLaUrl('/t/moda-andina')).toBe('moda-andina');
    expect(slugDeLaUrl('/catalogo')).toBeNull();
    expect(slugDeLaUrl('/t/ab/')).toBeNull(); // menos de 3 caracteres: no es una dirección válida
    expect(slugDeLaUrl('/t/Con-Mayusculas/')).toBeNull();
  });

  it('cada empresa guarda su sesión y su bolsa con claves propias', () => {
    expect(claveDeEmpresa('fs_token', null)).toBe('fs_token');
    expect(claveDeEmpresa('fs_token', 'moda-andina')).toBe('fs_token:moda-andina');
  });

  it('los colores de la marca reemplazan a los tokens de la hoja de estilos', () => {
    const raiz = document.createElement('div');
    aplicarMarca('#0F766E', '#F59E0B', raiz);
    expect(raiz.style.getPropertyValue('--primary')).toBe('#0F766E');
    expect(raiz.style.getPropertyValue('--primary-light')).toBe('#ecf4f3');
    expect(raiz.style.getPropertyValue('--primary-glow')).toBe('rgba(15, 118, 110, 0.25)');
    expect(raiz.style.getPropertyValue('--accent')).toBe('#F59E0B');
  });
});

describe('Interceptores del SaaS', () => {
  let http: HttpClient;
  let backend: HttpTestingController;
  const avisoPlan = signal<string | null>(null);

  beforeEach(() => {
    avisoPlan.set(null);
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([tiendaInterceptor, authInterceptor])),
        provideHttpClientTesting(),
        { provide: TiendaService, useValue: { slug: 'moda-andina', avisoPlan } },
        { provide: AuthService, useValue: { token: () => 'token-de-la-empresa' } },
        { provide: PlataformaService, useValue: { token: () => 'token-de-la-plataforma' } },
      ],
    });
    http = TestBed.inject(HttpClient);
    backend = TestBed.inject(HttpTestingController);
  });

  afterEach(() => backend.verify());

  it('manda la empresa de la URL y la sesión de esa empresa', () => {
    http.get('/api/v1/prendas').subscribe();
    const pedido = backend.expectOne('/api/v1/prendas');
    expect(pedido.request.headers.get('X-Tienda')).toBe('moda-andina');
    expect(pedido.request.headers.get('Authorization')).toBe('Bearer token-de-la-empresa');
    pedido.flush([]);
  });

  it('la API de la plataforma usa la sesión del superadmin', () => {
    http.get('/api/v1/plataforma/tiendas').subscribe();
    const pedido = backend.expectOne('/api/v1/plataforma/tiendas');
    expect(pedido.request.headers.get('Authorization')).toBe('Bearer token-de-la-plataforma');
    pedido.flush([]);
  });

  it('respeta la empresa y el token que ya trae el pedido (alta de una empresa nueva)', () => {
    http.get('/api/v1/auth/me', { headers: { 'X-Tienda': 'nueva', Authorization: 'Bearer propio' } }).subscribe();
    const pedido = backend.expectOne('/api/v1/auth/me');
    expect(pedido.request.headers.get('X-Tienda')).toBe('nueva');
    expect(pedido.request.headers.get('Authorization')).toBe('Bearer propio');
    pedido.flush({});
  });

  it('un rechazo por el plan (402) queda como aviso para toda la web', () => {
    http.post('/api/v1/sucursales', {}).subscribe({ error: () => undefined });
    backend
      .expectOne('/api/v1/sucursales')
      .flush({ detail: 'Tu plan Básico permite hasta 2 sucursales.' }, { status: 402, statusText: 'Payment Required' });
    expect(avisoPlan()).toBe('Tu plan Básico permite hasta 2 sucursales.');
  });
});
