import { CommonModule } from '@angular/common';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute } from '@angular/router';
import { forkJoin } from 'rxjs';
import { Prenda, VariantePrenda } from '../../../core/models/user.model';
import { BusinessService } from '../../../core/services/business.service';
import { ArMediapipe, encuadreDeZona, zonaDeCategoria } from '../ar-mediapipe/ar-mediapipe';

// Página del probador AR (MediaPipe) a pantalla completa, pensada para abrirse dentro de la app
// móvil (WebView): /probador-ar?prenda=4&variante=3&embed=1
@Component({
  selector: 'app-probador-ar',
  standalone: true,
  imports: [CommonModule, FormsModule, ArMediapipe],
  template: `
    <div class="probador">
      <div *ngIf="error()" class="probador-mensaje">
        <div style="font-size: 2.2rem;">⚠️</div>
        <p>{{ error() }}</p>
      </div>

      <div *ngIf="!error() && !prenda()" class="probador-mensaje">
        <div style="font-size: 2.2rem;">⏳</div>
        <p>Cargando prenda...</p>
      </div>

      <ng-container *ngIf="prenda() as p">
        <div class="probador-cabecera">
          <div class="probador-titulo">{{ p.nombre }}</div>
          <select
            *ngIf="variantes().length > 1"
            [ngModel]="varianteId()"
            (ngModelChange)="varianteId.set($event)"
            class="probador-select"
          >
            <option *ngFor="let v of variantes()" [ngValue]="v.id">{{ v.color_nombre }} · Talla {{ v.talla_nombre }}</option>
          </select>
        </div>

        <div *ngIf="!imagenReferencia()" class="probador-mensaje">
          <div style="font-size: 2.2rem;">🖼️</div>
          <p>Esta prenda todavía no tiene una foto de referencia configurada.</p>
        </div>

        <ng-container *ngIf="imagenReferencia() as url">
          <p class="probador-ayuda">Apoya el celular y aléjate hasta que se vea {{ encuadre() }}.</p>
          <app-ar-mediapipe
            [imagenUrl]="url"
            [zona]="zona()"
            altoMaximo="calc(100vh - 150px)"
            [permitirCaptura]="!embebido"
          ></app-ar-mediapipe>
        </ng-container>
      </ng-container>
    </div>
  `,
  styles: [`
    .probador { max-width: 720px; margin: 0 auto; padding: 0.75rem; }
    .probador-cabecera { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 0.5rem; margin-bottom: 0.4rem; }
    .probador-titulo { font-weight: 800; font-size: 1.05rem; color: #0f172a; }
    .probador-select { padding: 0.45rem 0.6rem; border-radius: 8px; border: 1px solid #cbd5e1; font-weight: 600; font-size: 0.85rem; }
    .probador-ayuda { font-size: 0.8rem; color: #475569; margin: 0 0 0.5rem; }
    .probador-mensaje { text-align: center; padding: 3rem 1rem; color: #475569; }
  `],
})
export class ProbadorAr implements OnInit {
  private readonly business = inject(BusinessService);
  private readonly route = inject(ActivatedRoute);

  prenda = signal<Prenda | null>(null);
  variantes = signal<VariantePrenda[]>([]);
  varianteId = signal<number | null>(null);
  error = signal<string | null>(null);
  embebido = false;

  zona = computed(() => zonaDeCategoria(this.prenda()?.categoria_nombre));
  encuadre = computed(() => encuadreDeZona(this.zona()));
  imagenReferencia = computed(() => {
    const variante = this.variantes().find((v) => v.id === this.varianteId());
    return variante?.imagen_url || this.prenda()?.imagen_url || null;
  });

  ngOnInit(): void {
    const params = this.route.snapshot.queryParamMap;
    const prendaId = Number(params.get('prenda'));
    const varianteInicial = Number(params.get('variante')) || null;
    this.embebido = params.get('embed') === '1';

    if (!prendaId) {
      this.error.set('No se indicó qué prenda probar.');
      return;
    }

    forkJoin({
      prenda: this.business.getPrenda(prendaId),
      variantes: this.business.getVariantes(prendaId),
    }).subscribe({
      next: ({ prenda, variantes }) => {
        const activas = variantes.filter((v) => v.estado);
        this.variantes.set(activas);
        this.varianteId.set(
          varianteInicial && activas.some((v) => v.id === varianteInicial) ? varianteInicial : activas[0]?.id ?? null
        );
        this.prenda.set(prenda);
      },
      error: () => this.error.set('No se pudo cargar la prenda. Revisa tu conexión e inténtalo de nuevo.'),
    });
  }
}
