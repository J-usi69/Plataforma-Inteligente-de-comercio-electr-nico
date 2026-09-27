import { CommonModule } from '@angular/common';
import { Component, EventEmitter, Input, OnDestroy, OnInit, Output, inject, signal } from '@angular/core';
import { QrLibelula } from '../../../core/models/user.model';
import { BusinessService } from '../../../core/services/business.service';

const SEGUNDOS_ENTRE_CONSULTAS = 4;

// Pago con QR a través de Libélula: genera el QR de la venta, lo muestra y consulta cada pocos
// segundos si ya se pagó (el backend además recibe el aviso de Libélula). Lo usan el carrito
// (compra digital) y la caja (cobro presencial).
@Component({
  selector: 'app-pago-qr-libelula',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="qr-panel">
      <div *ngIf="cargando()" class="qr-estado">
        <div class="qr-spinner"></div>
        <p>Generando el QR de pago...</p>
      </div>

      <div *ngIf="error()" class="qr-estado" style="color: #dc2626;">
        <p>{{ error() }}</p>
        <button type="button" class="btn btn-secondary btn-sm" (click)="generar()">Reintentar</button>
      </div>

      <ng-container *ngIf="qr() as q">
        <div *ngIf="q.modo_prueba" class="qr-prueba">
          MODO DE PRUEBA · Libélula todavía no está configurada: el QR es de demostración.
        </div>

        <img [src]="q.qr_url" alt="QR de pago" class="qr-imagen" />
        <p class="qr-instruccion">
          Escanea el QR con la app de tu banco (BNB, BCP, Unión, Mercantil, Ganadero...) y paga
          <strong>Bs. {{ q.monto | number: '1.2-2' }}</strong>.
        </p>

        <div class="qr-esperando">
          <div class="qr-spinner qr-spinner-chico"></div>
          Esperando la confirmación del pago...
        </div>

        <a *ngIf="q.url_pasarela" [href]="q.url_pasarela" target="_blank" rel="noopener" class="qr-link">
          Pagar en la pasarela de Libélula (tarjeta, Tigo Money...)
        </a>

        <button
          *ngIf="q.modo_prueba"
          type="button"
          class="btn btn-primary"
          style="width: 100%; margin-top: 0.75rem;"
          [disabled]="simulando()"
          (click)="simularPago()"
        >
          {{ simulando() ? 'Confirmando...' : '✓ Simular pago (modo de prueba)' }}
        </button>
      </ng-container>
    </div>
  `,
  styles: [`
    .qr-panel { text-align: center; }
    .qr-estado { padding: 1.5rem 0.5rem; color: #475569; font-size: 0.9rem; }
    .qr-prueba {
      background: #fef3c7; border: 1px solid #fcd34d; color: #92400e; border-radius: 8px;
      padding: 0.5rem 0.75rem; font-size: 0.75rem; font-weight: 700; margin-bottom: 0.75rem;
    }
    .qr-imagen {
      width: 220px; height: 220px; object-fit: contain; border: 1px solid #e2e8f0;
      border-radius: 12px; padding: 0.5rem; background: #ffffff;
    }
    .qr-instruccion { font-size: 0.85rem; color: #475569; margin: 0.75rem 0 0.5rem; }
    .qr-esperando {
      display: flex; align-items: center; justify-content: center; gap: 0.5rem;
      font-size: 0.8rem; color: #4f46e5; font-weight: 600;
    }
    .qr-link { display: block; margin-top: 0.75rem; font-size: 0.8rem; color: #4f46e5; }
    .qr-spinner {
      width: 32px; height: 32px; margin: 0 auto 0.5rem; border: 3px solid #e0e7ff;
      border-top-color: #4f46e5; border-radius: 50%; animation: qr-giro 0.9s linear infinite;
    }
    .qr-spinner-chico { width: 14px; height: 14px; margin: 0; border-width: 2px; }
    @keyframes qr-giro { to { transform: rotate(360deg); } }
  `],
})
export class PagoQrLibelula implements OnInit, OnDestroy {
  private readonly business = inject(BusinessService);

  @Input({ required: true }) ventaId!: number;
  @Output() pagado = new EventEmitter<void>();

  qr = signal<QrLibelula | null>(null);
  cargando = signal(false);
  error = signal<string | null>(null);
  simulando = signal(false);

  private consultaTimer: ReturnType<typeof setInterval> | null = null;
  private consultando = false;
  private terminado = false;

  ngOnInit(): void {
    this.generar();
  }

  ngOnDestroy(): void {
    this.detenerConsultas();
  }

  generar(): void {
    this.detenerConsultas();
    this.cargando.set(true);
    this.error.set(null);
    this.qr.set(null);

    this.business.generarQrLibelula(this.ventaId).subscribe({
      next: (qr) => {
        this.qr.set(qr);
        this.cargando.set(false);
        this.consultaTimer = setInterval(() => this.consultarEstado(), SEGUNDOS_ENTRE_CONSULTAS * 1000);
      },
      error: (err) => {
        this.cargando.set(false);
        this.error.set(err?.error?.detail ?? 'No se pudo generar el QR de pago.');
      },
    });
  }

  simularPago(): void {
    this.simulando.set(true);
    this.business.simularPagoQrLibelula(this.ventaId).subscribe({
      next: () => this.confirmarPagado(),
      error: (err) => {
        this.simulando.set(false);
        this.error.set(err?.error?.detail ?? 'No se pudo simular el pago.');
      },
    });
  }

  private consultarEstado(): void {
    if (this.consultando || this.terminado) return;
    this.consultando = true;
    this.business.getEstadoQrLibelula(this.ventaId).subscribe({
      next: (estado) => {
        this.consultando = false;
        if (estado.pagado) this.confirmarPagado();
      },
      // Un fallo puntual de red no corta la espera: se vuelve a consultar en el próximo intervalo
      error: () => (this.consultando = false),
    });
  }

  private confirmarPagado(): void {
    if (this.terminado) return;
    this.terminado = true;
    this.detenerConsultas();
    this.pagado.emit();
  }

  private detenerConsultas(): void {
    if (this.consultaTimer) {
      clearInterval(this.consultaTimer);
      this.consultaTimer = null;
    }
  }
}
