import { CommonModule } from '@angular/common';
import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Reserva, Sucursal } from '../../../core/models/user.model';
import { AuthService } from '../../../core/services/auth.service';
import { BusinessService } from '../../../core/services/business.service';

@Component({
  selector: 'app-gestionar-reservas',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './gestionar-reservas.html',
  styles: [`
    .encargado-hero {
      background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
      border-radius: 16px;
      padding: 2rem 2.5rem;
      color: #ffffff;
      margin-bottom: 2rem;
      display: flex;
      justify-content: space-between;
      align-items: center;
      box-shadow: 0 10px 25px -5px rgba(15, 23, 42, 0.15);

      h2 { color: #ffffff; font-size: 1.75rem; margin-bottom: 0.35rem; }
      p { color: #94a3b8; font-size: 0.9rem; }
    }

    .sucursal-selector-bar {
      display: flex;
      align-items: center;
      gap: 1rem;
      background: #ffffff;
      padding: 1rem 1.5rem;
      border-radius: 12px;
      border: 1px solid #e2e8f0;
      margin-bottom: 1.5rem;
    }

    .filter-tabs {
      display: flex;
      gap: 0.5rem;
      margin-bottom: 1.5rem;
      overflow-x: auto;
    }

    .filter-btn {
      padding: 0.5rem 1rem;
      border-radius: 8px;
      border: 1px solid #e2e8f0;
      background: #ffffff;
      font-size: 0.85rem;
      font-weight: 600;
      color: #64748b;
      cursor: pointer;
      transition: all 0.2s;

      &:hover {
        background: #f8fafc;
        color: #0f172a;
      }

      &.active {
        background: #4f46e5;
        color: #ffffff;
        border-color: #4f46e5;
        box-shadow: 0 4px 10px rgba(79, 70, 229, 0.25);
      }
    }

    .reserva-card {
      background: #ffffff;
      border: 1px solid #e2e8f0;
      border-radius: 14px;
      padding: 1.5rem;
      margin-bottom: 1rem;
      display: flex;
      justify-content: space-between;
      align-items: center;
      transition: all 0.2s;

      &:hover {
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
        border-color: #cbd5e1;
      }
    }

    .item-pill {
      display: inline-block;
      background: #f1f5f9;
      padding: 0.25rem 0.65rem;
      border-radius: 6px;
      font-size: 0.8rem;
      margin-right: 0.5rem;
      margin-bottom: 0.35rem;
      color: #334155;
    }
  `],
})
export class GestionarReservas implements OnInit {
  private readonly business = inject(BusinessService);
  readonly authService = inject(AuthService);

  sucursales = signal<Sucursal[]>([]);
  sucursalSeleccionadaId = signal<number>(1);
  reservas = signal<Reserva[]>([]);
  filtroEstado = signal<string>('todas');
  isLoading = signal(true);
  accionandoId = signal<number | null>(null);

  ngOnInit(): void {
    const defaultSucursal = this.authService.sucursalId() || 1;
    this.sucursalSeleccionadaId.set(defaultSucursal);

    this.business.getSucursales().subscribe((data) => {
      this.sucursales.set(data);
      this.cargarReservas();
    });
  }

  cargarReservas(): void {
    this.isLoading.set(true);
    const estado = this.filtroEstado() === 'todas' ? undefined : this.filtroEstado();
    this.business.getReservasSucursal(this.sucursalSeleccionadaId(), estado).subscribe({
      next: (data) => {
        this.reservas.set(data);
        this.isLoading.set(false);
      },
      error: () => this.isLoading.set(false),
    });
  }

  cambiarSucursal(id: number): void {
    this.sucursalSeleccionadaId.set(id);
    this.cargarReservas();
  }

  cambiarFiltro(estado: string): void {
    this.filtroEstado.set(estado);
    this.cargarReservas();
  }

  confirmarApartado(r: Reserva): void {
    if (!confirm(`¿Confirmas que ya apartaste físicamente las prendas de la Reserva #${r.id}?`)) return;
    this.accionandoId.set(r.id);
    this.business.confirmarPreparacionReserva(r.id).subscribe({
      next: (act) => {
        this.reservas.update((list) => list.map((item) => (item.id === act.id ? act : item)));
        this.accionandoId.set(null);
      },
      error: (err) => {
        alert(err.error?.detail || 'Error al confirmar preparación');
        this.accionandoId.set(null);
      },
    });
  }

  atenderCliente(r: Reserva): void {
    if (!confirm(`¿Confirmas que el cliente llegó y se le entregaron las prendas en el vestidor?`)) return;
    this.accionandoId.set(r.id);
    this.business.confirmarRecepcionCliente(r.id).subscribe({
      next: (act) => {
        this.reservas.update((list) => list.map((item) => (item.id === act.id ? act : item)));
        this.accionandoId.set(null);
      },
      error: (err) => {
        alert(err.error?.detail || 'Error al atender reserva');
        this.accionandoId.set(null);
      },
    });
  }

  marcarNoShow(r: Reserva): void {
    if (!confirm(`¿Marcar como "No se presentó"? El stock reservado se liberará automáticamente al inventario.`)) return;
    this.accionandoId.set(r.id);
    this.business.marcarReservaNoShow(r.id).subscribe({
      next: (act) => {
        this.reservas.update((list) => list.map((item) => (item.id === act.id ? act : item)));
        this.accionandoId.set(null);
      },
      error: (err) => {
        alert(err.error?.detail || 'Error al marcar no-show');
        this.accionandoId.set(null);
      },
    });
  }

  badgeClase(estado: string): string {
    switch (estado) {
      case 'pendiente': return 'badge-warning';
      case 'confirmada': return 'badge-info';
      case 'atendida': return 'badge-success';
      case 'cancelada':
      case 'expirada': return 'badge-danger';
      default: return 'badge-info';
    }
  }
}

