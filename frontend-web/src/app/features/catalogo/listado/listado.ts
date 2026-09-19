import { CommonModule } from '@angular/common';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterModule } from '@angular/router';
import {
  Categoria,
  Color,
  DisponibilidadSucursal,
  Prenda,
  Talla,
  VariantePrenda,
} from '../../../core/models/user.model';
import { AuthService } from '../../../core/services/auth.service';
import { BusinessService } from '../../../core/services/business.service';
import { CartService } from '../../../core/services/cart.service';
import { VestidorVirtual } from '../vestidor-virtual/vestidor-virtual';

@Component({
  selector: 'app-listado',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterModule, VestidorVirtual],
  templateUrl: './listado.html',
  styles: [`
    .hero-banner {
      background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 60%, #312e81 100%);
      border-radius: 20px;
      padding: 3.5rem 2.5rem;
      color: #ffffff;
      margin-bottom: 2.5rem;
      display: flex;
      justify-content: space-between;
      align-items: center;
      box-shadow: 0 15px 30px -10px rgba(15, 23, 42, 0.2);
      position: relative;
      overflow: hidden;

      &::after {
        content: '';
        position: absolute;
        width: 300px;
        height: 300px;
        border-radius: 50%;
        background: radial-gradient(circle, rgba(236, 72, 153, 0.25) 0%, transparent 70%);
        top: -60px;
        right: -60px;
      }
    }

    .hero-content {
      max-width: 650px;
      z-index: 1;

      .hero-pill {
        display: inline-flex;
        align-items: center;
        gap: 0.5rem;
        background: rgba(255, 255, 255, 0.12);
        backdrop-filter: blur(8px);
        padding: 0.35rem 0.85rem;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 1rem;
        border: 1px solid rgba(255, 255, 255, 0.15);
      }

      h1 {
        color: #ffffff;
        font-size: 2.5rem;
        line-height: 1.2;
        margin-bottom: 0.75rem;
      }

      p {
        color: #cbd5e1;
        font-size: 1rem;
        line-height: 1.6;
      }
    }

    .filters-section {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 1.5rem;
      margin-bottom: 2rem;
      flex-wrap: wrap;
    }

    .search-input-wrapper {
      position: relative;
      min-width: 280px;
      flex: 1;
      max-width: 400px;

      input {
        width: 100%;
        padding: 0.65rem 1rem 0.65rem 2.5rem;
        border-radius: 9999px;
        border: 1px solid #e2e8f0;
        background: #ffffff;
        font-size: 0.9rem;
        outline: none;
        transition: all 0.2s;

        &:focus {
          border-color: #4f46e5;
          box-shadow: 0 0 0 4px rgba(79, 70, 229, 0.15);
        }
      }

      svg {
        position: absolute;
        left: 0.85rem;
        top: 50%;
        transform: translateY(-50%);
        color: #94a3b8;
      }
    }

    .category-chips {
      display: flex;
      gap: 0.5rem;
      overflow-x: auto;
      padding-bottom: 4px;
    }

    .chip-btn {
      padding: 0.45rem 1rem;
      border-radius: 9999px;
      font-size: 0.85rem;
      font-weight: 600;
      border: 1px solid #e2e8f0;
      background: #ffffff;
      color: #475569;
      cursor: pointer;
      transition: all 0.2s;
      white-space: nowrap;

      &:hover {
        background: #f1f5f9;
        border-color: #cbd5e1;
      }

      &.active {
        background: #4f46e5;
        color: #ffffff;
        border-color: #4f46e5;
        box-shadow: 0 4px 10px rgba(79, 70, 229, 0.25);
      }
    }

    /* Product Cards */
    .product-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
      gap: 1.75rem;
    }

    .product-card {
      background: #ffffff;
      border: 1px solid #e2e8f0;
      border-radius: 16px;
      overflow: hidden;
      display: flex;
      flex-direction: column;
      cursor: pointer;
      transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);

      &:hover {
        transform: translateY(-6px);
        box-shadow: 0 16px 30px -10px rgba(0, 0, 0, 0.1);
        border-color: #cbd5e1;
      }
    }

    .product-banner {
      height: 220px;
      background: linear-gradient(135deg, #f8fafc 0%, #eef2ff 100%);
      display: flex;
      align-items: center;
      justify-content: center;
      position: relative;
      border-bottom: 1px solid #f1f5f9;

      .icon-box {
        font-size: 3.5rem;
        filter: drop-shadow(0 4px 8px rgba(0,0,0,0.05));
      }

      .product-photo {
        width: 100%;
        height: 100%;
        object-fit: cover;
      }

      .ar-badge {
        position: absolute;
        top: 14px;
        right: 14px;
        background: rgba(16, 185, 129, 0.95);
        color: #ffffff;
        padding: 0.3rem 0.65rem;
        border-radius: 9999px;
        font-size: 0.72rem;
        font-weight: 700;
        display: flex;
        align-items: center;
        gap: 0.35rem;
        box-shadow: 0 2px 8px rgba(16, 185, 129, 0.3);
      }
    }

    .product-info {
      padding: 1.5rem;
      display: flex;
      flex-direction: column;
      flex: 1;

      .brand-category {
        font-size: 0.75rem;
        font-weight: 700;
        text-transform: uppercase;
        color: #4f46e5;
        letter-spacing: 0.04em;
        margin-bottom: 0.35rem;
      }

      .product-title {
        font-size: 1.15rem;
        font-weight: 700;
        color: #0f172a;
        margin-bottom: 0.5rem;
      }

      .product-desc {
        font-size: 0.85rem;
        color: #64748b;
        line-height: 1.45;
        margin-bottom: 1.25rem;
        flex: 1;
      }

      .product-footer {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding-top: 1rem;
        border-top: 1px solid #f1f5f9;

        .price-label {
          font-size: 0.75rem;
          color: #94a3b8;
          display: block;
        }

        .price-val {
          font-size: 1.35rem;
          font-weight: 800;
          color: #0f172a;
        }
      }
    }
  `],
})
export class Listado implements OnInit {
  private readonly business = inject(BusinessService);
  private readonly auth = inject(AuthService);
  readonly cart = inject(CartService);

  isLoggedIn = this.auth.isLoggedIn;

  prendas = signal<Prenda[]>([]);
  categorias = signal<Categoria[]>([]);
  tallas = signal<Talla[]>([]);
  colores = signal<Color[]>([]);
  categoriaSeleccionada = signal<number | null>(null);
  tallaSeleccionada = signal<number | null>(null);
  colorSeleccionado = signal<number | null>(null);
  busqueda = signal('');
  isLoading = signal(true);

  prendaModal = signal<Prenda | null>(null);
  modalVariantes = signal<VariantePrenda[]>([]);
  modalVarianteId = signal<number | null>(null);
  modalCantidad = signal(1);
  modalAgregadoExito = signal(false);

  // --- CU-15: Flujo de reserva ---
  reservaPrenda = signal<Prenda | null>(null);
  reservaVariantes = signal<VariantePrenda[]>([]);
  reservaVarianteId = signal<number | null>(null);
  reservaDisponibilidad = signal<DisponibilidadSucursal[]>([]);
  reservaSucursalId = signal<number | null>(null);
  reservaCantidad = signal(1);
  reservaHorario = signal('');
  reservaEnviando = signal(false);
  reservaError = signal<string | null>(null);
  reservaExito = signal(false);

  // --- CU-28: Recomendaciones de productos (IA) ---
  recomendaciones = signal<Prenda[]>([]);

  // --- CU-14: Vestidor virtual ---
  vestidorPrenda = signal<Prenda | null>(null);

  prendasFiltradas = computed(() => {
    let list = this.prendas();
    const query = this.busqueda().toLowerCase().trim();
    if (query) {
      list = list.filter(
        (p) =>
          p.nombre.toLowerCase().includes(query) ||
          (p.descripcion && p.descripcion.toLowerCase().includes(query))
      );
    }
    return list;
  });

  sucursalSeleccionadaInfo = computed(
    () => this.reservaDisponibilidad().find((d) => d.sucursal_id === this.reservaSucursalId()) ?? null
  );

  ngOnInit(): void {
    this.cargarCategorias();
    this.cargarPrendas();
    this.business.getTallas().subscribe((data) => this.tallas.set(data));
    this.business.getColores().subscribe((data) => this.colores.set(data));
    if (this.isLoggedIn()) {
      // CU-28: widget silencioso; si la IA no está disponible o falla, simplemente no se muestra nada.
      this.business.getRecomendaciones().subscribe({
        next: (data) => this.recomendaciones.set(data.prendas || []),
        error: () => this.recomendaciones.set([]),
      });
    }
  }

  cargarCategorias(): void {
    this.business.getCategorias().subscribe((data) => this.categorias.set(data));
  }

  cargarPrendas(): void {
    this.isLoading.set(true);
    this.business
      .getPrendas({
        categoriaId: this.categoriaSeleccionada() ?? undefined,
        tallaId: this.tallaSeleccionada() ?? undefined,
        colorId: this.colorSeleccionado() ?? undefined,
      })
      .subscribe({
        next: (data) => {
          this.prendas.set(data);
          this.isLoading.set(false);
        },
        error: () => this.isLoading.set(false),
      });
  }

  filtrarPorCategoria(id: number | null): void {
    this.categoriaSeleccionada.set(id);
    this.cargarPrendas();
  }

  filtrarPorTalla(id: number | null): void {
    this.tallaSeleccionada.set(this.tallaSeleccionada() === id ? null : id);
    this.cargarPrendas();
  }

  filtrarPorColor(id: number | null): void {
    this.colorSeleccionado.set(this.colorSeleccionado() === id ? null : id);
    this.cargarPrendas();
  }

  verPrenda(p: Prenda): void {
    this.prendaModal.set(p);
    this.modalVariantes.set([]);
    this.modalVarianteId.set(null);
    this.modalCantidad.set(1);
    this.modalAgregadoExito.set(false);
    this.business.getVariantes(p.id).subscribe((data) => {
      const active = data.filter((v) => v.estado);
      this.modalVariantes.set(active);
      if (active.length > 0) {
        this.modalVarianteId.set(active[0].id);
      }
    });
  }

  agregarAlCarritoDesdeModal(): void {
    const prenda = this.prendaModal();
    const vId = this.modalVarianteId();
    if (!prenda || !vId) return;

    const variante = this.modalVariantes().find((v) => v.id === vId);
    if (!variante) return;

    this.cart.agregar({
      variante_id: variante.id,
      prenda_id: prenda.id,
      nombre: prenda.nombre,
      talla: variante.talla_nombre || 'Única',
      color: variante.color_nombre || 'Estándar',
      precio: Number(prenda.precio_base),
      cantidad: this.modalCantidad() || 1,
      imagen_url: prenda.imagen_url,
    });

    this.modalAgregadoExito.set(true);
    setTimeout(() => this.modalAgregadoExito.set(false), 3000);
  }

  cerrarModalPrenda(): void {
    this.prendaModal.set(null);
  }

  // --- CU-15: Reservar prendas ---
  abrirReserva(p: Prenda): void {
    this.prendaModal.set(null);
    this.reservaPrenda.set(p);
    this.reservaVariantes.set([]);
    this.reservaVarianteId.set(null);
    this.reservaDisponibilidad.set([]);
    this.reservaSucursalId.set(null);
    this.reservaCantidad.set(1);
    this.reservaHorario.set('');
    this.reservaError.set(null);
    this.reservaExito.set(false);

    this.business.getVariantes(p.id).subscribe((data) => this.reservaVariantes.set(data.filter((v) => v.estado)));
  }

  seleccionarVariante(varianteId: number): void {
    this.reservaVarianteId.set(varianteId);
    this.reservaSucursalId.set(null);
    this.reservaDisponibilidad.set([]);
    this.business.getDisponibilidad(varianteId).subscribe((data) => this.reservaDisponibilidad.set(data));
  }

  seleccionarSucursal(sucursalId: number): void {
    this.reservaSucursalId.set(sucursalId);
    this.reservaCantidad.set(1);
  }

  confirmarReserva(): void {
    const varianteId = this.reservaVarianteId();
    const sucursalId = this.reservaSucursalId();
    if (!varianteId || !sucursalId) return;

    this.reservaEnviando.set(true);
    this.reservaError.set(null);

    this.business
      .crearReserva({
        sucursal_id: sucursalId,
        horario_atencion: this.reservaHorario() || undefined,
        detalles: [{ variante_id: varianteId, cantidad: this.reservaCantidad() }],
      })
      .subscribe({
        next: () => {
          this.reservaEnviando.set(false);
          this.reservaExito.set(true);
        },
        error: (err) => {
          this.reservaEnviando.set(false);
          this.reservaError.set(err?.error?.detail ?? 'No se pudo crear la reserva.');
        },
      });
  }

  cerrarModalReserva(): void {
    this.reservaPrenda.set(null);
  }

  // --- CU-14: Vestidor virtual ---
  abrirVestidor(p: Prenda): void {
    this.vestidorPrenda.set(p);
  }

  cerrarVestidor(): void {
    this.vestidorPrenda.set(null);
  }
}
