import { CommonModule } from '@angular/common';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { FUNCIONES_PLAN, FuncionesPlan, NuevoPlan, PlanAdmin, TiendaAdmin } from '../../../core/models/tienda.model';
import { AltaEmpresa, PlataformaService } from '../../../core/services/plataforma.service';
import { IndicadoresPlataforma } from '../indicadores-plataforma/indicadores-plataforma';
import { aDireccion } from '../registro-tienda/registro-tienda';
import { Bitacora } from '../../../shared/bitacora/bitacora';
import { ReportesPersonalizados } from '../../../shared/reportes-personalizados/reportes-personalizados';
import { Respaldo } from '../../../shared/respaldo/respaldo';

const ALTA_VACIA: AltaEmpresa = { nombre_tienda: '', slug: '', correo: '', password: '', plan_codigo: 'basico' };

function planVacio(): NuevoPlan {
  return {
    codigo: '', nombre: '', descripcion: null, precio_mensual: 0,
    max_sucursales: null, max_prendas: null, max_personal: null,
    operacion_offline: true, reportes: true, reportes_ia: false, asistente_ia: true, vestidor_ar: true, pago_qr: true,
  };
}

/** Superadmin de la plataforma: indicadores, todas las empresas con su plan y su suscripción, la
 * configuración de los planes (los límites del enunciado son los valores iniciales), los reportes
 * personalizables de todas las empresas, la bitácora de toda la plataforma y el respaldo del sistema
 * completo o de cada empresa. */
@Component({
  selector: 'app-panel-plataforma',
  standalone: true,
  imports: [CommonModule, FormsModule, IndicadoresPlataforma, ReportesPersonalizados, Bitacora, Respaldo],
  templateUrl: './panel-plataforma.html',
  styleUrl: './panel-plataforma.scss',
})
export class PanelPlataforma implements OnInit {
  readonly plataforma = inject(PlataformaService);

  readonly tiendas = signal<TiendaAdmin[]>([]);
  /** Todos los planes, también los desactivados (la pestaña Planes los muestra para reactivarlos). */
  readonly planes = signal<PlanAdmin[]>([]);
  /** Los que se pueden contratar: los únicos que se ofrecen al dar de alta o cambiar de plan. */
  readonly planesActivos = computed(() => this.planes().filter((p) => p.estado));
  readonly pestana = signal<'indicadores' | 'empresas' | 'planes' | 'reportes' | 'bitacora' | 'respaldo'>('indicadores');
  readonly ejemplosReportes = [
    'Ingresos de este mes por plan',
    'Empresas del plan Básico que vencen pronto',
    '¿Qué empresas están cerca del límite de su plan?',
    'Inicios de sesión fallidos de esta semana',
  ];
  /** Empresa elegida en la pestaña Respaldo (su fuente se memoriza: una nueva por cada cambio). */
  readonly empresaRespaldo = signal<number | null>(null);
  readonly respaldoEmpresa = computed(() => {
    const id = this.empresaRespaldo();
    return id === null ? null : this.plataforma.respaldoDeEmpresa(id);
  });
  readonly tiendaRespaldo = computed(() => this.tiendas().find((t) => t.id === this.empresaRespaldo()) ?? null);
  readonly mensaje = signal<string | null>(null);
  readonly error = signal<string | null>(null);
  readonly ocupado = signal<string | null>(null);
  readonly funciones = FUNCIONES_PLAN;

  readonly resumen = computed(() => {
    const tiendas = this.tiendas();
    return {
      total: tiendas.length,
      activas: tiendas.filter((t) => t.estado === 'activa' && t.estado_suscripcion === 'activa').length,
      porPlan: this.planes()
        .map((p) => ({ nombre: p.nombre, cantidad: tiendas.filter((t) => t.plan_codigo === p.codigo).length, activo: p.estado }))
        .filter((p) => p.activo || p.cantidad > 0),
    };
  });

  correo = '';
  password = '';
  alta: AltaEmpresa = { ...ALTA_VACIA };
  mostrarAlta = false;
  nuevoPlan: NuevoPlan = planVacio();
  mostrarNuevoPlan = false;

  ngOnInit(): void {
    if (this.plataforma.conSesion()) {
      this.cargar();
    }
  }

  entrar(): void {
    this.error.set(null);
    this.plataforma.login(this.correo.trim(), this.password).subscribe({
      next: () => {
        this.password = '';
        this.cargar();
      },
      error: (err) => this.error.set(err?.error?.detail ?? 'No se pudo iniciar sesión'),
    });
  }

  salir(): void {
    this.plataforma.salir();
    this.tiendas.set([]);
  }

  cargar(): void {
    this.plataforma.tiendas().subscribe({ next: (t) => this.tiendas.set(t), error: (err) => this.fallo(err) });
    this.plataforma.planesAdmin().subscribe({ next: (p) => this.planes.set(p), error: (err) => this.fallo(err) });
  }

  urlDe(tienda: TiendaAdmin): string {
    return `/t/${tienda.slug}/`;
  }

  /** Planes para el selector de una empresa: los activos y el que ya tiene, aunque esté desactivado. */
  planesPara(tienda: TiendaAdmin): PlanAdmin[] {
    return this.planes().filter((p) => p.estado || p.codigo === tienda.plan_codigo);
  }

  cambiarPlan(tienda: TiendaAdmin, planCodigo: string): void {
    if (planCodigo === tienda.plan_codigo) {
      return;
    }
    this.operar(`plan-${tienda.id}`, this.plataforma.actualizarTienda(tienda.id, { plan_codigo: planCodigo }), `${tienda.nombre} pasó al plan elegido.`);
  }

  alternarTienda(tienda: TiendaAdmin): void {
    const suspender = tienda.estado === 'activa';
    if (suspender && !confirm(`¿Suspender ${tienda.nombre}? Nadie podrá usar la tienda hasta reactivarla.`)) {
      return;
    }
    this.operar(
      `estado-${tienda.id}`,
      this.plataforma.actualizarTienda(tienda.id, { estado: suspender ? 'suspendida' : 'activa' }),
      `${tienda.nombre} ${suspender ? 'quedó suspendida' : 'volvió a estar activa'}.`,
    );
  }

  alternarSuscripcion(tienda: TiendaAdmin): void {
    const cancelar = tienda.estado_suscripcion !== 'cancelada';
    if (cancelar && !confirm(`¿Cancelar la suscripción de ${tienda.nombre}? La tienda queda en modo consulta.`)) {
      return;
    }
    this.operar(
      `suscripcion-${tienda.id}`,
      this.plataforma.actualizarTienda(tienda.id, { estado_suscripcion: cancelar ? 'cancelada' : 'activa' }),
      `Suscripción de ${tienda.nombre} ${cancelar ? 'cancelada' : 'reactivada'}.`,
    );
  }

  renovar(tienda: TiendaAdmin): void {
    this.operar(`renovar-${tienda.id}`, this.plataforma.renovar(tienda.id, 1), `${tienda.nombre}: suscripción renovada por un mes.`);
  }

  alCambiarNombreAlta(): void {
    this.alta.slug = aDireccion(this.alta.nombre_tienda);
  }

  crearEmpresa(): void {
    this.ocupado.set('alta');
    this.error.set(null);
    this.plataforma.crearTienda({ ...this.alta, slug: aDireccion(this.alta.slug) }).subscribe({
      next: (tienda) => {
        this.ocupado.set(null);
        this.tiendas.update((ts) => [tienda, ...ts]);
        this.mensaje.set(`Empresa ${tienda.nombre} registrada con el plan ${tienda.plan}.`);
        this.alta = { ...ALTA_VACIA };
        this.mostrarAlta = false;
      },
      error: (err) => this.fallo(err),
    });
  }

  guardarPlan(plan: PlanAdmin): void {
    const { nombre, descripcion, precio_mensual, max_sucursales, max_prendas, max_personal } = plan;
    const funciones = Object.fromEntries(this.funciones.map((f) => [f.clave, plan[f.clave]])) as Partial<FuncionesPlan>;
    this.operarPlan(
      plan,
      this.plataforma.configurarPlan(plan.codigo, { nombre, descripcion, precio_mensual, max_sucursales, max_prendas, max_personal, ...funciones }),
      `«${plan.nombre}» guardado: rige desde ahora para todas sus empresas.`,
    );
  }

  alCambiarNombrePlan(): void {
    this.nuevoPlan.codigo = aDireccion(this.nuevoPlan.nombre).slice(0, 30).replace(/-+$/, '');
  }

  crearPlan(): void {
    this.ocupado.set('nuevo-plan');
    this.error.set(null);
    this.mensaje.set(null);
    this.plataforma.crearPlan({ ...this.nuevoPlan, codigo: aDireccion(this.nuevoPlan.codigo).slice(0, 30) }).subscribe({
      next: (plan) => {
        this.ocupado.set(null);
        this.planes.update((ps) => [...ps, plan]);
        this.mensaje.set(`«${plan.nombre}» creado: ya se ofrece al registrar empresas y en "Mi plan".`);
        this.nuevoPlan = planVacio();
        this.mostrarNuevoPlan = false;
      },
      error: (err) => this.fallo(err),
    });
  }

  /** Desactivado deja de ofrecerse a empresas nuevas; las que ya lo tienen lo conservan. */
  alternarPlan(plan: PlanAdmin): void {
    const desactivar = plan.estado;
    if (
      desactivar &&
      !confirm(
        `¿Desactivar el plan ${plan.nombre}? Deja de ofrecerse a empresas nuevas` +
          (plan.empresas ? `; las ${plan.empresas} que lo tienen lo conservan.` : '.'),
      )
    ) {
      return;
    }
    this.operarPlan(
      plan,
      this.plataforma.configurarPlan(plan.codigo, { estado: !desactivar }),
      `«${plan.nombre}» ${desactivar ? 'desactivado: ya no se puede contratar' : 'activado: se vuelve a ofrecer'}.`,
    );
  }

  /** Solo se elimina un plan que nunca se contrató; si no, el backend lo rechaza y se ofrece desactivarlo. */
  eliminarPlan(plan: PlanAdmin): void {
    if (!confirm(`¿Eliminar el plan ${plan.nombre}? No se puede deshacer.`)) {
      return;
    }
    this.ocupado.set(`plan-${plan.codigo}`);
    this.error.set(null);
    this.mensaje.set(null);
    this.plataforma.eliminarPlan(plan.codigo).subscribe({
      next: () => {
        this.ocupado.set(null);
        this.planes.update((ps) => ps.filter((p) => p.codigo !== plan.codigo));
        this.mensaje.set(`«${plan.nombre}» eliminado.`);
      },
      error: (err) => {
        const detalle = err?.error?.detail;
        if (err?.status === 409 && typeof detalle === 'string') {
          this.ocupado.set(null);
          if (plan.estado && confirm(`${detalle}\n\n¿Desactivarlo ahora?`)) {
            this.operarPlan(plan, this.plataforma.configurarPlan(plan.codigo, { estado: false }), `«${plan.nombre}» desactivado: ya no se puede contratar.`);
          } else {
            this.error.set(detalle);
          }
          return;
        }
        this.fallo(err);
      },
    });
  }

  private operarPlan(plan: PlanAdmin, pedido: ReturnType<PlataformaService['configurarPlan']>, mensaje: string): void {
    this.ocupado.set(`plan-${plan.codigo}`);
    this.error.set(null);
    this.mensaje.set(null);
    pedido.subscribe({
      next: (actualizado) => {
        this.ocupado.set(null);
        this.planes.update((ps) => ps.map((p) => (p.codigo === actualizado.codigo ? actualizado : p)));
        this.mensaje.set(mensaje);
      },
      error: (err) => this.fallo(err),
    });
  }

  private operar(clave: string, pedido: ReturnType<PlataformaService['renovar']>, mensaje: string): void {
    this.ocupado.set(clave);
    this.error.set(null);
    this.mensaje.set(null);
    pedido.subscribe({
      next: (actualizada) => {
        this.ocupado.set(null);
        this.tiendas.update((ts) => ts.map((t) => (t.id === actualizada.id ? actualizada : t)));
        this.mensaje.set(mensaje);
      },
      error: (err) => this.fallo(err),
    });
  }

  /** Errores de las pestañas Indicadores y Reportes (sesión vencida u otros). */
  alFallar(err: { status?: number; error?: { detail?: unknown } }): void {
    this.fallo(err);
  }

  private fallo(err: { status?: number; error?: { detail?: unknown } }): void {
    this.ocupado.set(null);
    if (err?.status === 401 || err?.status === 403) {
      this.salir();
      this.error.set('Tu sesión de la plataforma venció: iniciá sesión de nuevo.');
      return;
    }
    const detalle = err?.error?.detail;
    this.error.set(typeof detalle === 'string' ? detalle : 'No se pudo completar la operación. Revisá los datos.');
  }
}
