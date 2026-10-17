import { CommonModule } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterModule } from '@angular/router';
import { CambioPlan, FUNCIONES_PLAN, Plan, UsoPlan } from '../../../core/models/tienda.model';
import { AuthService } from '../../../core/services/auth.service';
import { TiendaService } from '../../../core/services/tienda.service';

type Recurso = 'sucursales' | 'prendas' | 'personal';

const MOVIMIENTOS: Record<string, string> = {
  alta: 'Alta',
  cambio_plan: 'Cambio de plan',
  renovacion: 'Renovación',
  suspension: 'Suspensión',
  reactivacion: 'Reactivación',
  cancelacion: 'Cancelación',
  ajuste: 'Ajuste',
};

/** El administrador de la empresa: su plan, cuánto usa de cada límite, la suscripción (inicio,
 * vencimiento, renovación), el cambio de plan y el historial. */
@Component({
  selector: 'app-mi-plan',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterModule],
  templateUrl: './mi-plan.html',
  styleUrl: './mi-plan.scss',
})
export class MiPlan implements OnInit {
  private readonly http = inject(HttpClient);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  readonly auth = inject(AuthService);
  readonly tienda = inject(TiendaService);

  readonly estado = signal<UsoPlan | null>(null);
  readonly procesando = signal<string | null>(null); // código del plan que se está contratando, o 'renovar'
  readonly error = signal<string | null>(null);
  readonly mensaje = signal<string | null>(null);
  mesesRenovacion = 1;

  readonly funciones = FUNCIONES_PLAN;
  readonly recursos: { clave: Recurso; nombre: string; limite: 'max_sucursales' | 'max_prendas' | 'max_personal' }[] = [
    { clave: 'sucursales', nombre: 'Sucursales activas', limite: 'max_sucursales' },
    { clave: 'prendas', nombre: 'Prendas', limite: 'max_prendas' },
    { clave: 'personal', nombre: 'Empleados', limite: 'max_personal' },
  ];

  ngOnInit(): void {
    if (!this.auth.isAdmin()) {
      this.router.navigate(['/login']);
      return;
    }
    const consulta = this.route.snapshot.queryParamMap;
    const sesionStripe = consulta.get('session_id');
    if (consulta.get('suscripcion') === 'ok' && sesionStripe) {
      this.confirmarPagoStripe(sesionStripe);
      return;
    }
    if (consulta.get('suscripcion') === 'cancelada') {
      this.mensaje.set('Cancelaste el pago en Stripe: tu plan no cambió.');
    }
    this.cargar();
  }

  cargar(): void {
    this.http.get<UsoPlan>('/api/v1/tienda/plan').subscribe({
      next: (estado) => this.estado.set(estado),
      error: (err) => this.fallo(err),
    });
  }

  limite(recurso: { limite: 'max_sucursales' | 'max_prendas' | 'max_personal' }): number | null {
    return this.estado()?.plan[recurso.limite] ?? null;
  }

  porcentaje(recurso: { clave: Recurso; limite: 'max_sucursales' | 'max_prendas' | 'max_personal' }): number {
    const maximo = this.limite(recurso);
    const usado = this.estado()?.uso[recurso.clave] ?? 0;
    return maximo ? Math.min(100, Math.round((usado / maximo) * 100)) : 0;
  }

  etiqueta(tipo: string): string {
    return MOVIMIENTOS[tipo] ?? tipo;
  }

  cambiarA(plan: Plan): void {
    const precio = `${plan.precio_mensual} ${plan.moneda}`;
    if (!confirm(`¿Pasar al plan ${plan.nombre} por ${precio} al mes? Se registra el pago del primer mes.`)) {
      return;
    }
    this.empezar(plan.codigo);
    this.http.post<CambioPlan>('/api/v1/tienda/plan', { plan_codigo: plan.codigo }).subscribe({
      next: (res) => {
        if (res.url) {
          window.location.href = res.url; // cobro con Stripe: vuelve a esta página con ?suscripcion=ok
          return;
        }
        this.terminar(res.estado, `Listo: tu empresa ahora tiene el plan ${plan.nombre}.`);
      },
      error: (err) => this.fallo(err),
    });
  }

  renovar(): void {
    this.empezar('renovar');
    this.http.post<UsoPlan>('/api/v1/tienda/plan/renovar', { meses: this.mesesRenovacion }).subscribe({
      next: (estado) => this.terminar(estado, `Suscripción renovada por ${this.mesesRenovacion} ${this.mesesRenovacion === 1 ? 'mes' : 'meses'}.`),
      error: (err) => this.fallo(err),
    });
  }

  private confirmarPagoStripe(sessionId: string): void {
    this.empezar('stripe');
    this.http.post<UsoPlan>('/api/v1/tienda/plan/confirmar', { session_id: sessionId }).subscribe({
      next: (estado) => {
        this.terminar(estado, 'Pago confirmado por Stripe: tu plan quedó actualizado.');
        this.router.navigate([], { queryParams: {}, replaceUrl: true });
      },
      error: (err) => {
        this.fallo(err);
        this.cargar();
      },
    });
  }

  private empezar(operacion: string): void {
    this.procesando.set(operacion);
    this.error.set(null);
    this.mensaje.set(null);
  }

  private terminar(estado: UsoPlan | null, mensaje: string): void {
    this.procesando.set(null);
    if (estado) {
      this.estado.set(estado);
    }
    this.mensaje.set(mensaje);
    this.tienda.avisoPlan.set(null);
    this.tienda.cargar(); // las funciones del plan nuevo se ven en toda la web sin recargar
  }

  private fallo(err: { error?: { detail?: string } }): void {
    this.procesando.set(null);
    this.error.set(err?.error?.detail ?? 'No se pudo completar la operación. Probá de nuevo.');
  }
}
