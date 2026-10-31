// API local: sin conexión, responde desde IndexedDB lo mismo que respondería el backend en las
// rutas que usan el catálogo, las reservas y la caja. Las pantallas no cambian: piden a la API como
// siempre y, si no hay red, contesta este servicio. Las escrituras (una reserva, un cobro en
// efectivo) entran a la cola de SincronizacionService y viajan solas al volver la conexión.
import { HttpErrorResponse, HttpRequest, HttpResponse } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { AuthService } from '../services/auth.service';
import { DatosLocales } from './almacen-local';
import { DatosReserva, DatosVenta, EstadoLocal, LineaConPrecio, OperacionLocal } from './modelos';
import { totalDe } from './reglas';
import { SincronizacionService } from './sincronizacion.service';

type Responder = (coincidencia: RegExpExecArray, req: HttpRequest<unknown>, datos: DatosLocales) => unknown;

/** Venta presencial armada sin conexión: existe solo en el dispositivo hasta que se cobra. */
interface VentaBorrador {
  id: number;
  sucursal_id: number;
  cliente_id: number | null;
  detalles: LineaConPrecio[];
  total: number;
  fecha: string;
  operacion?: OperacionLocal;
}

const PENDIENTES: EstadoLocal[] = ['registrada', 'enviada', 'conflicto'];

@Injectable({ providedIn: 'root' })
export class ApiLocal {
  private readonly sync = inject(SincronizacionService);
  private readonly auth = inject(AuthService);
  private readonly borradores = new Map<number, VentaBorrador>();
  private ultimoBorrador = 0;

  private readonly rutas: [string, RegExp, Responder][] = [
    ['GET', /^\/api\/v1\/prendas$/, (_m, req, d) => this.prendas(req, d)],
    ['GET', /^\/api\/v1\/prendas\/categorias$/, (_m, _r, d) => d.categorias.map((c) => ({ ...c, descripcion: null, estado: true }))],
    ['GET', /^\/api\/v1\/prendas\/(\d+)\/variantes$/, (m, _r, d) => this.variantes(d, Number(m[1]))],
    ['GET', /^\/api\/v1\/prendas\/(\d+)$/, (m, _r, d) => this.prendas(null, d).find((p) => p.id === Number(m[1])) ?? this.noEsta('La prenda')],
    ['GET', /^\/api\/v1\/catalogo-maestro\/tallas$/, (_m, _r, d) => d.tallas],
    ['GET', /^\/api\/v1\/catalogo-maestro\/colores$/, (_m, _r, d) => d.colores],
    ['GET', /^\/api\/v1\/sucursales$/, (_m, _r, d) => this.sucursales(d)],
    ['GET', /^\/api\/v1\/inventario\/disponibilidad\/(\d+)$/, (m, _r, d) => this.disponibilidad(d, Number(m[1]))],
    ['GET', /^\/api\/v1\/reservas$/, () => this.reservasPendientes()],
    ['GET', /^\/api\/v1\/reservas\/sucursal\/\d+$/, () => []], // las reservas de la sucursal viven en el servidor
    ['POST', /^\/api\/v1\/reservas$/, (_m, req, d) => this.reservar(req, d)],
    ['POST', /^\/api\/v1\/ventas\/presencial$/, (_m, req, d) => this.armarVenta(req, d)],
    ['POST', /^\/api\/v1\/ventas\/(-\d+)\/cobrar-caja$/, (m, req, d) => this.cobrarEnEfectivo(Number(m[1]), req, d)],
    ['GET', /^\/api\/v1\/ventas\/comprobante\/(-\d+)$/, (m, _r, d) => this.comprobante(Number(m[1]), d)],
  ];

  private ruta(req: HttpRequest<unknown>): [Responder, RegExpExecArray] | null {
    const camino = new URL(req.url, 'http://local').pathname;
    for (const [metodo, patron, responder] of this.rutas) {
      const coincidencia = metodo === req.method ? patron.exec(camino) : null;
      if (coincidencia) return [responder, coincidencia];
    }
    return null;
  }

  /** La ruta se puede responder sin conexión. */
  atiende(req: HttpRequest<unknown>): boolean {
    return this.ruta(req) !== null;
  }

  /** Una venta armada sin conexión (id negativo) solo existe acá, haya red o no. */
  soloLocal(req: HttpRequest<unknown>): boolean {
    return /\/ventas\/(comprobante\/)?-\d+/.test(req.url);
  }

  esMisReservas(req: HttpRequest<unknown>): boolean {
    return req.method === 'GET' && new URL(req.url, 'http://local').pathname === '/api/v1/reservas';
  }

  async responder(req: HttpRequest<unknown>): Promise<HttpResponse<unknown>> {
    const [responder, coincidencia] = this.ruta(req)!;
    await this.sync.listo();
    const datos = this.sync.datos();
    if (!datos) {
      throw this.error(503, 'No hay conexión y este dispositivo todavía no tiene los datos guardados: conectate una vez para descargarlos.');
    }
    const body = await responder(coincidencia, req, datos);
    return new HttpResponse({ status: req.method === 'POST' ? 201 : 200, body, url: req.url });
  }

  /** "Mis reservas" con conexión: las del servidor más las que todavía no se enviaron. */
  conPendientes(respuesta: HttpResponse<unknown>): HttpResponse<unknown> {
    const pendientes = this.reservasPendientes();
    return pendientes.length ? respuesta.clone({ body: [...pendientes, ...((respuesta.body as unknown[]) ?? [])] }) : respuesta;
  }

  // --- Lecturas -----------------------------------------------------------------
  private prendas(req: HttpRequest<unknown> | null, d: DatosLocales) {
    const filtro = req ? new URL(req.urlWithParams, 'http://local').searchParams : new URLSearchParams();
    const numero = (clave: string) => Number(filtro.get(clave)) || null;
    const [categoria, talla, color] = [numero('categoria_id'), numero('talla_id'), numero('color_id')];
    const buscar = (filtro.get('buscar') ?? '').toLowerCase();
    const categorias = new Map(d.categorias.map((c) => [c.id, c.nombre]));
    return d.prendas
      .filter((p) => !categoria || p.categoria_id === categoria)
      .filter((p) => !buscar || p.nombre.toLowerCase().includes(buscar))
      .filter((p) => (!talla && !color) || d.variantes.some((v) => v.prenda_id === p.id && (!talla || v.talla_id === talla) && (!color || v.color_id === color)))
      .map((p) => ({ ...p, estado: true, categoria_nombre: categorias.get(p.categoria_id) ?? null, coleccion_id: null, proveedor_id: null, modelo_3d_url: null }));
  }

  private variantes(d: DatosLocales, prendaId: number) {
    const tallas = new Map(d.tallas.map((t) => [t.id, t.nombre]));
    const colores = new Map(d.colores.map((c) => [c.id, c.nombre]));
    return d.variantes
      .filter((v) => v.prenda_id === prendaId)
      .map((v) => ({ ...v, estado: true, talla_nombre: tallas.get(v.talla_id) ?? null, color_nombre: colores.get(v.color_id) ?? null }));
  }

  private sucursales(d: DatosLocales) {
    return d.sucursales.map((s) => ({ id: s.id, nombre: s.nombre, direccion: s.direccion, ciudad_id: 0, ciudad_nombre: s.ciudad, estado: true }));
  }

  private disponibilidad(d: DatosLocales, varianteId: number) {
    const sucursales = new Map(d.sucursales.map((s) => [s.id, s]));
    return d.inventario
      .filter((i) => i.variante_id === varianteId && i.stock_disponible > 0 && sucursales.has(i.sucursal_id))
      .map((i) => {
        const s = sucursales.get(i.sucursal_id)!;
        return { sucursal_id: s.id, sucursal_nombre: s.nombre, ciudad_id: 0, ciudad_nombre: s.ciudad ?? '', direccion: s.direccion, stock_disponible: i.stock_disponible };
      });
  }

  /** Las reservas hechas en este dispositivo que el servidor todavía no confirmó. */
  reservasPendientes() {
    const d = this.sync.datos();
    const sucursales = new Map((d?.sucursales ?? []).map((s) => [s.id, s.nombre]));
    return this.sync
      .operaciones()
      .filter((op) => op.tipo === 'reserva' && PENDIENTES.includes(op.estado))
      .reverse()
      .map((op) => {
        const datos = op.datos as DatosReserva;
        const detalles = datos.detalles.map((l, i) => this.detalle(l.variante_id, l.cantidad, i));
        return {
          id: -op.orden,
          usuario_id: op.usuario_id,
          sucursal_id: op.sucursal_id,
          sucursal_nombre: sucursales.get(op.sucursal_id) ?? null,
          fecha_reserva: op.registrada_en,
          horario_atencion: datos.horario_atencion ?? null,
          estado: 'pendiente',
          total_estimado: detalles.reduce((s, l) => s + (l.subtotal ?? 0), 0),
          detalles,
          sincronizacion: op.estado,
        };
      });
  }

  // --- Escrituras: entran a la cola ---------------------------------------------
  private async reservar(req: HttpRequest<unknown>, d: DatosLocales) {
    const cuerpo = req.body as { sucursal_id: number; horario_atencion?: string; detalles: { variante_id: number; cantidad: number }[] };
    this.exigirSucursal(d, cuerpo.sucursal_id);
    for (const l of cuerpo.detalles) {
      const stock = d.inventario.find((i) => i.variante_id === l.variante_id && i.sucursal_id === cuerpo.sucursal_id)?.stock_disponible ?? 0;
      if (stock < l.cantidad) {
        throw this.error(400, `Stock insuficiente para la variante ${l.variante_id} en la sucursal seleccionada (disponible: ${stock}, solicitado: ${l.cantidad})`);
      }
    }
    // Como en el servidor, quien reserva desde el catálogo reserva para sí
    const usuario = this.auth.currentUser()!;
    const datos: DatosReserva = {
      cliente_id: usuario.personal ? usuario.id : null,
      detalles: cuerpo.detalles.map(({ variante_id, cantidad }) => ({ variante_id, cantidad })),
      horario_atencion: cuerpo.horario_atencion ?? null,
    };
    await this.sync.registrar('reserva', cuerpo.sucursal_id, datos);
    return this.reservasPendientes()[0];
  }

  private armarVenta(req: HttpRequest<unknown>, d: DatosLocales) {
    const cuerpo = req.body as {
      sucursal_id?: number;
      reserva_id?: number | null;
      cliente_id?: number | null;
      detalles: { variante_id: number; cantidad: number; precio_unitario?: number }[];
    };
    if (cuerpo.reserva_id) {
      throw this.error(503, 'Cobrar una reserva necesita conexión: sin Internet se cobran ventas de mostrador en efectivo.');
    }
    const sucursalId = cuerpo.sucursal_id ?? this.auth.sucursalId();
    this.exigirSucursal(d, sucursalId);
    const precios = new Map(d.prendas.map((p) => [p.id, p.precio_base]));
    const detalles = cuerpo.detalles.map((l) => {
      const variante = d.variantes.find((v) => v.id === l.variante_id) ?? this.noEsta('La variante');
      return { variante_id: l.variante_id, cantidad: l.cantidad, precio_unitario: l.precio_unitario ?? precios.get(variante.prenda_id) ?? 0 };
    });
    const borrador: VentaBorrador = {
      id: --this.ultimoBorrador,
      sucursal_id: sucursalId,
      cliente_id: cuerpo.cliente_id ?? null,
      detalles,
      total: totalDe(detalles),
      fecha: new Date().toISOString(),
    };
    this.borradores.set(borrador.id, borrador);
    return this.venta(borrador, d);
  }

  private async cobrarEnEfectivo(id: number, req: HttpRequest<unknown>, d: DatosLocales) {
    const borrador = this.borradores.get(id) ?? this.noEsta('La venta');
    const cuerpo = req.body as { metodo_pago: string; monto_recibido?: number };
    if (cuerpo.metodo_pago !== 'efectivo') {
      throw this.error(503, 'Sin conexión solo se puede cobrar en efectivo: tarjeta y QR necesitan Internet.');
    }
    if (!borrador.operacion) {
      const datos: DatosVenta = {
        cliente_id: borrador.cliente_id,
        detalles: borrador.detalles,
        total: borrador.total,
        metodo_pago: 'efectivo',
        monto_recibido: cuerpo.monto_recibido ?? null,
      };
      borrador.operacion = await this.sync.registrar('venta', borrador.sucursal_id, datos);
    }
    return this.venta(borrador, d);
  }

  private comprobante(id: number, d: DatosLocales) {
    const borrador = this.borradores.get(id) ?? this.noEsta('La venta');
    const sucursal = d.sucursales.find((s) => s.id === borrador.sucursal_id);
    const personal = this.auth.currentUser()?.personal;
    const cliente = d.clientes.find((c) => c.id === borrador.cliente_id);
    return {
      numero_comprobante: `PEND-${(borrador.operacion?.id ?? '').slice(0, 8).toUpperCase()}`,
      venta_id: id,
      fecha_emision: borrador.operacion?.registrada_en ?? borrador.fecha,
      tipo_origen: 'PRESENCIAL',
      sucursal_nombre: sucursal?.nombre ?? '',
      sucursal_direccion: sucursal?.direccion ?? '',
      ciudad_nombre: sucursal?.ciudad ?? null,
      cajero_nombre: personal ? `${personal.nombres} ${personal.apellidos}` : null,
      cliente_nombre: cliente?.correo ?? 'Cliente Mostrador',
      cliente_correo: cliente?.correo ?? null,
      metodo_pago: 'EFECTIVO',
      transaccion_id: borrador.operacion ? `OFFLINE-${borrador.operacion.id}` : null,
      estado_venta: 'PENDIENTE DE SINCRONIZAR',
      subtotal: borrador.total,
      total: borrador.total,
      items: borrador.detalles.map((l, i) => {
        const detalle = this.detalle(l.variante_id, l.cantidad, i, l.precio_unitario);
        return {
          descripcion: detalle.prenda_nombre ?? 'Prenda',
          talla: detalle.talla_nombre,
          color: detalle.color_nombre,
          codigo_barras: detalle.codigo_barras,
          cantidad: l.cantidad,
          precio_unitario: l.precio_unitario,
          subtotal: detalle.subtotal,
        };
      }),
    };
  }

  // --- Armado de respuestas -------------------------------------------------------
  private venta(borrador: VentaBorrador, d: DatosLocales) {
    const cobrada = !!borrador.operacion;
    const personal = this.auth.currentUser()?.personal;
    return {
      id: borrador.id,
      usuario_id: borrador.cliente_id,
      cliente_nombre: d.clientes.find((c) => c.id === borrador.cliente_id)?.correo ?? 'Cliente Ocasional',
      personal_id: personal?.id ?? null,
      personal_nombre: personal ? `${personal.nombres} ${personal.apellidos}` : null,
      sucursal_id: borrador.sucursal_id,
      sucursal_nombre: d.sucursales.find((s) => s.id === borrador.sucursal_id)?.nombre ?? null,
      reserva_id: null,
      tipo_origen: 'presencial',
      estado: cobrada ? 'pagada' : 'pendiente',
      total: borrador.total,
      fecha_venta: borrador.fecha,
      detalles: borrador.detalles.map((l, i) => this.detalle(l.variante_id, l.cantidad, i, l.precio_unitario)),
      pagos: cobrada
        ? [{ id: borrador.id, venta_id: borrador.id, metodo_pago: 'efectivo', pasarela: null, estado: 'pendiente de sincronizar', monto: borrador.total, transaccion_id: `OFFLINE-${borrador.operacion!.id}`, fecha_pago: borrador.operacion!.registrada_en }]
        : [],
    };
  }

  private detalle(varianteId: number, cantidad: number, indice: number, precio?: number) {
    const d = this.sync.datos();
    const variante = d?.variantes.find((v) => v.id === varianteId);
    const prenda = d?.prendas.find((p) => p.id === variante?.prenda_id);
    const unitario = precio ?? prenda?.precio_base ?? 0;
    return {
      id: -(indice + 1),
      variante_id: varianteId,
      cantidad,
      precio_unitario: unitario,
      subtotal: Math.round(unitario * cantidad * 100) / 100,
      prenda_id: prenda?.id ?? null,
      prenda_nombre: prenda?.nombre ?? null,
      talla_nombre: d?.tallas.find((t) => t.id === variante?.talla_id)?.nombre ?? null,
      color_nombre: d?.colores.find((c) => c.id === variante?.color_id)?.nombre ?? null,
      codigo_barras: variante?.codigo_barras ?? null,
    };
  }

  private exigirSucursal(d: DatosLocales, sucursalId: number): void {
    if (!d.sucursales.some((s) => s.id === sucursalId)) {
      throw this.error(400, 'La sucursal no está entre las guardadas en este dispositivo.');
    }
  }

  private noEsta(que: string): never {
    throw this.error(404, `${que} no está entre los datos guardados en este dispositivo.`);
  }

  private error(status: number, detail: string): HttpErrorResponse {
    return new HttpErrorResponse({ status, statusText: 'Sin conexión', error: { detail } });
  }
}
