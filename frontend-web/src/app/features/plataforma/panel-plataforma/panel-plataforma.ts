import { CommonModule } from '@angular/common';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { FUNCIONES_PLAN, FuncionesPlan, Plan, TiendaAdmin } from '../../../core/models/tienda.model';
import { AltaEmpresa, PlataformaService } from '../../../core/services/plataforma.service';
import { aDireccion } from '../registro-tienda/registro-tienda';

const ALTA_VACIA: AltaEmpresa = { nombre_tienda: '', slug: '', correo: '', password: '', plan_codigo: 'basico' };

/** Superadmin de la plataforma: todas las empresas con su plan y su suscripción, y la
 * configuración de los planes (los límites del enunciado son los valores iniciales). */
@Component({
  selector: 'app-panel-plataforma',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './panel-plataforma.html',
  styleUrl: './panel-plataforma.scss',
})
export class PanelPlataforma implements OnInit {
  readonly plataforma = inject(PlataformaService);

  readonly tiendas = signal<TiendaAdmin[]>([]);
  readonly planes = signal<Plan[]>([]);
  readonly pestana = signal<'empresas' | 'planes'>('empresas');
  readonly mensaje = signal<string | null>(null);
  readonly error = signal<string | null>(null);
  readonly ocupado = signal<string | null>(null);
  readonly funciones = FUNCIONES_PLAN;

  readonly resumen = computed(() => {
    const tiendas = this.tiendas();
    return {
      total: tiendas.length,
      activas: tiendas.filter((t) => t.estado === 'activa' && t.estado_suscripcion === 'activa').length,
      porPlan: this.planes().map((p) => ({ nombre: p.nombre, cantidad: tiendas.filter((t) => t.plan_codigo === p.codigo).length })),
    };
  });

  correo = '';
  password = '';
  alta: AltaEmpresa = { ...ALTA_VACIA };
  mostrarAlta = false;

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
    this.plataforma.planes().subscribe((p) => this.planes.set(p));
  }

  urlDe(tienda: TiendaAdmin): string {
    return `/t/${tienda.slug}/`;
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

  guardarPlan(plan: Plan): void {
    const { nombre, descripcion, precio_mensual, max_sucursales, max_prendas, max_personal } = plan;
    const funciones = Object.fromEntries(this.funciones.map((f) => [f.clave, plan[f.clave]])) as Partial<FuncionesPlan>;
    this.ocupado.set(`plan-${plan.codigo}`);
    this.error.set(null);
    this.plataforma
      .configurarPlan(plan.codigo, { nombre, descripcion, precio_mensual, max_sucursales, max_prendas, max_personal, ...funciones })
      .subscribe({
        next: () => {
          this.ocupado.set(null);
          this.mensaje.set(`Plan ${plan.nombre} guardado: rige desde ahora para todas sus empresas.`);
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
