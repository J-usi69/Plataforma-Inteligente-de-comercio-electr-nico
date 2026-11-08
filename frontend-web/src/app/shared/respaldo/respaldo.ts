import { CommonModule } from '@angular/common';
import { Component, computed, effect, input, output, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Restauracion } from '../../core/models/tienda.model';
import { FuenteRespaldo } from '../../core/services/fuentes';
import { descargar, detalleDelError, hoyISO } from '../../core/utils/descargas';

/** Nombres legibles de las tablas que más se miran en el resumen de una restauración. */
const TABLAS: Record<string, string> = {
  tienda: 'Empresas',
  plan: 'Planes',
  suscripcion: 'Suscripciones',
  usuario: 'Cuentas de usuario',
  rol: 'Roles',
  personal: 'Personal',
  sucursal: 'Sucursales',
  prenda: 'Prendas',
  variante_prenda: 'Variantes (talla y color)',
  inventario_sucursal: 'Existencias',
  venta: 'Ventas',
  reserva: 'Reservas',
  proveedor: 'Proveedores',
  bitacora: 'Registros de bitácora',
};

/** Las tablas principales del resumen, en el orden de TABLAS, con su cantidad de filas. */
export function resumenDeTablas(tablas: Record<string, number>): { nombre: string; filas: number }[] {
  return Object.entries(TABLAS)
    .filter(([tabla]) => tabla in tablas)
    .map(([tabla, nombre]) => ({ nombre, filas: tablas[tabla] }));
}

/** Respaldo y restauración (característica 6). Para una empresa (su administrador, o el
 * superadmin eligiendo la empresa) o para el sistema completo (superadmin). Antes de restaurar se
 * verifica el archivo y se muestra qué va a pasar; la restauración pide confirmación. */
@Component({
  selector: 'app-respaldo',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './respaldo.html',
  styleUrl: './respaldo.scss',
})
export class Respaldo {
  readonly fuente = input.required<FuenteRespaldo>();
  readonly titulo = input('Respaldo y restauración');
  readonly descripcion = input('');
  readonly alcance = input<'empresa' | 'sistema'>('empresa');
  /** Para el nombre del archivo: respaldo_<prefijo>_<fecha>.json.gz */
  readonly prefijoArchivo = input('empresa');

  readonly fallo = output<{ status?: number; error?: { detail?: unknown } }>();
  /** Se restauró de verdad: la pantalla que lo contiene debería recargar sus datos. */
  readonly restaurado = output<Restauracion>();

  readonly ocupado = signal<string | null>(null);
  readonly error = signal<string | null>(null);
  readonly mensaje = signal<string | null>(null);
  readonly archivo = signal<File | null>(null);
  readonly vista = signal<Restauracion | null>(null);
  readonly tablas = computed(() => resumenDeTablas(this.vista()?.tablas ?? {}));

  confirmado = false;

  constructor() {
    // Si cambia la empresa elegida, lo verificado para la anterior ya no vale
    effect(() => {
      this.fuente();
      this.reiniciar();
    });
  }

  private reiniciar(): void {
    this.archivo.set(null);
    this.vista.set(null);
    this.confirmado = false;
    this.error.set(null);
    this.mensaje.set(null);
  }

  descargar(): void {
    this.error.set(null);
    this.mensaje.set(null);
    this.ocupado.set('descargar');
    this.fuente()
      .descargar()
      .subscribe({
        next: (contenido) => {
          this.ocupado.set(null);
          const nombre = `respaldo_${this.prefijoArchivo()}_${hoyISO()}.json.gz`;
          descargar(contenido, nombre);
          this.mensaje.set(`Se descargó ${nombre}. Guardalo en un lugar seguro: tiene los datos y las contraseñas cifradas de los usuarios.`);
        },
        error: (err) => this.manejar(err, 'No se pudo generar el respaldo.'),
      });
  }

  elegir(evento: Event): void {
    const entrada = evento.target as HTMLInputElement;
    this.reiniciar();
    this.archivo.set(entrada.files?.[0] ?? null);
  }

  /** Simula la restauración en el servidor (y la deshace) para mostrar qué cambiaría. */
  verificar(): void {
    const archivo = this.archivo();
    if (!archivo) {
      this.error.set('Elegí el archivo .json.gz del respaldo.');
      return;
    }
    this.error.set(null);
    this.mensaje.set(null);
    this.vista.set(null);
    this.confirmado = false;
    this.ocupado.set('verificar');
    this.fuente()
      .restaurar(archivo, true)
      .subscribe({
        next: (vista) => {
          this.ocupado.set(null);
          this.vista.set(vista);
        },
        error: (err) => this.manejar(err, 'No se pudo verificar el respaldo.'),
      });
  }

  restaurar(): void {
    const archivo = this.archivo();
    if (!archivo || !this.vista() || !this.confirmado) return;
    this.error.set(null);
    this.ocupado.set('restaurar');
    this.fuente()
      .restaurar(archivo, false)
      .subscribe({
        next: (resultado) => {
          this.ocupado.set(null);
          this.vista.set(null);
          this.archivo.set(null);
          this.confirmado = false;
          this.mensaje.set(
            `Listo: se restauraron ${resultado.filas} registros del respaldo del ${this.fecha(resultado.respaldo_del)}.` +
              (resultado.usuarios_desactivados ? ` ${resultado.usuarios_desactivados} cuenta(s) creadas después quedaron desactivadas.` : '') +
              (resultado.empresas_suspendidas ? ` ${resultado.empresas_suspendidas} empresa(s) dadas de alta después quedaron suspendidas.` : ''),
          );
          this.restaurado.emit(resultado);
        },
        error: (err) => this.manejar(err, 'No se pudo restaurar el respaldo. No se cambió nada.'),
      });
  }

  fecha(iso: string | null): string {
    if (!iso) return '-';
    const fecha = new Date(iso);
    return Number.isNaN(fecha.getTime()) ? iso : fecha.toLocaleString('es-BO', { dateStyle: 'short', timeStyle: 'short' });
  }

  private manejar(err: { status?: number; error?: unknown }, porDefecto: string): void {
    this.ocupado.set(null);
    if (err?.status === 401) {
      this.fallo.emit(err as { status?: number });
      return;
    }
    detalleDelError(err, porDefecto).then((texto) => this.error.set(texto));
  }
}
