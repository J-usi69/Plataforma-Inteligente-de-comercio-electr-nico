import { CommonModule } from '@angular/common';
import { Component, OnInit, computed, inject, output, signal } from '@angular/core';
import { IndicadoresPlataforma as Indicadores } from '../../../core/models/tienda.model';
import { PlataformaService } from '../../../core/services/plataforma.service';

/** Porcentaje de una barra respecto del mayor valor (mínimo visible para valores chicos). */
export function alturaBarra(valor: number, maximo: number): number {
  if (!maximo || valor <= 0) return 0;
  return Math.max(4, Math.round((valor / maximo) * 100));
}

/** Tablero del superadmin: ingresos por suscripciones, empresas por plan, ventas de cada empresa
 * y suscripciones que vencen pronto. */
@Component({
  selector: 'app-indicadores-plataforma',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './indicadores-plataforma.html',
  styleUrl: './indicadores-plataforma.scss',
})
export class IndicadoresPlataforma implements OnInit {
  private readonly plataforma = inject(PlataformaService);

  /** Avisa al panel si la sesión venció (401/403) o hubo otro error. */
  readonly fallo = output<{ status?: number; error?: { detail?: unknown } }>();

  readonly datos = signal<Indicadores | null>(null);
  readonly cargando = signal(true);
  readonly altura = alturaBarra;

  readonly maxIngresoMes = computed(() => Math.max(0, ...(this.datos()?.ingresos_por_mes ?? []).map((m) => m.monto)));
  readonly maxEmpresasPlan = computed(() => Math.max(0, ...(this.datos()?.empresas_por_plan ?? []).map((p) => p.cantidad)));
  readonly maxVentas = computed(() => Math.max(0, ...(this.datos()?.ventas_por_empresa ?? []).map((v) => v.total)));

  ngOnInit(): void {
    this.cargar();
  }

  cargar(): void {
    this.cargando.set(true);
    this.plataforma.indicadores().subscribe({
      next: (d) => {
        this.datos.set(d);
        this.cargando.set(false);
      },
      error: (err) => {
        this.cargando.set(false);
        this.fallo.emit(err);
      },
    });
  }
}
