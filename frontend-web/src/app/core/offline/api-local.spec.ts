import 'fake-indexeddb/auto';
import { HttpClient, HttpErrorResponse, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { computed, signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { firstValueFrom } from 'rxjs';
import { AuthService } from '../services/auth.service';
import { TiendaService } from '../services/tienda.service';
import { Paquete } from './modelos';
import { offlineInterceptor } from './offline.interceptor';
import { SincronizacionService } from './sincronizacion.service';

const PAQUETE: Paquete = {
  generado_en: new Date().toISOString(),
  vigencia_horas: 12,
  tienda: 'moda-andina',
  dias_para_cambio: 7,
  sucursales: [{ id: 1, nombre: 'Centro', direccion: 'Calle 1', ciudad: 'La Paz' }],
  categorias: [{ id: 1, nombre: 'Poleras' }, { id: 2, nombre: 'Camperas' }],
  tallas: [{ id: 1, nombre: 'M' }],
  colores: [{ id: 1, nombre: 'Negro', hex: '#111111' }],
  prendas: [
    { id: 10, nombre: 'Polera', descripcion: null, categoria_id: 1, precio_base: 100, imagen_url: null },
    { id: 20, nombre: 'Campera', descripcion: null, categoria_id: 2, precio_base: 300, imagen_url: null },
  ],
  variantes: [
    { id: 100, prenda_id: 10, talla_id: 1, color_id: 1, codigo_barras: 'P-M', imagen_url: null },
    { id: 200, prenda_id: 20, talla_id: 1, color_id: 1, codigo_barras: 'C-M', imagen_url: null },
  ],
  inventario: [
    { variante_id: 100, sucursal_id: 1, stock_disponible: 5 },
    { variante_id: 200, sucursal_id: 1, stock_disponible: 0 },
  ],
  clientes: [],
  ventas: [],
};

let base = 0;

describe('El sistema sin conexión funciona igual (API local + cola)', () => {
  let http: HttpClient;
  let backend: HttpTestingController;
  let sync: SincronizacionService;

  const pedir = <T>(metodo: 'GET' | 'POST', url: string, cuerpo?: unknown): Promise<T> =>
    firstValueFrom(metodo === 'GET' ? http.get<T>(url) : http.post<T>(url, cuerpo));

  beforeEach(async () => {
    const usuario = signal({
      id: 7, correo: 'cajero@prueba.com', roles: ['Cajero'], permisos: [], estado: true,
      personal: { id: 3, nombres: 'Marco', apellidos: 'Mamani', cargo: 'Cajero', sucursal_id: 1 },
    });
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([offlineInterceptor])),
        provideHttpClientTesting(),
        { provide: AuthService, useValue: { currentUser: usuario, isLoggedIn: computed(() => !!usuario()), sucursalId: () => 1 } },
        { provide: TiendaService, useValue: { slug: `api-local-${++base}`, tiene: () => true } },
      ],
    });
    http = TestBed.inject(HttpClient);
    backend = TestBed.inject(HttpTestingController);
    sync = TestBed.inject(SincronizacionService);
    const descarga = sync.descargarPaquete();
    backend.expectOne('/api/v1/sync/paquete').flush(PAQUETE);
    await descarga;
    sync.enLinea.set(false);
  });

  afterEach(() => backend.verify());

  it('el catálogo, las variantes y la disponibilidad salen de lo guardado sin tocar la red', async () => {
    const prendas = await pedir<{ nombre: string; categoria_nombre: string }[]>('GET', '/api/v1/prendas?categoria_id=1');
    const variantes = await pedir<{ talla_nombre: string; color_nombre: string }[]>('GET', '/api/v1/prendas/10/variantes');
    const disponibilidad = await pedir<{ sucursal_nombre: string; stock_disponible: number }[]>('GET', '/api/v1/inventario/disponibilidad/100');

    expect(prendas).toEqual([expect.objectContaining({ nombre: 'Polera', categoria_nombre: 'Poleras' })]);
    expect(variantes[0]).toEqual(expect.objectContaining({ talla_nombre: 'M', color_nombre: 'Negro' }));
    expect(disponibilidad).toEqual([expect.objectContaining({ sucursal_nombre: 'Centro', stock_disponible: 5 })]);
    expect(await pedir<unknown[]>('GET', '/api/v1/inventario/disponibilidad/200')).toEqual([]); // sin stock no se ofrece
    backend.expectNone(() => true);
  });

  it('si una lectura no llega al servidor, contesta con lo guardado y pasa a sin conexión', async () => {
    sync.enLinea.set(true);
    const respuesta = pedir<{ nombre: string }[]>('GET', '/api/v1/prendas');
    backend.expectOne('/api/v1/prendas').flush(null, { status: 504, statusText: 'Gateway Timeout' }); // el Service Worker sin red

    expect((await respuesta).map((p) => p.nombre)).toEqual(['Polera', 'Campera']);
    expect(sync.enLinea()).toBe(false);
  });

  it('una reserva sin conexión entra a la cola, descuenta el stock local y aparece en mis reservas', async () => {
    const reserva = await pedir<{ id: number; sincronizacion: string }>('POST', '/api/v1/reservas', {
      sucursal_id: 1,
      detalles: [{ variante_id: 100, cantidad: 2 }],
    });

    expect(reserva.id).toBeLessThan(0);
    expect(reserva.sincronizacion).toBe('registrada');
    expect(sync.operaciones().map((op) => [op.tipo, op.estado])).toEqual([['reserva', 'registrada']]);
    expect((await pedir<{ stock_disponible: number }[]>('GET', '/api/v1/inventario/disponibilidad/100'))[0].stock_disponible).toBe(3);
    expect((await pedir<{ id: number }[]>('GET', '/api/v1/reservas')).map((r) => r.id)).toEqual([reserva.id]);

    await expect(pedir('POST', '/api/v1/reservas', { sucursal_id: 1, detalles: [{ variante_id: 200, cantidad: 1 }] })).rejects.toMatchObject({
      status: 400, // sin stock conocido no se reserva, igual que en el servidor
    });
  });

  it('la caja cobra en efectivo sin conexión y emite el ticket pendiente de sincronizar', async () => {
    const venta = await pedir<{ id: number; total: number; estado: string }>('POST', '/api/v1/ventas/presencial', {
      sucursal_id: 1,
      detalles: [{ variante_id: 100, cantidad: 1, precio_unitario: 100 }],
    });
    expect([venta.id < 0, venta.total, venta.estado]).toEqual([true, 100, 'pendiente']);

    const tarjeta = pedir('POST', `/api/v1/ventas/${venta.id}/cobrar-caja`, { metodo_pago: 'tarjeta' });
    await expect(tarjeta).rejects.toBeInstanceOf(HttpErrorResponse);

    const cobrada = await pedir<{ estado: string }>('POST', `/api/v1/ventas/${venta.id}/cobrar-caja`, { metodo_pago: 'efectivo', monto_recibido: 150 });
    const ticket = await pedir<{ estado_venta: string; cajero_nombre: string; total: number }>('GET', `/api/v1/ventas/comprobante/${venta.id}`);

    expect(cobrada.estado).toBe('pagada');
    expect(ticket).toEqual(expect.objectContaining({ estado_venta: 'PENDIENTE DE SINCRONIZAR', cajero_nombre: 'Marco Mamani', total: 100 }));
    const [op] = sync.operaciones();
    expect([op.tipo, op.estado, (op.datos as { monto_recibido: number }).monto_recibido]).toEqual(['venta', 'registrada', 150]);
  });

  it('con conexión, mis reservas muestra las del servidor más las que faltan enviar', async () => {
    await pedir('POST', '/api/v1/reservas', { sucursal_id: 1, detalles: [{ variante_id: 100, cantidad: 1 }] });
    sync.enLinea.set(true);

    const lista = pedir<{ id: number }[]>('GET', '/api/v1/reservas');
    backend.expectOne('/api/v1/reservas').flush([{ id: 41, estado: 'confirmada', detalles: [] }]);

    const ids = (await lista).map((r) => r.id);
    expect(ids).toHaveLength(2);
    expect(ids[0]).toBeLessThan(0);
    expect(ids[1]).toBe(41);
  });
});
