import { CommonModule } from '@angular/common';
import { Component, computed, effect, input, output, signal, untracked } from '@angular/core';
import { FormsModule } from '@angular/forms';
import {
  CatalogoReporte,
  Celda,
  CriterioReporte,
  FormatoReporte,
  OPERADORES_CRITERIO,
  OpcionesReporte,
  ReporteIAPlataforma,
  ReportePlataforma,
} from '../../core/models/tienda.model';
import { FuenteReportes } from '../../core/services/fuentes';
import { descargar, detalleDelError, hoyISO } from '../../core/utils/descargas';

interface ColumnaElegible {
  nombre: string;
  elegida: boolean;
}

/** Mueve un elemento de la lista una posición (delta -1 sube, +1 baja); fuera de rango no cambia nada. */
export function mover<T>(lista: T[], indice: number, delta: number): T[] {
  const destino = indice + delta;
  if (destino < 0 || destino >= lista.length) return lista;
  const copia = [...lista];
  [copia[indice], copia[destino]] = [copia[destino], copia[indice]];
  return copia;
}

/** Reportes personalizables (característica 5), del superadmin o de una empresa según la fuente:
 * el usuario elige el reporte, qué columnas ver y en qué orden, los criterios de selección, el
 * período y el orden, y lo exporta a Excel, PDF o HTML o lo envía por correo. También lo puede
 * pedir con palabras, escritas o dictadas: la IA lo traduce a esas mismas opciones. */
@Component({
  selector: 'app-reportes-personalizados',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './reportes-personalizados.html',
  styleUrl: './reportes-personalizados.scss',
})
export class ReportesPersonalizados {
  readonly fuente = input.required<FuenteReportes>();
  /** El plan incluye los reportes con IA (si no, se muestra avisoSinIA en lugar del cuadro). */
  readonly iaDisponible = input(true);
  readonly avisoSinIA = input<string | null>(null);
  readonly ejemplos = input<string[]>([]);
  /** Prefijo de los archivos descargados (p. ej. "plataforma" o el slug de la empresa). */
  readonly prefijoArchivos = input('reporte');

  readonly fallo = output<{ status?: number; error?: { detail?: unknown } }>();

  readonly catalogo = signal<CatalogoReporte[]>([]);
  readonly tipo = signal<string>('');
  readonly definicion = computed(() => this.catalogo().find((r) => r.tipo === this.tipo()) ?? null);
  readonly columnas = signal<ColumnaElegible[]>([]);
  readonly elegidas = computed(() => this.columnas().filter((c) => c.elegida).map((c) => c.nombre));
  readonly reporte = signal<ReportePlataforma | null>(null);
  readonly ocupado = signal<string | null>(null);
  readonly error = signal<string | null>(null);
  readonly mensaje = signal<string | null>(null);
  readonly operadores = OPERADORES_CRITERIO;
  readonly dictando = signal(false);
  readonly interpretacion = signal<string | null>(null);

  pedido = '';

  criterios: CriterioReporte[] = [];
  desde = '';
  hasta = '';
  orden = '';
  descendente = false;
  destinatario = '';
  formatoCorreo: FormatoReporte = 'pdf';

  constructor() {
    // Cada vez que cambia la fuente (al entrar, o si el panel la cambia) se carga su catálogo
    effect(() => {
      const fuente = this.fuente();
      untracked(() => this.cargarCatalogo(fuente));
    });
  }

  private cargarCatalogo(fuente: FuenteReportes): void {
    fuente.catalogo().subscribe({
      next: (catalogo) => {
        this.catalogo.set(catalogo);
        if (catalogo.length) this.elegirTipo(catalogo[0].tipo);
      },
      error: (err) => this.fallo.emit(err),
    });
  }

  /** Reporte por comando: la IA interpreta el pedido y el resultado se carga en el constructor para
   * ajustarlo o exportarlo como cualquier otro. */
  pedirConIA(texto = this.pedido): void {
    const pedido = texto.trim();
    if (pedido.length < 3) {
      this.error.set('Escribí o dictá qué reporte necesitás.');
      return;
    }
    this.pedido = pedido;
    this.error.set(null);
    this.mensaje.set(null);
    this.ocupado.set('ia');
    this.fuente()
      .reporteIA(pedido)
      .subscribe({
        next: (respuesta) => {
          this.ocupado.set(null);
          this.aplicar(respuesta);
        },
        error: (err) => this.manejar(err),
      });
  }

  /** Dictado por voz (Web Speech API del navegador): al terminar de hablar se genera el reporte. */
  dictar(): void {
    const ventana = window as unknown as Record<string, unknown>;
    const Reconocimiento = ventana['SpeechRecognition'] ?? ventana['webkitSpeechRecognition'];
    if (!Reconocimiento) {
      this.error.set('Este navegador no permite dictar por voz. Probá con Chrome o Edge, o escribí el pedido.');
      return;
    }
    const reconocimiento = new (Reconocimiento as new () => ReconocimientoDeVoz)();
    reconocimiento.lang = 'es-BO';
    reconocimiento.interimResults = false;
    reconocimiento.continuous = false;
    reconocimiento.onresult = (evento) => {
      const texto = evento.results[0][0].transcript;
      this.dictando.set(false);
      this.pedirConIA(texto);
    };
    reconocimiento.onerror = () => {
      this.dictando.set(false);
      this.error.set('No se pudo escuchar el pedido. Revisá el permiso del micrófono e intentá de nuevo.');
    };
    reconocimiento.onend = () => this.dictando.set(false);
    this.error.set(null);
    this.dictando.set(true);
    reconocimiento.start();
  }

  private aplicar({ opciones, reporte }: ReporteIAPlataforma): void {
    const definicion = this.catalogo().find((r) => r.tipo === opciones.tipo);
    if (!definicion) return;
    this.tipo.set(opciones.tipo);
    const elegidas = opciones.columnas?.length ? opciones.columnas : definicion.columnas;
    this.columnas.set([
      ...elegidas.map((nombre) => ({ nombre, elegida: true })),
      ...definicion.columnas.filter((c) => !elegidas.includes(c)).map((nombre) => ({ nombre, elegida: false })),
    ]);
    this.criterios = opciones.criterios.map((c) => ({ ...c }));
    this.desde = opciones.desde ?? '';
    this.hasta = opciones.hasta ?? '';
    this.orden = opciones.orden ?? definicion.orden;
    this.descendente = opciones.descendente ?? definicion.descendente;
    this.reporte.set(reporte);
    this.interpretacion.set(`Interpretado como «${definicion.titulo}» · ${reporte.filtros}`);
  }

  /** Al cambiar de reporte se vuelve a sus valores por defecto: todas las columnas y su orden. */
  elegirTipo(tipo: string): void {
    const definicion = this.catalogo().find((r) => r.tipo === tipo);
    if (!definicion) return;
    this.tipo.set(tipo);
    this.columnas.set(definicion.columnas.map((nombre) => ({ nombre, elegida: true })));
    this.criterios = [];
    this.desde = '';
    this.hasta = '';
    this.orden = definicion.orden;
    this.descendente = definicion.descendente;
    this.reporte.set(null);
    this.interpretacion.set(null);
    this.error.set(null);
    this.mensaje.set(null);
  }

  alternarColumna(indice: number): void {
    this.columnas.update((cs) => cs.map((c, i) => (i === indice ? { ...c, elegida: !c.elegida } : c)));
  }

  moverColumna(indice: number, delta: number): void {
    this.columnas.update((cs) => mover(cs, indice, delta));
  }

  agregarCriterio(): void {
    const columna = this.definicion()?.columnas[0] ?? '';
    this.criterios = [...this.criterios, { columna, operador: 'contiene', valor: '' }];
  }

  quitarCriterio(indice: number): void {
    this.criterios = this.criterios.filter((_, i) => i !== indice);
  }

  private opciones(): OpcionesReporte | null {
    if (!this.elegidas().length) {
      this.error.set('Elegí al menos una columna.');
      return null;
    }
    if (this.desde && this.hasta && this.desde > this.hasta) {
      this.error.set('La fecha "desde" es posterior a "hasta".');
      return null;
    }
    return {
      desde: this.desde || undefined,
      hasta: this.hasta || undefined,
      columnas: this.elegidas(),
      criterios: this.criterios,
      orden: this.orden || undefined,
      descendente: this.descendente,
    };
  }

  generar(): void {
    const opciones = this.preparar('generar');
    if (!opciones) return;
    this.fuente()
      .reporte(this.tipo(), opciones)
      .subscribe({
        next: (reporte) => {
          this.ocupado.set(null);
          this.reporte.set(reporte);
        },
        error: (err) => this.manejar(err),
      });
  }

  private nombreArchivo(formato: FormatoReporte): string {
    return `${this.prefijoArchivos()}_${this.tipo()}_${hoyISO()}.${formato === 'excel' ? 'xlsx' : formato}`;
  }

  exportar(formato: FormatoReporte): void {
    const opciones = this.preparar(formato);
    if (!opciones) return;
    this.fuente()
      .exportar(this.tipo(), formato, opciones)
      .subscribe({
        next: (archivo) => {
          this.ocupado.set(null);
          descargar(archivo, this.nombreArchivo(formato));
        },
        error: (err) => this.manejar(err),
      });
  }

  enviar(): void {
    if (!/^\S+@\S+\.\S+$/.test(this.destinatario.trim())) {
      this.error.set('Ingresá un correo válido para enviar el reporte.');
      return;
    }
    const opciones = this.preparar('correo');
    if (!opciones) return;
    this.fuente()
      .enviar(this.tipo(), this.destinatario.trim(), this.formatoCorreo, opciones)
      .subscribe({
        next: () => {
          this.ocupado.set(null);
          this.mensaje.set(`Reporte enviado a ${this.destinatario.trim()}.`);
        },
        error: (err) => (err?.status === 503 ? this.enviarDesdeElEquipo(opciones) : this.manejar(err)),
      });
  }

  /** Sin correo configurado en el servidor: se descarga el archivo y se abre el programa de correo
   * del usuario con el asunto y el texto listos, para adjuntarlo y enviarlo. */
  private enviarDesdeElEquipo(opciones: OpcionesReporte): void {
    const formato = this.formatoCorreo;
    this.fuente()
      .exportar(this.tipo(), formato, opciones)
      .subscribe({
        next: (archivo) => {
          this.ocupado.set(null);
          const nombre = this.nombreArchivo(formato);
          descargar(archivo, nombre);
          const titulo = this.definicion()?.titulo ?? 'Reporte';
          const actual = this.reporte();
          const resumen = actual?.tipo === this.tipo() ? `\n\n${actual.narrativa}\n${actual.filtros}` : '';
          const cuerpo = `Te envío el reporte "${titulo}" de FashionStore.${resumen}\n\nAdjunto: ${nombre}`;
          window.location.href = `mailto:${encodeURIComponent(this.destinatario.trim())}?subject=${encodeURIComponent(`FashionStore · ${titulo}`)}&body=${encodeURIComponent(cuerpo)}`;
          this.mensaje.set(`Se descargó ${nombre} y se abrió tu programa de correo: adjuntá el archivo y envialo.`);
        },
        error: (err) => this.manejar(err),
      });
  }

  esMonto(columna: string): boolean {
    return this.reporte()?.columnas_monto.includes(columna) ?? false;
  }

  esNumero(valor: Celda): boolean {
    return typeof valor === 'number';
  }

  private preparar(accion: string): OpcionesReporte | null {
    this.error.set(null);
    this.mensaje.set(null);
    const opciones = this.opciones();
    if (opciones) this.ocupado.set(accion);
    return opciones;
  }

  private manejar(err: { status?: number; error?: unknown }): void {
    this.ocupado.set(null);
    if (err?.status === 401 || err?.status === 403) {
      this.fallo.emit(err as { status?: number });
      return;
    }
    detalleDelError(err, 'No se pudo generar el reporte.').then((texto) => this.error.set(texto));
  }
}

/** Lo mínimo de la Web Speech API que se usa (no viene tipada en TypeScript). */
interface ReconocimientoDeVoz {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  onresult: (evento: { results: { [i: number]: { [j: number]: { transcript: string } } } }) => void;
  onerror: () => void;
  onend: () => void;
  start(): void;
}
