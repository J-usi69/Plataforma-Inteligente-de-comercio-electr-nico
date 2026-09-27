import { CommonModule } from '@angular/common';
import {
  AfterViewInit,
  Component,
  ElementRef,
  Input,
  OnChanges,
  OnDestroy,
  SimpleChanges,
  ViewChild,
  signal,
} from '@angular/core';
import type { ImageSegmenter, NormalizedLandmark, PoseLandmarker } from '@mediapipe/tasks-vision';

const WASM_URL = 'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@1.0.1/wasm';
const MODELO_POSE =
  'https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task';
const MODELO_SEGMENTACION =
  'https://storage.googleapis.com/mediapipe-models/image_segmenter/selfie_multiclass_256x256/float32/latest/selfie_multiclass_256x256.tflite';
// Clases de selfie_multiclass: 0 fondo, 1 pelo, 2 piel cuerpo, 3 piel cara, 4 ropa, 5 otros
const CLASE_ROPA = 4;

export type ZonaCorporal = 'superior' | 'inferior' | 'vestido' | 'calzado';
type EstadoAr = 'cargando' | 'listo' | 'sin-camara' | 'error';

interface Modelos {
  pose: PoseLandmarker;
  segmentador: ImageSegmenter;
}

interface Caja {
  cx: number;
  cy: number;
  w: number;
  h: number;
  ang: number;
}

// Los modelos pesan ~22 MB en total: se cargan una sola vez por sesión del navegador.
let modelosPromise: Promise<Modelos> | null = null;

function cargarModelos(): Promise<Modelos> {
  if (!modelosPromise) {
    modelosPromise = (async () => {
      // Import dinámico: la librería solo se descarga cuando alguien abre el modo AR
      const { FilesetResolver, ImageSegmenter, PoseLandmarker } = await import('@mediapipe/tasks-vision');
      const fileset = await FilesetResolver.forVisionTasks(WASM_URL);
      const crearPose = (delegate: 'GPU' | 'CPU') =>
        PoseLandmarker.createFromOptions(fileset, {
          baseOptions: { modelAssetPath: MODELO_POSE, delegate },
          runningMode: 'VIDEO',
          numPoses: 1,
        });
      const pose = await crearPose('GPU').catch(() => crearPose('CPU'));
      const segmentador = await ImageSegmenter.createFromOptions(fileset, {
        baseOptions: { modelAssetPath: MODELO_SEGMENTACION, delegate: 'CPU' },
        runningMode: 'IMAGE',
        outputCategoryMask: true,
        outputConfidenceMasks: false,
      });
      return { pose, segmentador };
    })().catch((err) => {
      modelosPromise = null;
      throw err;
    });
  }
  return modelosPromise;
}

function cargarImagen(url: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error('No se pudo cargar la foto de la prenda'));
    img.src = url;
  });
}

// Recorta la prenda de su foto de catálogo: primero con el segmentador de MediaPipe (clase
// "ropa", sirve cuando la foto muestra a una persona usándola); si casi no detecta ropa (foto
// de producto sin persona), cae a quitar el color de fondo tomado de las esquinas.
function recortarPrenda(img: HTMLImageElement, segmentador: ImageSegmenter): { canvas: HTMLCanvasElement; metodo: string } {
  const escala = Math.min(1, 512 / Math.max(img.naturalWidth, img.naturalHeight));
  const w = Math.round(img.naturalWidth * escala);
  const h = Math.round(img.naturalHeight * escala);
  const canvas = document.createElement('canvas');
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext('2d', { willReadFrequently: true })!;
  ctx.drawImage(img, 0, 0, w, h);
  const datos = ctx.getImageData(0, 0, w, h);
  const px = datos.data;

  let metodo = 'fondo por color';
  const resultado = segmentador.segment(canvas);
  const mascara = resultado.categoryMask;
  if (mascara) {
    const clases = mascara.getAsUint8Array();
    let ropa = 0;
    for (let i = 0; i < clases.length; i++) if (clases[i] === CLASE_ROPA) ropa++;
    if (ropa / clases.length > 0.03) {
      metodo = 'segmentación de ropa (MediaPipe)';
      for (let y = 0; y < h; y++) {
        const my = Math.min(mascara.height - 1, Math.floor((y * mascara.height) / h));
        for (let x = 0; x < w; x++) {
          const mx = Math.min(mascara.width - 1, Math.floor((x * mascara.width) / w));
          if (clases[my * mascara.width + mx] !== CLASE_ROPA) px[(y * w + x) * 4 + 3] = 0;
        }
      }
    }
  }
  resultado.close();

  if (metodo === 'fondo por color') {
    const muestra = (x0: number, y0: number) => {
      let r = 0, g = 0, b = 0, n = 0;
      for (let y = y0; y < y0 + 8; y++)
        for (let x = x0; x < x0 + 8; x++) {
          const i = (y * w + x) * 4;
          r += px[i]; g += px[i + 1]; b += px[i + 2]; n++;
        }
      return [r / n, g / n, b / n];
    };
    const esquinas = [muestra(0, 0), muestra(w - 8, 0), muestra(0, h - 8), muestra(w - 8, h - 8)];
    const fondo = [0, 1, 2].map((c) => esquinas.reduce((s, e) => s + e[c], 0) / 4);
    for (let i = 0; i < px.length; i += 4) {
      const d = Math.hypot(px[i] - fondo[0], px[i + 1] - fondo[1], px[i + 2] - fondo[2]);
      if (d < 38) px[i + 3] = 0;
      else if (d < 70) px[i + 3] = Math.round(((d - 38) / 32) * 255);
    }
  }
  ctx.putImageData(datos, 0, 0);

  // Recortar al rectángulo que realmente tiene prenda, para que se ajuste bien al cuerpo.
  let minX = w, minY = h, maxX = 0, maxY = 0;
  for (let y = 0; y < h; y++)
    for (let x = 0; x < w; x++)
      if (px[(y * w + x) * 4 + 3] > 40) {
        if (x < minX) minX = x;
        if (x > maxX) maxX = x;
        if (y < minY) minY = y;
        if (y > maxY) maxY = y;
      }
  if (maxX <= minX || maxY <= minY) return { canvas, metodo };
  const recorte = document.createElement('canvas');
  recorte.width = maxX - minX + 1;
  recorte.height = maxY - minY + 1;
  recorte.getContext('2d')!.drawImage(canvas, minX, minY, recorte.width, recorte.height, 0, 0, recorte.width, recorte.height);
  return { canvas: recorte, metodo };
}

@Component({
  selector: 'app-ar-mediapipe',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="ar-contenedor">
      <video #video autoplay playsinline muted class="ar-video-oculto"></video>
      <canvas #lienzo class="ar-lienzo" [class.ar-lienzo-visible]="estado() === 'listo'"></canvas>

      <div *ngIf="estado() === 'cargando'" class="ar-estado">
        <div style="font-size: 2.2rem;">⏳</div>
        <p><strong>Cargando MediaPipe...</strong></p>
        <p style="font-size: 0.8rem;">La primera vez descarga ~22 MB de modelos; después queda en caché.</p>
      </div>
      <div *ngIf="estado() === 'sin-camara'" class="ar-estado">
        <div style="font-size: 2.2rem;">📷</div>
        <p>No se pudo acceder a la cámara. El modo AR en vivo necesita la cámara encendida.</p>
      </div>
      <div *ngIf="estado() === 'error'" class="ar-estado" style="color: #dc2626;">
        <div style="font-size: 2.2rem;">⚠️</div>
        <p>{{ mensajeError() }}</p>
      </div>
    </div>

    <div *ngIf="estado() === 'listo'" class="ar-barra">
      <span>{{ fps() }} FPS · {{ personaDetectada() ? 'persona detectada' : 'buscando persona...' }} · recorte: {{ metodoRecorte() }}</span>
      <button class="btn btn-secondary btn-sm" (click)="capturar()">📸 Capturar</button>
    </div>
  `,
  styles: [`
    .ar-contenedor { position: relative; min-height: 220px; }
    .ar-video-oculto { position: absolute; width: 1px; height: 1px; opacity: 0; pointer-events: none; }
    .ar-lienzo { display: none; width: 100%; max-height: 420px; border-radius: 12px; background: #0f172a; object-fit: contain; }
    .ar-lienzo-visible { display: block; }
    .ar-estado { text-align: center; padding: 2rem 1rem; color: #475569; }
    .ar-barra { display: flex; justify-content: space-between; align-items: center; gap: 0.5rem; margin-top: 0.6rem; font-size: 0.78rem; color: #64748b; }
  `],
})
export class ArMediapipe implements AfterViewInit, OnChanges, OnDestroy {
  @Input() imagenUrl: string | null = null;
  @Input() zona: ZonaCorporal = 'superior';

  @ViewChild('video') videoRef!: ElementRef<HTMLVideoElement>;
  @ViewChild('lienzo') lienzoRef!: ElementRef<HTMLCanvasElement>;

  estado = signal<EstadoAr>('cargando');
  mensajeError = signal('');
  fps = signal(0);
  personaDetectada = signal(false);
  metodoRecorte = signal('-');

  private modelos: Modelos | null = null;
  private prenda: HTMLCanvasElement | null = null;
  private stream: MediaStream | null = null;
  private raf = 0;
  private activo = false;
  private caja: Caja | null = null;
  private cuadros = 0;
  private inicioFps = 0;

  async ngAfterViewInit(): Promise<void> {
    this.activo = true;
    try {
      this.stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'user', width: { ideal: 640 }, height: { ideal: 480 } },
        audio: false,
      });
    } catch {
      this.estado.set('sin-camara');
      return;
    }
    const video = this.videoRef.nativeElement;
    video.srcObject = this.stream;
    await video.play().catch(() => undefined);

    try {
      this.modelos = await cargarModelos();
      await this.prepararPrenda();
    } catch (err) {
      this.mostrarError(err instanceof Error ? err.message : 'No se pudo iniciar MediaPipe');
      return;
    }
    if (!this.activo) return;
    this.estado.set('listo');
    this.inicioFps = performance.now();
    this.raf = requestAnimationFrame(() => this.cuadro());
  }

  ngOnChanges(changes: SimpleChanges): void {
    if ((changes['imagenUrl'] || changes['zona']) && this.modelos) {
      this.caja = null;
      this.prepararPrenda().catch((err) => this.mostrarError(err instanceof Error ? err.message : String(err)));
    }
  }

  ngOnDestroy(): void {
    this.activo = false;
    cancelAnimationFrame(this.raf);
    this.stream?.getTracks().forEach((t) => t.stop());
  }

  private async prepararPrenda(): Promise<void> {
    if (!this.imagenUrl || !this.modelos) {
      this.prenda = null;
      return;
    }
    const img = await cargarImagen(this.imagenUrl);
    const { canvas, metodo } = recortarPrenda(img, this.modelos.segmentador);
    this.prenda = canvas;
    this.metodoRecorte.set(metodo);
  }

  private cuadro(): void {
    if (!this.activo || !this.modelos) return;
    const video = this.videoRef.nativeElement;
    const lienzo = this.lienzoRef.nativeElement;

    if (video.readyState >= 2 && video.videoWidth) {
      const W = video.videoWidth;
      const H = video.videoHeight;
      if (lienzo.width !== W) lienzo.width = W;
      if (lienzo.height !== H) lienzo.height = H;
      const ctx = lienzo.getContext('2d')!;

      // Vista espejo, como un probador real
      ctx.save();
      ctx.scale(-1, 1);
      ctx.drawImage(video, -W, 0, W, H);
      ctx.restore();

      const resultado = this.modelos.pose.detectForVideo(video, performance.now());
      const puntos = resultado.landmarks[0];
      this.personaDetectada.set(!!puntos);
      if (puntos && this.prenda) {
        const nueva = this.calcularCaja(puntos, W, H);
        if (nueva) {
          // Suavizado para que la prenda no tiemble entre cuadros
          const a = 0.35;
          this.caja = this.caja
            ? {
                cx: this.caja.cx + (nueva.cx - this.caja.cx) * a,
                cy: this.caja.cy + (nueva.cy - this.caja.cy) * a,
                w: this.caja.w + (nueva.w - this.caja.w) * a,
                h: this.caja.h + (nueva.h - this.caja.h) * a,
                ang: this.caja.ang + (nueva.ang - this.caja.ang) * a,
              }
            : nueva;
          const c = this.caja;
          ctx.save();
          ctx.translate(c.cx, c.cy);
          ctx.rotate(c.ang);
          ctx.drawImage(this.prenda, -c.w / 2, -c.h / 2, c.w, c.h);
          ctx.restore();
        }
      }

      this.cuadros++;
      const ahora = performance.now();
      if (ahora - this.inicioFps >= 1000) {
        this.fps.set(Math.round((this.cuadros * 1000) / (ahora - this.inicioFps)));
        this.cuadros = 0;
        this.inicioFps = ahora;
      }
    }
    this.raf = requestAnimationFrame(() => this.cuadro());
  }

  // Convierte los puntos del cuerpo (normalizados 0..1) en el rectángulo rotado donde va la
  // prenda. La x se invierte porque la imagen se muestra en espejo.
  private calcularCaja(lm: NormalizedLandmark[], W: number, H: number): Caja | null {
    const p = (i: number) => ({ x: (1 - lm[i].x) * W, y: lm[i].y * H, v: lm[i].visibility ?? 1 });
    const medio = (a: { x: number; y: number }, b: { x: number; y: number }) => ({ x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 });
    const dist = (a: { x: number; y: number }, b: { x: number; y: number }) => Math.hypot(a.x - b.x, a.y - b.y);
    const angulo = (a: { x: number; y: number }, b: { x: number; y: number }) => {
      const [izq, der] = a.x < b.x ? [a, b] : [b, a];
      return Math.atan2(der.y - izq.y, der.x - izq.x);
    };
    const visibles = (...idx: number[]) => idx.every((i) => p(i).v > 0.4);

    const hombroI = p(11), hombroD = p(12), caderaI = p(23), caderaD = p(24);
    const hombros = medio(hombroI, hombroD);
    const caderas = medio(caderaI, caderaD);

    switch (this.zona) {
      case 'superior': {
        if (!visibles(11, 12)) return null;
        const anchoHombros = dist(hombroI, hombroD);
        const torso = visibles(23, 24) ? dist(hombros, caderas) : anchoHombros * 1.3;
        const h = torso * 1.3;
        return { cx: hombros.x, cy: hombros.y + h * 0.4, w: anchoHombros * 1.9, h, ang: angulo(hombroI, hombroD) };
      }
      case 'vestido': {
        if (!visibles(11, 12, 25, 26)) return null;
        const rodillas = medio(p(25), p(26));
        const h = dist(hombros, rodillas) * 1.2;
        return { cx: hombros.x, cy: hombros.y + h * 0.45, w: dist(hombroI, hombroD) * 2.1, h, ang: angulo(hombroI, hombroD) };
      }
      case 'inferior': {
        if (!visibles(23, 24, 27, 28)) return null;
        const tobillos = medio(p(27), p(28));
        const h = dist(caderas, tobillos) * 1.12;
        return { cx: caderas.x, cy: caderas.y + h * 0.46, w: dist(caderaI, caderaD) * 2.6, h, ang: angulo(caderaI, caderaD) };
      }
      case 'calzado': {
        if (!visibles(27, 28)) return null;
        const tobI = p(27), tobD = p(28);
        const pies = medio(medio(tobI, tobD), medio(p(31), p(32)));
        const w = Math.max(dist(tobI, tobD) * 1.9, H * 0.12);
        const h = w * (this.prenda!.height / this.prenda!.width);
        return { cx: pies.x, cy: pies.y, w, h, ang: 0 };
      }
    }
  }

  capturar(): void {
    this.lienzoRef.nativeElement.toBlob((blob) => {
      if (!blob) return;
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = 'vestidor-mediapipe.png';
      a.click();
      URL.revokeObjectURL(a.href);
    }, 'image/png');
  }

  private mostrarError(mensaje: string): void {
    this.estado.set('error');
    this.mensajeError.set(mensaje);
  }
}
