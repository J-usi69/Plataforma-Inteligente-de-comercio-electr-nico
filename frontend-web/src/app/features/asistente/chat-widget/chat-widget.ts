import { CommonModule } from '@angular/common';
import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { AuthService } from '../../../core/services/auth.service';
import { BusinessService } from '../../../core/services/business.service';

interface MensajeChat {
  autor: 'cliente' | 'asistente';
  texto: string;
}

@Component({
  selector: 'app-chat-widget',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './chat-widget.html',
  styles: [`
    .chat-fab {
      position: fixed;
      bottom: 24px;
      right: 24px;
      width: 56px;
      height: 56px;
      border-radius: 50%;
      background: #4f46e5;
      color: #ffffff;
      border: none;
      box-shadow: 0 8px 20px rgba(79, 70, 229, 0.35);
      cursor: pointer;
      font-size: 1.4rem;
      z-index: 100;
    }

    .chat-panel {
      position: fixed;
      bottom: 90px;
      right: 24px;
      width: 320px;
      max-height: 440px;
      background: #ffffff;
      border-radius: 16px;
      box-shadow: 0 20px 40px -10px rgba(0, 0, 0, 0.25);
      border: 1px solid #e2e8f0;
      display: flex;
      flex-direction: column;
      z-index: 100;
      overflow: hidden;
    }

    .chat-header {
      background: #4f46e5;
      color: #ffffff;
      padding: 0.85rem 1rem;
      font-weight: 700;
      font-size: 0.9rem;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }

    .chat-body {
      flex: 1;
      overflow-y: auto;
      padding: 0.85rem;
      display: flex;
      flex-direction: column;
      gap: 0.5rem;
      min-height: 220px;
    }

    .chat-bubble {
      max-width: 85%;
      padding: 0.55rem 0.75rem;
      border-radius: 10px;
      font-size: 0.82rem;
      line-height: 1.4;
    }

    .chat-bubble.cliente {
      align-self: flex-end;
      background: #eef2ff;
      color: #312e81;
    }

    .chat-bubble.asistente {
      align-self: flex-start;
      background: #f1f5f9;
      color: #0f172a;
    }

    .chat-input-bar {
      display: flex;
      gap: 0.5rem;
      padding: 0.75rem;
      border-top: 1px solid #e2e8f0;
    }
  `],
})
export class ChatWidget {
  private readonly business = inject(BusinessService);
  readonly authService = inject(AuthService);

  abierto = signal(false);
  enviando = signal(false);
  mensajeActual = '';
  mensajes = signal<MensajeChat[]>([
    { autor: 'asistente', texto: '¡Hola! Soy el asistente de FashionStore. ¿En qué puedo ayudarte hoy?' },
  ]);

  toggle(): void {
    this.abierto.set(!this.abierto());
  }

  enviar(): void {
    const texto = this.mensajeActual.trim();
    if (!texto || this.enviando()) return;

    this.mensajes.update((prev) => [...prev, { autor: 'cliente', texto }]);
    this.mensajeActual = '';
    this.enviando.set(true);

    this.business.enviarMensajeChat(texto).subscribe({
      next: (res) => {
        this.mensajes.update((prev) => [...prev, { autor: 'asistente', texto: res.respuesta }]);
        this.enviando.set(false);
      },
      error: () => {
        this.mensajes.update((prev) => [...prev, {
          autor: 'asistente',
          texto: 'No pude procesar tu consulta en este momento. Intentá de nuevo más tarde.',
        }]);
        this.enviando.set(false);
      },
    });
  }
}
