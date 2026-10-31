import { DatePipe } from '@angular/common';
import { Component, computed, inject, input, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { DatosCambio, DatosVenta, LineaConPrecio, OperacionLocal } from '../../../core/offline/modelos';
import { dentroDelPlazo, diferenciaDeCambio, formatoBs, vencimientoDelCambio } from '../../../core/offline/reglas';
import { SincronizacionService } from '../../../core/offline/sincronizacion.service';

interface LineaEntrega extends LineaConPrecio {
  nombre: string;
}

/** Venta que se puede cambiar: ya sincronizada (viene en el paquete) o hecha en este dispositivo. */
interface VentaCambiable {
  clave: string;
  venta_id: number | null;
  venta_operacion_id: string | null;
  fecha: string;
  etiqueta: string;
  lineas: (LineaConPrecio & { disponible: number })[];
}

/** Cambio de prendas en caja (dentro del plazo de la tienda, por igual o mayor valor). Con o sin
 * conexión es lo mismo: entra a la cola y se confirma en el servidor, que valida las reglas. */
@Component({
  selector: 'app-cambio-prenda',
  standalone: true,
  imports: [DatePipe, FormsModule],
  templateUrl: './cambio-prenda.html',
})
export class CambioPrenda {
  readonly sync = inject(SincronizacionService);
  readonly sucursalId = input.required<number>();
  readonly formatoBs = formatoBs;

  readonly ventaClave = signal<string | null>(null);
  readonly devolver = signal<Record<number, number>>({});
  readonly entrega = signal<LineaEntrega[]>([]);
  readonly aviso = signal<{ ok: boolean; texto: string } | null>(null);
  readonly guardando = signal(false);
  entregaVarianteId: number | null = null;
  motivo = '';

  private readonly mapas = computed(() => {
    const d = this.sync.datos();
    const porId = <T extends { id: number }>(filas: T[] = []) => new Map(filas.map((f) => [f.id, f]));
    return {
      prendas: porId(d?.prendas),
      variantes: porId(d?.variantes),
      tallas: porId(d?.tallas),
      colores: porId(d?.colores),
      clientes: porId(d?.clientes),
      stock: new Map((d?.inventario ?? []).map((i) => [`${i.variante_id}:${i.sucursal_id}`, i.stock_disponible])),
    };
  });

  readonly ventas = computed<VentaCambiable[]>(() => {
    const d = this.sync.datos();
    if (!d) return [];
    const ops = this.sync.operaciones();
    const enServidor = new Set(d.ventas.map((v) => v.id));
    const sincronizadas = d.ventas.map((v) => ({
      clave: `v${v.id}`,
      venta_id: v.id,
      venta_operacion_id: null,
      fecha: v.fecha_venta,
      etiqueta: `Venta #${v.id} · ${this.mapas().clientes.get(v.cliente_id ?? -1)?.correo ?? 'cliente ocasional'} · ${formatoBs(v.total)}`,
      lineas: v.detalles.map((l) => ({ ...l, disponible: l.cantidad - l.devuelto - this.devueltoSinSincronizar(ops, v.id, null, l.variante_id) })),
    }));
    const deEsteDispositivo = ops
      .filter((op) => op.tipo === 'venta' && op.estado !== 'rechazada' && !enServidor.has(op.resultado?.referencia_id ?? -1))
      .map((op) => {
        const venta = op.datos as DatosVenta;
        return {
          clave: `o${op.id}`,
          venta_id: null,
          venta_operacion_id: op.id,
          fecha: op.registrada_en,
          etiqueta: `Venta sin sincronizar · ${formatoBs(venta.total)}`,
          lineas: venta.detalles.map((l) => ({ ...l, disponible: l.cantidad - this.devueltoSinSincronizar(ops, null, op.id, l.variante_id) })),
        };
      });
    return [...deEsteDispositivo, ...sincronizadas].sort((a, b) => b.fecha.localeCompare(a.fecha));
  });

  readonly venta = computed(() => this.ventas().find((v) => v.clave === this.ventaClave()) ?? null);
  readonly devueltas = computed<LineaConPrecio[]>(() =>
    (this.venta()?.lineas ?? [])
      .filter((l) => (this.devolver()[l.variante_id] ?? 0) > 0)
      .map((l) => ({ variante_id: l.variante_id, cantidad: this.devolver()[l.variante_id], precio_unitario: l.precio_unitario })),
  );
  readonly diferencia = computed(() => diferenciaDeCambio(this.devueltas(), this.entrega()));
  readonly enPlazo = computed(() => {
    const venta = this.venta();
    const info = this.sync.info();
    return !!venta && !!info && dentroDelPlazo(venta.fecha, info.dias_para_cambio);
  });
  readonly opcionesDeEntrega = computed(() =>
    (this.sync.datos()?.variantes ?? []).map((v) => ({ id: v.id, texto: `${this.nombreDe(v.id)} · stock ${this.stock(v.id)}` })),
  );

  nombreDe(varianteId: number): string {
    const { variantes, prendas, tallas, colores } = this.mapas();
    const v = variantes.get(varianteId);
    if (!v) return `Variante #${varianteId}`;
    return `${prendas.get(v.prenda_id)?.nombre ?? 'Prenda'} — ${tallas.get(v.talla_id)?.nombre ?? ''} / ${colores.get(v.color_id)?.nombre ?? ''}`;
  }

  stock(varianteId: number): number {
    return this.mapas().stock.get(`${varianteId}:${this.sucursalId()}`) ?? 0;
  }

  vencimiento(fecha: string): Date {
    return vencimientoDelCambio(fecha, this.sync.info()?.dias_para_cambio ?? 0);
  }

  elegirVenta(clave: string | null): void {
    this.ventaClave.set(clave);
    this.devolver.set({});
    this.entrega.set([]);
    this.aviso.set(null);
  }

  fijarDevolucion(varianteId: number, cantidad: number, disponible: number): void {
    const valor = Math.max(0, Math.min(disponible, Math.floor(Number(cantidad) || 0)));
    this.devolver.update((actual) => ({ ...actual, [varianteId]: valor }));
  }

  agregarEntrega(): void {
    const v = this.mapas().variantes.get(Number(this.entregaVarianteId));
    if (!v) return;
    const precio = this.mapas().prendas.get(v.prenda_id)?.precio_base ?? 0;
    this.entrega.update((lineas) =>
      lineas.some((l) => l.variante_id === v.id)
        ? lineas.map((l) => (l.variante_id === v.id ? { ...l, cantidad: l.cantidad + 1 } : l))
        : [...lineas, { variante_id: v.id, cantidad: 1, precio_unitario: precio, nombre: this.nombreDe(v.id) }],
    );
  }

  quitarEntrega(varianteId: number): void {
    this.entrega.update((lineas) => lineas.filter((l) => l.variante_id !== varianteId));
  }

  async registrar(): Promise<void> {
    const venta = this.venta();
    if (!venta || !this.devueltas().length || !this.entrega().length) {
      this.aviso.set({ ok: false, texto: 'Elegí qué prendas devuelve el cliente y cuáles se lleva.' });
      return;
    }
    if (!this.enPlazo()) {
      this.aviso.set({ ok: false, texto: 'La venta ya está fuera del plazo de cambio.' });
      return;
    }
    if (this.diferencia() < 0) {
      this.aviso.set({ ok: false, texto: 'El cambio tiene que ser por prendas de igual o mayor valor.' });
      return;
    }
    const datos: DatosCambio = {
      venta_id: venta.venta_id,
      venta_operacion_id: venta.venta_operacion_id,
      devuelve: this.devueltas().map(({ variante_id, cantidad }) => ({ variante_id, cantidad })),
      entrega: this.entrega().map(({ variante_id, cantidad, precio_unitario }) => ({ variante_id, cantidad, precio_unitario })),
      diferencia: this.diferencia(),
      motivo: this.motivo.trim() || null,
      metodo_pago: 'efectivo',
    };
    this.guardando.set(true);
    try {
      await this.sync.registrar('cambio', this.sucursalId(), datos);
      this.aviso.set({
        ok: true,
        texto: this.sync.enLinea()
          ? `Cambio registrado. Cobrá ${formatoBs(datos.diferencia)} de diferencia; se está confirmando en el servidor.`
          : `Cambio registrado. Cobrá ${formatoBs(datos.diferencia)} de diferencia; se enviará solo al volver la conexión.`,
      });
      this.ventaClave.set(null);
      this.devolver.set({});
      this.entrega.set([]);
      this.motivo = '';
    } catch (err) {
      this.aviso.set({ ok: false, texto: err instanceof Error ? err.message : 'No se pudo registrar el cambio.' });
    } finally {
      this.guardando.set(false);
    }
  }

  /** Devuelto en cambios de este dispositivo que el servidor todavía no reflejó en el paquete. */
  private devueltoSinSincronizar(ops: OperacionLocal[], ventaId: number | null, ventaOperacionId: string | null, varianteId: number): number {
    return ops
      .filter((op) => op.tipo === 'cambio' && ['registrada', 'enviada', 'conflicto'].includes(op.estado))
      .map((op) => op.datos as DatosCambio)
      .filter((c) => (ventaId !== null && c.venta_id === ventaId) || (ventaOperacionId !== null && c.venta_operacion_id === ventaOperacionId))
      .reduce((suma, c) => suma + c.devuelve.filter((l) => l.variante_id === varianteId).reduce((s, l) => s + l.cantidad, 0), 0);
  }
}
