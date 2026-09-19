import { CommonModule } from '@angular/common';
import { Component, EventEmitter, Input, Output } from '@angular/core';

@Component({
  selector: 'app-paginador',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './paginador.html',
  styles: [`
    .paginador {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 1rem;
      padding: 1.25rem 0 0.5rem;
    }

    .paginador-btn {
      padding: 0.4rem 0.9rem;
      border-radius: 8px;
      border: 1px solid #e2e8f0;
      background: #ffffff;
      color: #334155;
      font-size: 0.82rem;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.2s;

      &:hover:not(:disabled) {
        background: #f1f5f9;
        border-color: #cbd5e1;
      }

      &:disabled {
        opacity: 0.4;
        cursor: not-allowed;
      }
    }

    .paginador-info {
      font-size: 0.82rem;
      color: #64748b;
      font-weight: 600;
    }
  `],
})
export class Paginador {
  @Input() paginaActual = 1;
  @Input() totalPaginas = 1;
  @Output() cambiarPagina = new EventEmitter<number>();

  ir(pagina: number): void {
    if (pagina < 1 || pagina > this.totalPaginas || pagina === this.paginaActual) return;
    this.cambiarPagina.emit(pagina);
  }
}
