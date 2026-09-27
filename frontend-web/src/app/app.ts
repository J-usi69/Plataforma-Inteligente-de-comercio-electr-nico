import { CommonModule } from '@angular/common';
import { Component, inject } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { NavigationEnd, Router, RouterModule } from '@angular/router';
import { filter, map } from 'rxjs';
import { AuthService } from './core/services/auth.service';
import { CartService } from './core/services/cart.service';
import { ChatWidget } from './features/asistente/chat-widget/chat-widget';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, RouterModule, ChatWidget],
  templateUrl: './app.html',
  styleUrl: './app.scss',
})
export class App {
  readonly authService = inject(AuthService);
  readonly cartService = inject(CartService);
  private readonly router = inject(Router);

  // El probador AR se abre dentro de la app móvil: ahí sobran el menú, el pie y el chat de la tienda
  readonly pantallaLimpia = toSignal(
    this.router.events.pipe(
      filter((e) => e instanceof NavigationEnd),
      map(() => this.router.url.startsWith('/probador-ar'))
    ),
    { initialValue: window.location.pathname.startsWith('/probador-ar') }
  );

  onLogout(): void {
    this.authService.logout();
  }
}
