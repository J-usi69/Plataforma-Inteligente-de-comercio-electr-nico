import 'fake-indexeddb/auto';
import { HttpErrorResponse, provideHttpClient } from '@angular/common/http';
import { HttpTestingController, TestRequest, provideHttpClientTesting } from '@angular/common/http/testing';
import { computed, signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { AuthService } from '../services/auth.service';
import { TiendaService } from '../services/tienda.service';
import { AlmacenLocal } from './almacen-local';
import { DatosVenta, Paquete, ResultadoOperacion } from './modelos';
import { TimeoutError } from 'rxjs';
import { SincronizacionService, sinConexion } from './sincronizacion.service';

const OPERACIONES = '/api/v1/sync/operaciones';
const PAQUETE: Paquete = {
  generado_en: new Date().toISOString(),
  vigencia_horas: 12,
  tienda: 'moda-andina',
  dias_para_cambio: 7,
  sucursales: [{ id: 1, nombre: 'Centro', direccion: 'Calle 1', ciudad: 'La Paz' }],
  categorias: [{ id: 1, nombre: 'Poleras' }],
  tallas: [{ id: 1, nombre: 'M' }],
  colores: [{ id: 1, nombre: 'Negro', hex: '#111111' }],
  prendas: [{ id: 10, nombre: 'Polera', descripcion: null, categoria_id: 1, precio_base: 100, imagen_url: null }],
  variantes: [{ id: 100, prenda_id: 10, talla_id: 1, color_id: 1, codigo_barras: 'P-M', imagen_url: null }],
  inventario: [{ variante_id: 100, sucursal_id: 1, stock_disponible: 5 }],
  clientes: [],
  ventas: [],
};
const venta = (cantidad: number): DatosVenta => ({
  cliente_id: null,
  detalles: [{ variante_id: 100, cantidad, precio_unitario: 100 }],
  total: 100 * cantidad,
  metodo_pago: 'efectivo',
  monto_recibido: null,
});
const respuesta = (id: string, estado: ResultadoOperacion['estado'], extra: Partial<ResultadoOperacion> = {}): ResultadoOperacion => ({
  id, tipo: 'venta', estado, codigo: null, mensaje: null, referencia_tipo: null, referencia_id: null, duplicada: false, procesada_en: null, ...extra,
});

let base = 0;

describe('Sincronización de la operación sin conexión', () => {
  let sync: SincronizacionService;
  let backend: HttpTestingController;
  let slug: string;

  /** Espera a que el servicio haga el pedido (antes lee y escribe IndexedDB, que es asíncrono). */
  const pedido = (url: string): Promise<TestRequest> => vi.waitFor(() => backend.expectOne((r) => r.url === url));

  beforeEach(async () => {
    slug = `prueba-${++base}`; // una base IndexedDB nueva por test
    const usuario = signal({ id: 7, correo: 'cajero@prueba.com', roles: ['Cajero'], permisos: [], estado: true });
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: AuthService, useValue: { currentUser: usuario, isLoggedIn: computed(() => !!usuario()) } },
        { provide: TiendaService, useValue: { slug, tiene: () => true } },
      ],
    });
    sync = TestBed.inject(SincronizacionService);
    backend = TestBed.inject(HttpTestingController);
    const descarga = sync.descargarPaquete();
    backend.expectOne('/api/v1/sync/paquete').flush(PAQUETE);
    await descarga;
    sync.enLinea.set(false);
  });

  afterEach(() => backend.verify());

  it('sin conexión la venta queda guardada, descuenta el stock local y sobrevive a cerrar la app', async () => {
    const op = await sync.registrar('venta', 1, venta(2));

    expect(op.estado).toBe('registrada');
    expect(sync.pendientes()).toBe(1);
    backend.expectNone(OPERACIONES); // sin conexión no se intenta enviar
    // Otra instancia sobre la misma base = la app vuelta a abrir
    const reabierta = new AlmacenLocal(`fashionstore-offline:${slug}`);
    expect((await reabierta.operaciones()).map((o) => o.id)).toEqual([op.id]);
    expect((await reabierta.leerPaquete())!.inventario[0].stock_disponible).toBe(3);
  });

  it('al volver la conexión envía en orden, guarda la respuesta de cada una y no borra ninguna', async () => {
    const primera = await sync.registrar('venta', 1, venta(1));
    const segunda = await sync.registrar('venta', 1, venta(9));
    sync.enLinea.set(true);

    const envio = sync.sincronizar();
    const lote = await pedido(OPERACIONES);
    expect(lote.request.body.operaciones.map((o: { id: string }) => o.id)).toEqual([primera.id, segunda.id]);
    expect(lote.request.body.operaciones[0]).not.toHaveProperty('estado'); // solo viaja lo que pide el contrato
    lote.flush({
      recibido_en: new Date().toISOString(),
      resultados: [
        respuesta(primera.id, 'confirmada', { referencia_tipo: 'venta', referencia_id: 55 }),
        respuesta(segunda.id, 'conflicto', { codigo: 'sin_stock', mensaje: 'El inventario del sistema no alcanza' }),
      ],
    });
    (await pedido('/api/v1/sync/estado')).flush({ resultados: [respuesta(segunda.id, 'conflicto')], desconocidas: [] });
    (await pedido('/api/v1/sync/paquete')).flush(PAQUETE); // con algo confirmado se renueva el stock
    await envio;

    expect(sync.operaciones().map((o) => [o.estado, o.resultado?.referencia_id ?? o.resultado?.codigo])).toEqual([
      ['confirmada', 55],
      ['conflicto', 'sin_stock'],
    ]);
    expect(sync.pendientes()).toBe(0);
  });

  it('si el servidor no responde, las operaciones quedan y se reenvían con el mismo id', async () => {
    const op = await sync.registrar('venta', 1, venta(1));
    sync.enLinea.set(true);

    const primerIntento = sync.sincronizar();
    (await pedido(OPERACIONES)).error(new ProgressEvent('error'), { status: 0 });
    await primerIntento;
    expect(sync.operaciones()[0].estado).toBe('enviada');
    expect(sync.ultimoError()).toContain('conexión');

    const segundoIntento = sync.sincronizar();
    const reintento = await pedido(OPERACIONES);
    expect(reintento.request.body.operaciones[0].id).toBe(op.id);
    reintento.flush({ recibido_en: new Date().toISOString(), resultados: [respuesta(op.id, 'error')] }); // falla momentánea
    await segundoIntento;

    const [guardada] = sync.operaciones();
    expect([guardada.estado, guardada.intentos]).toEqual(['enviada', 2]);
  });

  it('sin red, el Service Worker responde 504 y el proxy 502/503: cuenta como sin conexión', () => {
    for (const status of [0, 502, 503, 504]) {
      expect(sinConexion(new HttpErrorResponse({ status }))).toBe(true);
    }
    expect(sinConexion(new HttpErrorResponse({ status: 402 }))).toBe(false); // el servidor respondió
    expect(sinConexion(new TimeoutError())).toBe(true);
  });

  it('cuando el encargado resuelve un conflicto, el dispositivo se entera', async () => {
    const op = await sync.registrar('venta', 1, venta(9));
    sync.enLinea.set(true);
    const envio = sync.sincronizar();
    (await pedido(OPERACIONES)).flush({ recibido_en: new Date().toISOString(), resultados: [respuesta(op.id, 'conflicto')] });
    (await pedido('/api/v1/sync/estado')).flush({ resultados: [respuesta(op.id, 'conflicto')], desconocidas: [] });
    await envio;

    const consulta = sync.sincronizar();
    (await pedido('/api/v1/sync/estado')).flush({
      resultados: [respuesta(op.id, 'confirmada', { referencia_tipo: 'venta', referencia_id: 77 })],
      desconocidas: [],
    });
    await consulta;

    expect(sync.operaciones()[0].estado).toBe('confirmada');
    expect(sync.operaciones()[0].resultado?.referencia_id).toBe(77);
  });
});
