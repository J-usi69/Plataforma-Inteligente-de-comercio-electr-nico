import { CommonModule } from '@angular/common';
import { Component, OnInit, inject, signal } from '@angular/core';
import { ComprobanteVenta, Venta } from '../../../core/models/user.model';
import { BusinessService } from '../../../core/services/business.service';

@Component({
  selector: 'app-mis-compras',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './mis-compras.html',
  styles: [`
    .compra-card {
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
        border-color: #cbd5e1;
        box-shadow: 0 4px 10px rgba(0, 0, 0, 0.04);
      }
    }
  `],
})
export class MisCompras implements OnInit {
  private readonly business = inject(BusinessService);

  compras = signal<Venta[]>([]);
  isLoading = signal(true);
  comprobanteSeleccionado = signal<ComprobanteVenta | null>(null);

  ngOnInit(): void {
    this.cargarCompras();
  }

  cargarCompras(): void {
    this.isLoading.set(true);
    this.business.getMisCompras().subscribe({
      next: (data) => {
        this.compras.set(data);
        this.isLoading.set(false);
      },
      error: () => this.isLoading.set(false),
    });
  }

  verComprobante(ventaId: number): void {
    this.business.getComprobanteVenta(ventaId).subscribe((comp) => {
      this.comprobanteSeleccionado.set(comp);
    });
  }

  cerrarComprobante(): void {
    this.comprobanteSeleccionado.set(null);
  }

  imprimirComprobante(): void {
    window.print();
  }
}

