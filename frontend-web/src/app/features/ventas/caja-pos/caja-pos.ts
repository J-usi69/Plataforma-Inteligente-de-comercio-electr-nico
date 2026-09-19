import { CommonModule } from '@angular/common';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import {
  ComprobanteVenta,
  Prenda,
  Reserva,
  Sucursal,
  VariantePrenda,
  Venta,
} from '../../../core/models/user.model';
import { AuthService } from '../../../core/services/auth.service';
import { BusinessService } from '../../../core/services/business.service';
import { descargarComprobantePdf } from '../../../core/utils/comprobante-pdf';

interface VentaItemFila {
  variante_id: number;
  prenda_nombre: string;
  talla_nombre?: string;
  color_nombre?: string;
  precio_unitario: number;
  cantidad: number;
}

@Component({
  selector: 'app-caja-pos',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './caja-pos.html',
  styles: [`
    .caja-hero {
      background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
      border-radius: 16px;
      padding: 2rem 2.5rem;
      color: #ffffff;
      margin-bottom: 2rem;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }

    .pos-layout {
      display: grid;
      grid-template-columns: 1.1fr 0.9fr;
      gap: 1.5rem;

      @media (max-width: 992px) {
        grid-template-columns: 1fr;
      }
    }

    .pos-card {
      background: #ffffff;
      border: 1px solid #e2e8f0;
      border-radius: 14px;
      padding: 1.5rem;
      box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
    }

    .reserva-pill {
      background: #f8fafc;
      border: 1px solid #cbd5e1;
      padding: 0.85rem;
      border-radius: 10px;
      margin-bottom: 0.75rem;
      cursor: pointer;
      display: flex;
      justify-content: space-between;
      align-items: center;
      transition: all 0.2s;

      &:hover {
        background: #f1f5f9;
        border-color: #4f46e5;
      }
    }

    .total-box {
      background: #0f172a;
      color: #ffffff;
      padding: 1.25rem;
      border-radius: 12px;
      margin: 1.5rem 0;
      display: flex;
      justify-content: space-between;
      align-items: center;

      .total-amount {
        font-size: 1.75rem;
        font-weight: 800;
        color: #10b981;
      }
    }

    .ticket-view {
      font-family: 'Courier New', Courier, monospace;
      background: #ffffff;
      border: 1px dashed #94a3b8;
      padding: 1.5rem;
      border-radius: 8px;
      max-width: 420px;
      margin: 0 auto;
      color: #0f172a;
    }
  `],
})
export class CajaPos implements OnInit {
  private readonly business = inject(BusinessService);
  readonly authService = inject(AuthService);

  sucursales = signal<Sucursal[]>([]);
  sucursalId = signal<number>(1);
  reservasAtendidas = signal<Reserva[]>([]);
  reservaSeleccionadaId = signal<number | null>(null);

  // Ítems de la venta actual
  items = signal<VentaItemFila[]>([]);
  prendas = signal<Prenda[]>([]);
  variantesDisponibles = signal<VariantePrenda[]>([]);
  prendaSeleccionadaId: number | null = null;
  varianteSeleccionadaId: number | null = null;

  // Estados de cobro
  isLoading = signal(false);
  ventaCreada = signal<Venta | null>(null);
  showModalCobro = signal(false);
  metodoPago = 'efectivo';
  montoRecibido: number = 0;
  comprobanteEmitido = signal<ComprobanteVenta | null>(null);

  totalVenta = computed(() =>
    this.items().reduce((sum, item) => sum + item.precio_unitario * item.cantidad, 0)
  );

  cambioDevolver = computed(() => {
    if (this.metodoPago !== 'efectivo') return 0;
    return Math.max(0, this.montoRecibido - this.totalVenta());
  });

  ngOnInit(): void {
    const sucursalId = this.authService.sucursalId() || 1;
    this.sucursalId.set(sucursalId);

    this.business.getSucursales().subscribe((data) => this.sucursales.set(data));
    this.business.getPrendas().subscribe((data) => this.prendas.set(data));
    this.cargarReservasAtendidas();
  }

  cargarReservasAtendidas(): void {
    this.business.getReservasSucursal(this.sucursalId(), 'atendida').subscribe({
      next: (data) => this.reservasAtendidas.set(data),
      error: () => {},
    });
  }

  cambiarSucursal(id: number): void {
    this.sucursalId.set(id);
    this.items.set([]);
    this.reservaSeleccionadaId.set(null);
    this.cargarReservasAtendidas();
  }

  cargarReservaEnVenta(r: Reserva): void {
    this.reservaSeleccionadaId.set(r.id);
    const nuevasFilas: VentaItemFila[] = r.detalles.map((d) => ({
      variante_id: d.variante_id,
      prenda_nombre: d.prenda_nombre || 'Prenda de Reserva',
      talla_nombre: d.talla_nombre || undefined,
      color_nombre: d.color_nombre || undefined,
      precio_unitario: d.precio_unitario || 150.0,
      cantidad: d.cantidad,
    }));
    this.items.set(nuevasFilas);
  }

  onSeleccionarPrenda(prendaId: number): void {
    this.prendaSeleccionadaId = prendaId;
    this.business.getVariantes(prendaId).subscribe((vars) => {
      this.variantesDisponibles.set(vars);
      if (vars.length) {
        this.varianteSeleccionadaId = vars[0].id;
      }
    });
  }

  agregarItemManual(): void {
    if (!this.varianteSeleccionadaId) return;
    const prenda = this.prendas().find((p) => p.id === Number(this.prendaSeleccionadaId));
    const variante = this.variantesDisponibles().find((v) => v.id === Number(this.varianteSeleccionadaId));
    if (!prenda || !variante) return;

    this.items.update((actuales) => {
      const idx = actuales.findIndex((i) => i.variante_id === variante.id);
      if (idx > -1) {
        const clon = [...actuales];
        clon[idx].cantidad += 1;
        return clon;
      }
      return [
        ...actuales,
        {
          variante_id: variante.id,
          prenda_nombre: prenda.nombre,
          talla_nombre: variante.talla_nombre || undefined,
          color_nombre: variante.color_nombre || undefined,
          precio_unitario: prenda.precio_base,
          cantidad: 1,
        },
      ];
    });
  }

  quitarItem(varianteId: number): void {
    this.items.update((lista) => lista.filter((i) => i.variante_id !== varianteId));
  }

  limpiarVenta(): void {
    this.items.set([]);
    this.reservaSeleccionadaId.set(null);
    this.ventaCreada.set(null);
  }

  // Registrar Venta y abrir cobro
  iniciarCobro(): void {
    if (!this.items().length) return;
    this.isLoading.set(true);

    const payload = {
      sucursal_id: this.sucursalId(),
      reserva_id: this.reservaSeleccionadaId(),
      detalles: this.items().map((i) => ({
        variante_id: i.variante_id,
        cantidad: i.cantidad,
        precio_unitario: i.precio_unitario,
      })),
    };

    this.business.registrarVentaPresencial(payload).subscribe({
      next: (venta) => {
        this.ventaCreada.set(venta);
        this.isLoading.set(false);
        this.montoRecibido = venta.total;
        this.showModalCobro.set(true);
      },
      error: (err) => {
        this.isLoading.set(false);
        alert(err.error?.detail || 'Error al registrar venta presencial');
      },
    });
  }

  // Confirmar pago en caja
  confirmarPagoCaja(): void {
    const venta = this.ventaCreada();
    if (!venta) return;

    this.isLoading.set(true);
    this.business
      .cobrarEnCaja(venta.id, {
        metodo_pago: this.metodoPago,
        monto_recibido: this.metodoPago === 'efectivo' ? this.montoRecibido : venta.total,
      })
      .subscribe({
        next: () => {
          this.showModalCobro.set(false);
          // Obtener y mostrar comprobante de venta
          this.business.getComprobanteVenta(venta.id).subscribe((comp) => {
            this.comprobanteEmitido.set(comp);
            this.isLoading.set(false);
            this.limpiarVenta();
            this.cargarReservasAtendidas();
          });
        },
        error: (err) => {
          this.isLoading.set(false);
          alert(err.error?.detail || 'Error al procesar pago');
        },
      });
  }

  cerrarComprobante(): void {
    this.comprobanteEmitido.set(null);
  }

  imprimirComprobante(): void {
    window.print();
  }

  // CU-23: descarga real del comprobante en PDF (antes solo se podía "Imprimir").
  descargarComprobante(): void {
    const comp = this.comprobanteEmitido();
    if (comp) descargarComprobantePdf(comp);
  }
}

