import { CommonModule } from '@angular/common';
import { Component, DestroyRef, OnInit, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { Subject, debounceTime, distinctUntilChanged, of, switchMap } from 'rxjs';
import { FUNCIONES_PLAN, Plan } from '../../../core/models/tienda.model';
import { PlataformaService } from '../../../core/services/plataforma.service';

/** Texto libre -> dirección válida para la URL (misma regla que el backend: a-z, 0-9 y guiones). */
export function aDireccion(texto: string): string {
  return texto
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 40);
}

/** Alta pública de una empresa en la plataforma: crea la tienda con su administrador y el plan
 * elegido (primer mes con pago simulado) y entra directo a su panel. */
@Component({
  selector: 'app-registro-tienda',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './registro-tienda.html',
  styleUrl: './registro-tienda.scss',
})
export class RegistroTienda implements OnInit {
  private readonly plataforma = inject(PlataformaService);
  private readonly destroyRef = inject(DestroyRef);

  readonly planes = signal<Plan[]>([]);
  readonly disponibilidad = signal<{ disponible: boolean; motivo: string | null } | null>(null);
  readonly enviando = signal(false);
  readonly error = signal<string | null>(null);
  readonly funciones = FUNCIONES_PLAN;
  readonly origen = window.location.origin;

  nombre = '';
  slug = '';
  correo = '';
  password = '';
  planCodigo = 'basico';
  private slugEditadoAMano = false;
  private readonly cambiosDeSlug = new Subject<string>();

  ngOnInit(): void {
    this.plataforma.planes().subscribe((planes) => this.planes.set(planes));
    this.cambiosDeSlug
      .pipe(
        debounceTime(350),
        distinctUntilChanged(),
        switchMap((slug) => (slug.length >= 3 ? this.plataforma.disponible(slug) : of(null))),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((disponibilidad) => this.disponibilidad.set(disponibilidad));
  }

  alCambiarNombre(): void {
    if (!this.slugEditadoAMano) {
      this.slug = aDireccion(this.nombre);
      this.cambiosDeSlug.next(this.slug);
    }
  }

  alCambiarSlug(): void {
    this.slugEditadoAMano = true;
    this.slug = aDireccion(this.slug);
    this.cambiosDeSlug.next(this.slug);
  }

  async crear(): Promise<void> {
    if (this.disponibilidad()?.disponible === false) {
      return;
    }
    this.enviando.set(true);
    this.error.set(null);
    this.plataforma
      .registrar({
        nombre_tienda: this.nombre.trim(),
        slug: this.slug,
        correo: this.correo.trim(),
        password: this.password,
        plan_codigo: this.planCodigo,
      })
      .subscribe({
        next: async (registro) => {
          try {
            await this.plataforma.abrirSesionEnEmpresa(registro);
          } finally {
            // Recarga completa: la app arranca dentro de la empresa nueva (su marca, su sesión)
            window.location.href = `/t/${registro.slug}/admin/plan`;
          }
        },
        error: (err) => {
          this.enviando.set(false);
          const detalle = err?.error?.detail;
          this.error.set(
            Array.isArray(detalle)
              ? 'Revisá los datos: el correo debe ser válido y la contraseña tener al menos 8 caracteres.'
              : (detalle ?? 'No se pudo crear la empresa. Probá de nuevo.'),
          );
        },
      });
  }
}
