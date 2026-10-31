import { DatePipe } from '@angular/common';
import { Component, computed, inject, signal } from '@angular/core';
import { EstadoLocal } from '../../core/offline/modelos';
import { SincronizacionService } from '../../core/offline/sincronizacion.service';

const ETIQUETAS: Record<EstadoLocal, string> = {
  registrada: 'Registrada (por enviar)',
  enviada: 'Enviando',
  confirmada: 'Confirmada',
  rechazada: 'Rechazada',
  conflicto: 'En revisión del encargado',
};
const CLASES: Record<EstadoLocal, string> = {
  registrada: 'badge-warning',
  enviada: 'badge-info',
  confirmada: 'badge-success',
  rechazada: 'badge-danger',
  conflicto: 'badge-warning',
};

/** Indicador de la barra: cuántas operaciones registradas en este dispositivo faltan
 * sincronizar y, al abrirlo, cómo terminó cada una. La cola se envía sola; esto solo informa. */
@Component({
  selector: 'app-cola-sincronizacion',
  standalone: true,
  imports: [DatePipe],
  templateUrl: './cola-sincronizacion.html',
  styleUrl: './cola-sincronizacion.scss',
})
export class ColaSincronizacion {
  readonly sync = inject(SincronizacionService);
  readonly abierta = signal(false);
  readonly etiquetas = ETIQUETAS;
  readonly clases = CLASES;
  readonly porSincronizar = computed(() => this.sync.pendientes() + this.sync.enConflicto());
  readonly recientes = computed(() => [...this.sync.operaciones()].reverse().slice(0, 30));
}
