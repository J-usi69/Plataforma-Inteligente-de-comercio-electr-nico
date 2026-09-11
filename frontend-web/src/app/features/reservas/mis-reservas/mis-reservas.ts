import { CommonModule } from '@angular/common';
import { Component, OnInit, inject, signal } from '@angular/core';
import { Reserva } from '../../../core/models/user.model';
import { BusinessService } from '../../../core/services/business.service';

@Component({
  imports: [CommonModule],
  selector: 'app-mis-reservas',
  styles: ``,
  templateUrl: './mis-reservas.html',
})
export class MisReservas implements OnInit {
  private readonly business = inject(BusinessService);

  reservas = signal<Reserva[]>([]);
  isLoading = signal(true);
  cancelandoId = signal<number | null>(null);

  ngOnInit(): void {
    this.cargarReservas();
  }

  cargarReservas(): void {
    this.isLoading.set(true);
    this.business.getMisReservas().subscribe({
      next: (data) => {
        this.reservas.set(data);
        this.isLoading.set(false);
      },
      error: () => this.isLoading.set(false),
    });
  }

  badgeClase(estado: string): string {
    switch (estado) {
      case 'pendiente':
        return 'badge-warning';
      case 'confirmada':
        return 'badge-info';
      case 'atendida':
        return 'badge-success';
      case 'cancelada':
      case 'expirada':
        return 'badge-danger';
      default:
        return 'badge-info';
    }
  }

  cancelar(reserva: Reserva): void {
    if (!confirm('¿Seguro que quieres cancelar esta reserva?')) return;

    this.cancelandoId.set(reserva.id);
    this.business.cancelarReserva(reserva.id).subscribe({
      next: (actualizada) => {
        this.reservas.update((lista) => lista.map((r) => (r.id === actualizada.id ? actualizada : r)));
        this.cancelandoId.set(null);
      },
      error: () => this.cancelandoId.set(null),
    });
  }
}
