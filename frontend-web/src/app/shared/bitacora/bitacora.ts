import { CommonModule } from '@angular/common';
import { Component, computed, effect, input, output, signal, untracked } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { CriterioReporte, FormatoReporte, OpcionesReporte, ReportePlataforma } from '../../core/models/tienda.model';
import { FuenteReportes } from '../../core/services/fuentes';
import { descargar, detalleDelError, hoyISO } from '../../core/utils/descargas';
import { Paginador } from '../paginador/paginador';

const POR_PAGINA = 25;
const DIAS_POR_DEFECTO = 30;

/** Los filtros de la bitácora como criterios del reporte (los vacíos no se mandan). */
export function criteriosBitacora(filtros: { usuario: string; accion: string; empresa: string }): CriterioReporte[] {
  const pares: [string, string][] = [
    ['Usuario', filtros.usuario],
    ['Acción', filtros.accion],
    ['Empresa', filtros.empresa],
  ];
  return pares.filter(([, valor]) => valor.trim()).map(([columna, valor]) => ({ columna, operador: 'contiene', valor: valor.trim() }));
}

function haceDias(dias: number): string {
  const fecha = new Date();
  fecha.setDate(fecha.getDate() - dias);
  return fecha.toISOString().slice(0, 10);
}

/** Bitácora (característica 3): cada acción con fecha y hora, usuario, rol, IP y acción. El
 * administrador de una empresa ve la de su empresa; el superadmin, la de todas y la de la
 * plataforma (con la columna Empresa). Es de solo lectura: nadie la edita ni la borra. */
@Component({
  selector: 'app-bitacora',
  standalone: true,
  imports: [CommonModule, FormsModule, Paginador],
  templateUrl: './bitacora.html',
  styleUrl: './bitacora.scss',
})
export class Bitacora {
  readonly fuente = input.required<FuenteReportes>();
  /** Muestra el filtro por empresa (bitácora de la plataforma). */
  readonly conEmpresa = input(false);
  readonly prefijoArchivos = input('bitacora');

  readonly fallo = output<{ status?: number; error?: { detail?: unknown } }>();

  readonly reporte = signal<ReportePlataforma | null>(null);
  readonly pagina = signal(1);
  readonly ocupado = signal<string | null>(null);
  readonly error = signal<string | null>(null);
  readonly totalPaginas = computed(() => Math.max(1, Math.ceil((this.reporte()?.filas.length ?? 0) / POR_PAGINA)));
  readonly filasPagina = computed(() => {
    const inicio = (this.pagina() - 1) * POR_PAGINA;
    return this.reporte()?.filas.slice(inicio, inicio + POR_PAGINA) ?? [];
  });
  readonly columnaAccion = computed(() => this.reporte()?.columnas.indexOf('Acción') ?? -1);

  desde = haceDias(DIAS_POR_DEFECTO);
  hasta = '';
  usuario = '';
  accion = '';
  empresa = '';

  constructor() {
    effect(() => {
      this.fuente();
      untracked(() => this.buscar());
    });
  }

  private opciones(): OpcionesReporte | null {
    if (this.desde && this.hasta && this.desde > this.hasta) {
      this.error.set('La fecha "desde" es posterior a "hasta".');
      return null;
    }
    return {
      desde: this.desde || undefined,
      hasta: this.hasta || undefined,
      columnas: [],
      criterios: criteriosBitacora({ usuario: this.usuario, accion: this.accion, empresa: this.conEmpresa() ? this.empresa : '' }),
    };
  }

  buscar(): void {
    this.error.set(null);
    const opciones = this.opciones();
    if (!opciones) return;
    this.ocupado.set('buscar');
    this.fuente()
      .reporte('bitacora', opciones)
      .subscribe({
        next: (reporte) => {
          this.ocupado.set(null);
          this.reporte.set(reporte);
          this.pagina.set(1);
        },
        error: (err) => this.manejar(err),
      });
  }

  limpiar(): void {
    this.desde = '';
    this.hasta = '';
    this.usuario = '';
    this.accion = '';
    this.empresa = '';
    this.buscar();
  }

  exportar(formato: FormatoReporte): void {
    this.error.set(null);
    const opciones = this.opciones();
    if (!opciones) return;
    this.ocupado.set(formato);
    this.fuente()
      .exportar('bitacora', formato, opciones)
      .subscribe({
        next: (archivo) => {
          this.ocupado.set(null);
          descargar(archivo, `${this.prefijoArchivos()}_bitacora_${hoyISO()}.${formato === 'excel' ? 'xlsx' : formato}`);
        },
        error: (err) => this.manejar(err),
      });
  }

  /** Las acciones de seguridad (intentos fallidos o sobre datos de otra empresa, desactivaciones,
   * restauraciones) se destacan. */
  esAlerta(accion: unknown): boolean {
    return /fallid|intento de|inactiva|desactiv|restaur|eliminad/i.test(String(accion ?? ''));
  }

  private manejar(err: { status?: number; error?: unknown }): void {
    this.ocupado.set(null);
    if (err?.status === 401 || err?.status === 403) {
      this.fallo.emit(err as { status?: number });
      return;
    }
    detalleDelError(err, 'No se pudo consultar la bitácora.').then((texto) => this.error.set(texto));
  }
}
