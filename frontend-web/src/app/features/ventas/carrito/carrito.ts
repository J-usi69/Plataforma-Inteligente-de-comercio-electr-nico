import { CommonModule } from '@angular/common';
import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { ComprobanteVenta, Sucursal, Venta } from '../../../core/models/user.model';
import { AuthService } from '../../../core/services/auth.service';
import { BusinessService } from '../../../core/services/business.service';
import { CartService } from '../../../core/services/cart.service';

@Component({
  selector: 'app-carrito',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './carrito.html',
  styles: [`
    .cart-grid {
      display: grid;
      grid-template-columns: 1.2fr 0.8fr;
      gap: 2rem;

      @media (max-width: 900px) {
        grid-template-columns: 1fr;
      }
    }

    .cart-item-card {
      display: flex;
      align-items: center;
      gap: 1.25rem;
      background: #ffffff;
      border: 1px solid #e2e8f0;
      border-radius: 12px;
      padding: 1.25rem;
      margin-bottom: 1rem;
      transition: all 0.2s;

      &:hover {
        border-color: #cbd5e1;
        box-shadow: 0 4px 10px rgba(0,0,0,0.04);
      }
    }

    .item-img-placeholder {
      width: 70px;
      height: 70px;
      border-radius: 8px;
      background: #f1f5f9;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 2rem;
      flex-shrink: 0;
    }

    .order-summary-card {
      background: #ffffff;
      border: 1px solid #e2e8f0;
      border-radius: 16px;
      padding: 1.75rem;
      position: sticky;
      top: 90px;
      box-shadow: 0 4px 12px rgba(0,0,0,0.03);
    }

    .qr-container {
      background: #ffffff;
      border: 2px solid #e2e8f0;
      border-radius: 16px;
      padding: 1.5rem;
      text-align: center;
      margin: 1.5rem 0;
    }

    .qr-mock {
      width: 180px;
      height: 180px;
      margin: 0 auto 1rem;
      background: repeating-linear-gradient(
        0deg,
        #0f172a,
        #0f172a 10px,
        #ffffff 10px,
        #ffffff 20px
      );
      display: flex;
      align-items: center;
      justify-content: center;
      border: 6px solid #0f172a;
      border-radius: 8px;
      font-weight: 800;
      color: #0f172a;
      background-color: #ffffff;
    }
  `],
})
export class Carrito implements OnInit {
  readonly cart = inject(CartService);
  private readonly business = inject(BusinessService);
  readonly authService = inject(AuthService);
  private readonly router = inject(Router);

  sucursales = signal<Sucursal[]>([]);
  isLoading = signal(false);

  // Pasarela de pago digital
  showModalPasarela = signal(false);
  ventaEnProceso = signal<Venta | null>(null);
  metodoDigital = signal<'qr' | 'tarjeta'>('qr');
  numeroTarjeta = '';
  fechaExpiracion = '';
  cvv = '';
  comprobanteEmitido = signal<ComprobanteVenta | null>(null);

  ngOnInit(): void {
    this.business.getSucursales().subscribe((data) => {
      this.sucursales.set(data);
    });
  }

  cambiarSucursal(event: any): void {
    const id = Number(event.target.value);
    this.cart.setSucursal(id);
  }

  // Iniciar compra digital desde la web
  iniciarCompraDigital(): void {
    if (!this.authService.isLoggedIn()) {
      alert('Debes iniciar sesión para completar tu compra digital');
      this.router.navigate(['/login']);
      return;
    }

    if (!this.cart.items().length) return;

    this.isLoading.set(true);

    const payload = {
      sucursal_id: this.cart.sucursalId(),
      detalles: this.cart.items().map((i) => ({
        variante_id: i.variante_id,
        cantidad: i.cantidad,
      })),
    };

    this.business.crearVentaDigital(payload).subscribe({
      next: (venta) => {
        this.ventaEnProceso.set(venta);
        this.isLoading.set(false);
        this.showModalPasarela.set(true);
      },
      error: (err) => {
        this.isLoading.set(false);
        alert(err.error?.detail || 'Error al generar la orden digital. Verifica el stock en la sucursal seleccionada.');
      },
    });
  }

  // Procesar pago electrónico en la pasarela
  confirmarPagoDigital(): void {
    const venta = this.ventaEnProceso();
    if (!venta) return;

    this.isLoading.set(true);

    this.business
      .pagarVentaDigital(venta.id, {
        metodo_pago: this.metodoDigital(),
        pasarela: this.metodoDigital() === 'qr' ? 'Libélula QR Interoperable' : 'Pasarela Tarjeta Visa/Mastercard',
        numero_tarjeta_simulada: this.metodoDigital() === 'tarjeta' ? this.numeroTarjeta : undefined,
      })
      .subscribe({
        next: (ventaPagada) => {
          this.cart.vaciar();
          this.showModalPasarela.set(false);

          // Obtener comprobante oficial
          this.business.getComprobanteVenta(ventaPagada.id).subscribe((comp) => {
            this.comprobanteEmitido.set(comp);
            this.isLoading.set(false);
          });
        },
        error: (err) => {
          this.isLoading.set(false);
          alert(err.error?.detail || 'Error al procesar el pago con la pasarela.');
        },
      });
  }

  cerrarComprobante(): void {
    this.comprobanteEmitido.set(null);
    this.router.navigate(['/mis-compras']);
  }

  imprimirComprobante(): void {
    window.print();
  }
}
