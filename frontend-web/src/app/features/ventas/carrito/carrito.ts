import { CommonModule } from '@angular/common';
import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { environment } from '../../../environments/environment';
import { ComprobanteVenta, Sucursal, Venta } from '../../../core/models/user.model';
import { AuthService } from '../../../core/services/auth.service';
import { BusinessService } from '../../../core/services/business.service';
import { CartService } from '../../../core/services/cart.service';

// Stripe.js se carga por <script> en index.html (no via npm) y expone `Stripe` en window.
declare const Stripe: any;

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
  comprobanteEmitido = signal<ComprobanteVenta | null>(null);

  // Stripe Elements (tarjeta)
  private stripe: any = null;
  private stripeElements: any = null;
  private stripeCardElement: any = null;
  private stripeCardMontado = false;

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

  // El usuario eligió pagar con tarjeta: monta el Card Element de Stripe en el DOM
  seleccionarTarjeta(): void {
    this.metodoDigital.set('tarjeta');
    if (this.stripeCardMontado) return;

    // Se monta en el próximo ciclo para asegurar que el *ngIf ya renderizó el div
    setTimeout(() => {
      if (!this.stripe) {
        this.stripe = Stripe(environment.stripePublishableKey);
      }
      this.stripeElements = this.stripe.elements();
      this.stripeCardElement = this.stripeElements.create('card');
      this.stripeCardElement.mount('#stripe-card-element');
      this.stripeCardElement.on('change', (event: any) => {
        const errorDiv = document.getElementById('stripe-card-errors');
        if (errorDiv) errorDiv.textContent = event.error ? event.error.message : '';
      });
      this.stripeCardMontado = true;
    }, 0);
  }

  // Procesar pago electrónico en la pasarela
  confirmarPagoDigital(): void {
    const venta = this.ventaEnProceso();
    if (!venta) return;

    if (this.metodoDigital() === 'tarjeta') {
      this.confirmarPagoConStripe(venta);
      return;
    }

    // QR / Libélula: Stripe no maneja QR interoperable boliviano, se mantiene simulado
    this.isLoading.set(true);
    this.business
      .pagarVentaDigital(venta.id, {
        metodo_pago: 'qr',
        pasarela: 'Libélula QR Interoperable',
      })
      .subscribe({
        next: (ventaPagada) => this.finalizarCompra(ventaPagada.id),
        error: (err) => {
          this.isLoading.set(false);
          alert(err.error?.detail || 'Error al procesar el pago con la pasarela.');
        },
      });
  }

  // Pago con tarjeta: crea el PaymentIntent en el backend, lo confirma con Stripe
  // (el número de tarjeta viaja directo al servidor de Stripe, nunca al nuestro),
  // y solo si Stripe confirma el pago se le notifica al backend para marcar la venta pagada.
  private confirmarPagoConStripe(venta: Venta): void {
    this.isLoading.set(true);

    this.business.crearIntentoPagoStripe(venta.id).subscribe({
      next: ({ client_secret }) => {
        this.stripe
          .confirmCardPayment(client_secret, { payment_method: { card: this.stripeCardElement } })
          .then((resultado: any) => {
            if (resultado.error) {
              this.isLoading.set(false);
              alert(resultado.error.message || 'La tarjeta fue rechazada.');
              return;
            }

            this.business
              .pagarVentaDigital(venta.id, {
                metodo_pago: 'tarjeta',
                stripe_payment_intent_id: resultado.paymentIntent.id,
              })
              .subscribe({
                next: (ventaPagada) => this.finalizarCompra(ventaPagada.id),
                error: (err) => {
                  this.isLoading.set(false);
                  alert(err.error?.detail || 'Error al confirmar el pago con la pasarela.');
                },
              });
          });
      },
      error: (err) => {
        this.isLoading.set(false);
        alert(err.error?.detail || 'Error al iniciar el pago con Stripe.');
      },
    });
  }

  cerrarModalPasarela(): void {
    this.showModalPasarela.set(false);
    this.metodoDigital.set('qr');
    this.stripeCardElement?.destroy();
    this.stripeCardElement = null;
    this.stripeCardMontado = false;
  }

  private finalizarCompra(ventaId: number): void {
    this.cart.vaciar();
    this.showModalPasarela.set(false);
    this.stripeCardElement?.destroy();
    this.stripeCardElement = null;
    this.stripeCardMontado = false;

    this.business.getComprobanteVenta(ventaId).subscribe((comp) => {
      this.comprobanteEmitido.set(comp);
      this.isLoading.set(false);
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
