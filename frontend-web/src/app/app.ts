import { CommonModule } from '@angular/common';
import { Component, inject, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { NavigationEnd, Router, RouterModule } from '@angular/router';
import { SwUpdate } from '@angular/service-worker';
import { filter, map } from 'rxjs';
import { SincronizacionService } from './core/offline/sincronizacion.service';
import { AuthService } from './core/services/auth.service';
import { CartService } from './core/services/cart.service';
import { TiendaService } from './core/services/tienda.service';
import { ChatWidget } from './features/asistente/chat-widget/chat-widget';
import { ColaSincronizacion } from './shared/cola-sincronizacion/cola-sincronizacion';

/** El evento beforeinstallprompt de Chrome/Edge (todavía sin tipo en TypeScript). */
interface PedidoInstalacion {
  prompt(): Promise<void>;
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>;
}

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, RouterModule, ChatWidget, ColaSincronizacion],
  templateUrl: './app.html',
  styleUrl: './app.scss',
})
export class App {
  readonly authService = inject(AuthService);
  readonly cartService = inject(CartService);
  readonly tienda = inject(TiendaService);
  readonly sync = inject(SincronizacionService);
  private readonly router = inject(Router);
  /** El Service Worker bajó una versión nueva de la web: se ofrece recargar (sin cortar una venta en curso). */
  readonly versionNueva = signal(false);
  /** CU-07: el navegador permite instalar la web como app; se ofrece con un botón propio. Si no
   * lo permite (Safari, Firefox), el botón no aparece y la web sigue funcionando igual. */
  readonly instalable = signal(false);
  private pedidoInstalacion: PedidoInstalacion | null = null;

  constructor() {
    window.addEventListener('beforeinstallprompt', (evento) => {
      evento.preventDefault();
      this.pedidoInstalacion = evento as unknown as PedidoInstalacion;
      this.instalable.set(true);
    });
    window.addEventListener('appinstalled', () => {
      this.pedidoInstalacion = null;
      this.instalable.set(false);
    });
    this.sync.iniciar();
    const actualizaciones = inject(SwUpdate, { optional: true }); // sin Service Worker (tests) no hay
    if (actualizaciones?.isEnabled) {
      actualizaciones.versionUpdates
        .pipe(filter((evento) => evento.type === 'VERSION_READY'))
        .subscribe(() => this.versionNueva.set(true));
    }
  }

  recargar(): void {
    document.location.reload();
  }

  async instalar(): Promise<void> {
    const pedido = this.pedidoInstalacion;
    if (!pedido) {
      return;
    }
    await pedido.prompt();
    if ((await pedido.userChoice).outcome === 'accepted') {
      this.pedidoInstalacion = null;
      this.instalable.set(false);
    }
  }

  // El probador AR se abre dentro de la app móvil: ahí sobran el menú, el pie y el chat de la tienda
  readonly pantallaLimpia = toSignal(
    this.router.events.pipe(
      filter((e) => e instanceof NavigationEnd),
      map(() => this.router.url.startsWith('/probador-ar'))
    ),
    { initialValue: window.location.pathname.startsWith('/probador-ar') }
  );

  onLogout(): void {
    const pendientes = this.sync.pendientes();
    if (
      pendientes > 0 &&
      !confirm(`Tenés ${pendientes} operaciones sin enviar. Quedan guardadas en este dispositivo y se envían cuando vuelvas a iniciar sesión. ¿Salir igual?`)
    ) {
      return;
    }
    this.authService.logout();
  }
}
