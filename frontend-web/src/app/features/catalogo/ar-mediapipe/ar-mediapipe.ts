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
import type { DrawingUtils, ImageSegmenter, MPMask, NormalizedLandmark, PoseLandmarker } from '@mediapipe/tasks-vision';

const WASM_URL = 'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@1.0.1/wasm';
const MODELO_POSE =
  'https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task';
const MODELO_SEGMENTACION =
  'https://storage.googleapis.com/mediapipe-models/image_segmenter/selfie_multiclass_256x256/float32/latest/selfie_multiclass_256x256.tflite';
// Clases de selfie_multiclass: 0 fondo, 1 pelo, 2 piel cuerpo, 3 piel cara, 4 ropa, 5 otros
const CLASE_ROPA = 4;

// 'abrigo' es una prenda de arriba con manga larga: además del torso, las mangas siguen los brazos
export type ZonaCorporal = 'superior' | 'abrigo' | 'inferior' | 'vestido' | 'calzado';
type EstadoAr = 'cargando' | 'listo' | 'sin-camara' | 'error';

export function zonaDeCategoria(categoria?: string | null): ZonaCorporal {
  const nombre = (categoria || '').toLowerCase();
  if (nombre.includes('vestido')) return 'vestido';
  if (nombre.includes('pantal') || nombre.includes('jean')) return 'inferior';
  if (nombre.includes('calzado') || nombre.includes('zapat')) return 'calzado';
  if (nombre.includes('chaqueta') || nombre.includes('abrigo') || nombre.includes('blazer')) return 'abrigo';
  return 'superior';
}

// Qué parte del cuerpo tiene que verse en la cámara, para el texto de ayuda
export function encuadreDeZona(zona: ZonaCorporal): string {
  switch (zona) {
    case 'calzado':
      return 'todo tu cuerpo, incluidos los pies';
    case 'inferior':
      return 'de la cintura a los tobillos';
    case 'vestido':
      return 'de los hombros a las rodillas';
    default:
      return 'de los hombros a la cadera';
  }
}

interface Modelos {
  pose: PoseLandmarker;
  segmentador: ImageSegmenter;
  // Con la pose en GPU la silueta queda en una textura del lienzo WebGL de MediaPipe: se dibuja
  // ahí mismo con DrawingUtils (bajarla a la CPU no anda en muchos celulares). Si no hay GPU o
  // la silueta sale vacía, dibujoGpu es null y la pose corre en CPU.
  dibujoGpu: DrawingUtils | null;
  lienzoGpu: HTMLCanvasElement;
  crearPoseCpu: () => Promise<PoseLandmarker>;
}

// Punto del cuerpo ya pasado a píxeles del lienzo (en espejo si es la cámara frontal)
interface Punto {
  x: number;
  y: number;
  // Qué tan seguro está MediaPipe de que el punto se ve (0..1)
  v: number;
  // Visible y dentro de la imagen: fuera del cuadro MediaPipe igual estima el punto, pero mal
  ok: boolean;
}

// Pedazo de la foto de la prenda: x, y, ancho, alto
type Rect = [number, number, number, number];

const medio = (a: Punto, b: Punto): Punto => ({
  x: (a.x + b.x) / 2,
  y: (a.y + b.y) / 2,
  v: Math.min(a.v, b.v),
  ok: a.ok && b.ok,
});
const dist = (a: Punto, b: Punto) => Math.hypot(a.x - b.x, a.y - b.y);

// Ejes del cuerpo a partir de dos puntos simétricos (hombros o caderas): `u` va de izquierda a
// derecha de la pantalla y `d` es su perpendicular hacia los pies.
function ejes(a: Punto, b: Punto) {
  const [izq, der] = a.x < b.x ? [a, b] : [b, a];
  const ancho = dist(izq, der) || 1;
  const u = { x: (der.x - izq.x) / ancho, y: (der.y - izq.y) / ancho };
  return { centro: medio(izq, der), ancho, u, d: { x: -u.y, y: u.x }, ang: Math.atan2(u.y, u.x) };
}

// Los modelos pesan ~22 MB en total: se cargan una sola vez por sesión del navegador.
let modelosPromise: Promise<Modelos> | null = null;

function cargarModelos(): Promise<Modelos> {
  if (!modelosPromise) {
    modelosPromise = (async () => {
      // Import dinámico: la librería solo se descarga cuando alguien abre el modo AR
      const { DrawingUtils, FilesetResolver, ImageSegmenter, PoseLandmarker } = await import('@mediapipe/tasks-vision');
      const fileset = await FilesetResolver.forVisionTasks(WASM_URL);
      const lienzoGpu = document.createElement('canvas');
      const crearPose = (delegate: 'GPU' | 'CPU') =>
        PoseLandmarker.createFromOptions(fileset, {
          baseOptions: { modelAssetPath: MODELO_POSE, delegate },
          runningMode: 'VIDEO',
          numPoses: 1,
          // Silueta de la persona en cada cuadro: con ella la prenda toma la forma del cuerpo
          outputSegmentationMasks: true,
          ...(delegate === 'GPU' ? { canvas: lienzoGpu } : {}),
        });
      let pose: PoseLandmarker;
      let dibujoGpu: DrawingUtils | null = null;
      try {
        pose = await crearPose('GPU');
        dibujoGpu = new DrawingUtils(lienzoGpu.getContext('webgl2')!);
      } catch {
        pose = await crearPose('CPU');
      }
      const segmentador = await ImageSegmenter.createFromOptions(fileset, {
        baseOptions: { modelAssetPath: MODELO_SEGMENTACION, delegate: 'CPU' },
        runningMode: 'IMAGE',
        outputCategoryMask: true,
        outputConfidenceMasks: false,
      });
      return { pose, segmentador, dibujoGpu, lienzoGpu, crearPoseCpu: () => crearPose('CPU') };
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

// Deja solo la mancha más grande de la máscara y le rellena los huecos: saca pedazos sueltos
// (fondo confundido con ropa) y agujeros dentro de la prenda (ramas, sombras, reflejos).
function limpiarMascara(bin: Uint8Array, w: number, h: number): Uint8Array {
  const n = w * h;
  const mancha = new Int32Array(n);
  const pila = new Int32Array(n);
  let mayor = 0;
  let mayorTam = 0;
  let id = 0;
  for (let i = 0; i < n; i++) {
    if (!bin[i] || mancha[i]) continue;
    id++;
    let tam = 0;
    let tope = 0;
    pila[tope++] = i;
    mancha[i] = id;
    while (tope) {
      const j = pila[--tope];
      tam++;
      const x = j % w;
      for (const k of [x > 0 ? j - 1 : -1, x < w - 1 ? j + 1 : -1, j - w, j + w]) {
        if (k >= 0 && k < n && bin[k] && !mancha[k]) {
          mancha[k] = id;
          pila[tope++] = k;
        }
      }
    }
    if (tam > mayorTam) {
      mayorTam = tam;
      mayor = id;
    }
  }

  // Todo lo que no es la mancha elegida y se conecta con el borde es fondo; lo demás son huecos
  const fondo = new Uint8Array(n);
  let tope = 0;
  const marcar = (k: number) => {
    if (mancha[k] !== mayor && !fondo[k]) {
      fondo[k] = 1;
      pila[tope++] = k;
    }
  };
  for (let x = 0; x < w; x++) {
    marcar(x);
    marcar(n - w + x);
  }
  for (let y = 0; y < h; y++) {
    marcar(y * w);
    marcar(y * w + w - 1);
  }
  while (tope) {
    const j = pila[--tope];
    const x = j % w;
    if (x > 0) marcar(j - 1);
    if (x < w - 1) marcar(j + 1);
    if (j >= w) marcar(j - w);
    if (j < n - w) marcar(j + w);
  }
  const limpia = new Uint8Array(n);
  for (let i = 0; i < n; i++) limpia[i] = fondo[i] ? 0 : 1;
  return limpia;
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

  let metodo = 'fondo por color';
  const resultado = segmentador.segment(canvas);
  const mascara = resultado.categoryMask;
  if (mascara) {
    const clases = mascara.getAsUint8Array();
    const ropa = new Uint8Array(clases.length);
    let total = 0;
    for (let i = 0; i < clases.length; i++) {
      if (clases[i] === CLASE_ROPA) {
        ropa[i] = 1;
        total++;
      }
    }
    if (total / clases.length > 0.03) {
      metodo = 'segmentación de ropa (MediaPipe)';
      const limpia = limpiarMascara(ropa, mascara.width, mascara.height);
      // La máscara se estira con suavizado para que el borde de la prenda no quede serruchado
      const alfa = document.createElement('canvas');
      alfa.width = mascara.width;
      alfa.height = mascara.height;
      const actx = alfa.getContext('2d')!;
      const datosAlfa = actx.createImageData(alfa.width, alfa.height);
      for (let i = 0; i < limpia.length; i++) datosAlfa.data[i * 4 + 3] = limpia[i] ? 255 : 0;
      actx.putImageData(datosAlfa, 0, 0);
      ctx.globalCompositeOperation = 'destination-in';
      ctx.imageSmoothingQuality = 'high';
      ctx.drawImage(alfa, 0, 0, w, h);
      ctx.globalCompositeOperation = 'source-over';
    }
  }
  resultado.close();

  const datos = ctx.getImageData(0, 0, w, h);
  const px = datos.data;
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
    const distancia = new Float32Array(w * h);
    const prenda = new Uint8Array(w * h);
    for (let j = 0; j < distancia.length; j++) {
      const i = j * 4;
      distancia[j] = Math.hypot(px[i] - fondo[0], px[i + 1] - fondo[1], px[i + 2] - fondo[2]);
      prenda[j] = distancia[j] >= 38 ? 1 : 0;
    }
    const limpia = limpiarMascara(prenda, w, h);
    for (let j = 0; j < limpia.length; j++) {
      const d = distancia[j];
      // Fuera de la mancha: transparente; huecos rellenados: opacos; borde: transición suave
      px[j * 4 + 3] = !limpia[j] ? 0 : !prenda[j] || d >= 70 ? 255 : Math.round(((d - 38) / 32) * 255);
    }
    ctx.putImageData(datos, 0, 0);
  }

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

// Pinta un pedazo de la prenda como un rectángulo centrado en (cx, cy) y girado.
function pintarCaja(ctx: CanvasRenderingContext2D, textura: HTMLCanvasElement, src: Rect, cx: number, cy: number, w: number, h: number, ang: number): void {
  ctx.save();
  ctx.translate(cx, cy);
  ctx.rotate(ang);
  ctx.drawImage(textura, src[0], src[1], src[2], src[3], -w / 2, -h / 2, w, h);
  ctx.restore();
}

// Pinta un pedazo de la prenda como una tira que va de `a` a `b` (el borde de arriba del pedazo
// queda en `a`): así una manga o una pierna del pantalón sigue al brazo o a la pierna.
function pintarTira(ctx: CanvasRenderingContext2D, textura: HTMLCanvasElement, src: Rect, a: Punto, b: Punto, ancho: number): void {
  const largo = dist(a, b);
  if (largo < 2) return;
  ctx.save();
  ctx.translate(a.x, a.y);
  ctx.rotate(Math.atan2(b.y - a.y, b.x - a.x) - Math.PI / 2);
  // Se alarga un poco en las dos puntas para que no quede un hueco en el codo o la rodilla
  ctx.drawImage(textura, src[0], src[1], src[2], src[3], -ancho / 2, -largo * 0.1, ancho, largo * 1.2);
  ctx.restore();
}

@Component({
  selector: 'app-ar-mediapipe',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="ar-contenedor">
      <video #video autoplay playsinline muted class="ar-video-oculto"></video>
      <canvas
        #lienzo
        class="ar-lienzo"
        [class.ar-lienzo-visible]="estado() === 'listo'"
        [style.max-height]="altoMaximo"
      ></canvas>
      <div *ngIf="estado() === 'listo' && aviso()" class="ar-aviso">{{ aviso() }}</div>

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
      <div class="ar-botones">
        <button *ngIf="variasCamaras()" class="btn btn-secondary btn-sm" [disabled]="cambiandoCamara()" (click)="cambiarCamara()">
          🔄 {{ camara() === 'user' ? 'Cámara trasera' : 'Cámara frontal' }}
        </button>
        <button *ngIf="permitirCaptura" class="btn btn-secondary btn-sm" (click)="capturar()">📸 Capturar</button>
      </div>
    </div>
  `,
  styles: [`
    .ar-contenedor { position: relative; min-height: 220px; }
    .ar-video-oculto { position: absolute; width: 1px; height: 1px; opacity: 0; pointer-events: none; }
    .ar-lienzo { display: none; width: 100%; max-height: 420px; border-radius: 12px; background: #0f172a; object-fit: contain; }
    .ar-lienzo-visible { display: block; }
    .ar-aviso {
      position: absolute; top: 0.6rem; left: 50%; transform: translateX(-50%); max-width: 90%;
      padding: 0.35rem 0.8rem; border-radius: 999px; background: rgba(15, 23, 42, 0.78); color: #fff;
      font-size: 0.8rem; text-align: center; pointer-events: none;
    }
    .ar-estado { text-align: center; padding: 2rem 1rem; color: #475569; }
    .ar-barra { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 0.5rem; margin-top: 0.6rem; font-size: 0.78rem; color: #64748b; }
    .ar-botones { display: flex; gap: 0.4rem; }
  `],
})
export class ArMediapipe implements AfterViewInit, OnChanges, OnDestroy {
  @Input() imagenUrl: string | null = null;
  @Input() zona: ZonaCorporal = 'superior';
  @Input() altoMaximo = '420px';
  // Dentro de la app móvil (WebView) no se pueden descargar archivos
  @Input() permitirCaptura = true;

  @ViewChild('video') videoRef!: ElementRef<HTMLVideoElement>;
  @ViewChild('lienzo') lienzoRef!: ElementRef<HTMLCanvasElement>;

  estado = signal<EstadoAr>('cargando');
  mensajeError = signal('');
  fps = signal(0);
  personaDetectada = signal(false);
  metodoRecorte = signal('-');
  aviso = signal<string | null>(null);
  // Frontal ("user") se ve en espejo, como un probador; la trasera ("environment") sirve para
  // que otra persona sostenga el celular, y se muestra tal cual
  camara = signal<'user' | 'environment'>('user');
  variasCamaras = signal(false);
  cambiandoCamara = signal(false);

  private modelos: Modelos | null = null;
  private prenda: HTMLCanvasElement | null = null;
  private stream: MediaStream | null = null;
  private raf = 0;
  private activo = false;
  private puntos: Punto[] | null = null;
  private siluetasVacias = 0;
  private siluetaGpuRevisada = false;
  // Silueta de la persona en el canal alfa: el lienzo WebGL de MediaPipe (GPU) o un canvas chico
  // armado en CPU. La capa es donde se arma la prenda antes de pegarla sobre el video.
  private fuenteSilueta: HTMLCanvasElement | null = null;
  private silueta: HTMLCanvasElement | null = null;
  private siluetaDatos: ImageData | null = null;
  private muestra: HTMLCanvasElement | null = null;
  private capa: HTMLCanvasElement | null = null;
  private cuadros = 0;
  private inicioFps = 0;

  async ngAfterViewInit(): Promise<void> {
    this.activo = true;
    try {
      await this.abrirCamara();
    } catch {
      this.estado.set('sin-camara');
      return;
    }
    // Recién con el permiso dado el navegador lista todas las cámaras
    navigator.mediaDevices
      .enumerateDevices()
      .then((d) => this.variasCamaras.set(d.filter((x) => x.kind === 'videoinput').length > 1))
      .catch(() => undefined);

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
      this.prepararPrenda().catch((err) => this.mostrarError(err instanceof Error ? err.message : String(err)));
    }
  }

  ngOnDestroy(): void {
    this.activo = false;
    cancelAnimationFrame(this.raf);
    this.stream?.getTracks().forEach((t) => t.stop());
  }

  private async abrirCamara(): Promise<void> {
    this.stream?.getTracks().forEach((t) => t.stop());
    this.stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: { ideal: this.camara() }, width: { ideal: 640 }, height: { ideal: 480 } },
      audio: false,
    });
    const video = this.videoRef.nativeElement;
    video.srcObject = this.stream;
    await video.play().catch(() => undefined);
  }

  async cambiarCamara(): Promise<void> {
    const anterior = this.camara();
    this.camara.set(anterior === 'user' ? 'environment' : 'user');
    this.cambiandoCamara.set(true);
    // Los puntos suavizados de la otra cámara no sirven (además cambia el espejo)
    this.puntos = null;
    try {
      await this.abrirCamara();
    } catch {
      // Si no se pudo abrir la otra, se vuelve a la que andaba
      this.camara.set(anterior);
      await this.abrirCamara().catch(() => this.estado.set('sin-camara'));
    } finally {
      this.cambiandoCamara.set(false);
    }
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

      // Con la frontal, vista espejo como un probador real
      if (this.camara() === 'user') {
        ctx.save();
        ctx.scale(-1, 1);
        ctx.drawImage(video, -W, 0, W, H);
        ctx.restore();
      } else {
        ctx.drawImage(video, 0, 0, W, H);
      }

      // Con callback las máscaras no se copian: solo valen dentro de esta función
      this.modelos.pose.detectForVideo(video, performance.now(), (resultado) => {
        const lm = resultado.landmarks[0];
        this.personaDetectada.set(!!lm);
        if (!lm) {
          this.puntos = null;
          this.aviso.set('Colócate frente a la cámara');
          return;
        }
        const puntos = this.suavizar(lm, W, H);
        const mascara = resultado.segmentationMasks?.[0];
        if (mascara && !this.actualizarSilueta(mascara) && ++this.siluetasVacias === 3) {
          // Hay persona pero la silueta llega vacía: esta GPU no deja usar la máscara
          this.pasarPoseACpu();
        }
        this.dibujarPrenda(ctx, puntos, W, H);
      });

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

  // Pasa los puntos a píxeles (en espejo con la frontal) y los suaviza entre cuadros para que la
  // prenda no tiemble
  private suavizar(lm: NormalizedLandmark[], W: number, H: number): Punto[] {
    const espejo = this.camara() === 'user';
    const nuevos = lm.map((l) => ({
      x: (espejo ? 1 - l.x : l.x) * W,
      y: l.y * H,
      v: l.visibility ?? 1,
      ok: (l.visibility ?? 1) > 0.5 && l.x > -0.05 && l.x < 1.05 && l.y > -0.05 && l.y < 1.1,
    }));
    const previos = this.puntos;
    if (previos && previos.length === nuevos.length) {
      nuevos.forEach((n, i) => {
        n.x = previos[i].x + (n.x - previos[i].x) * 0.5;
        n.y = previos[i].y + (n.y - previos[i].y) * 0.5;
      });
    }
    this.puntos = nuevos;
    return nuevos;
  }

  private async pasarPoseACpu(): Promise<void> {
    const modelos = this.modelos;
    if (!modelos?.dibujoGpu) return;
    modelos.dibujoGpu.close();
    modelos.dibujoGpu = null;
    const anterior = modelos.pose;
    modelos.pose = await modelos.crearPoseCpu();
    anterior.close();
  }

  // Deja la silueta de la persona en el alfa de `fuenteSilueta`. Devuelve si salió algo.
  private actualizarSilueta(mascara: MPMask): boolean {
    const modelos = this.modelos;
    if (modelos?.dibujoGpu) {
      modelos.dibujoGpu.drawConfidenceMask(mascara, [0, 0, 0, 0], [255, 255, 255, 255]);
      this.fuenteSilueta = modelos.lienzoGpu;
      // Se revisa solo hasta ver una silueta con algo: leer el lienzo WebGL cada cuadro es caro
      if (!this.siluetaGpuRevisada) this.siluetaGpuRevisada = !this.lienzoVacio(modelos.lienzoGpu);
      return this.siluetaGpuRevisada;
    }

    // En CPU: la confianza (0..1) se copia al alfa de un canvas chico; al estirarlo sobre el
    // video con suavizado, el borde de la prenda queda prolijo
    const paso = Math.max(1, Math.round(mascara.width / 160));
    const w = Math.floor(mascara.width / paso);
    const h = Math.floor(mascara.height / paso);
    this.silueta ??= document.createElement('canvas');
    if (this.silueta.width !== w || this.silueta.height !== h) {
      this.silueta.width = w;
      this.silueta.height = h;
      this.siluetaDatos = null;
    }
    const sctx = this.silueta.getContext('2d')!;
    this.siluetaDatos ??= sctx.createImageData(w, h);
    const alfa = this.siluetaDatos.data;
    const confianza = mascara.getAsFloat32Array();
    let hayPersona = false;
    for (let y = 0; y < h; y++) {
      const fila = y * paso * mascara.width;
      for (let x = 0; x < w; x++) {
        const v = confianza[fila + x * paso];
        if (v > 0.3) hayPersona = true;
        alfa[(y * w + x) * 4 + 3] = v <= 0.3 ? 0 : v >= 0.6 ? 255 : ((v - 0.3) / 0.3) * 255;
      }
    }
    sctx.putImageData(this.siluetaDatos, 0, 0);
    this.fuenteSilueta = this.silueta;
    return hayPersona;
  }

  private lienzoVacio(lienzo: HTMLCanvasElement): boolean {
    this.muestra ??= document.createElement('canvas');
    this.muestra.width = 16;
    this.muestra.height = 16;
    const mctx = this.muestra.getContext('2d', { willReadFrequently: true })!;
    mctx.drawImage(lienzo, 0, 0, 16, 16);
    const datos = mctx.getImageData(0, 0, 16, 16).data;
    for (let i = 3; i < datos.length; i += 4) if (datos[i] > 0) return false;
    return true;
  }

  private dibujarPrenda(ctx: CanvasRenderingContext2D, P: Punto[], W: number, H: number): void {
    if (!this.prenda) return;
    this.capa ??= document.createElement('canvas');
    const capa = this.capa;
    if (capa.width !== W) capa.width = W;
    if (capa.height !== H) capa.height = H;
    const cctx = capa.getContext('2d')!;
    cctx.globalCompositeOperation = 'source-over';
    cctx.clearRect(0, 0, W, H);

    const { pintado, aviso } = this.pintarZona(cctx, this.prenda, P);
    this.aviso.set(aviso);
    if (!pintado) return;

    if (this.fuenteSilueta) {
      // La prenda queda solo donde está la persona: toma la forma del cuerpo y no tapa el fondo
      cctx.globalCompositeOperation = 'destination-in';
      if (this.camara() === 'user') {
        cctx.save();
        cctx.scale(-1, 1);
        cctx.drawImage(this.fuenteSilueta, -W, 0, W, H);
        cctx.restore();
      } else {
        cctx.drawImage(this.fuenteSilueta, 0, 0, W, H);
      }
    }
    // ...ni la cara, el cuello o las manos
    cctx.globalCompositeOperation = 'destination-out';
    this.borrarPartes(cctx, P);
    cctx.globalCompositeOperation = 'source-over';
    ctx.drawImage(capa, 0, 0);
  }

  // Pinta la prenda sobre el cuerpo según su zona. Devuelve si pintó algo y, si falta ver una
  // parte del cuerpo, qué pedirle a la persona.
  private pintarZona(ctx: CanvasRenderingContext2D, t: HTMLCanvasElement, P: Punto[]): { pintado: boolean; aviso: string | null } {
    const tw = t.width;
    const th = t.height;
    const todo: Rect = [0, 0, tw, th];

    switch (this.zona) {
      case 'superior':
      case 'abrigo': {
        if (!P[11].ok || !P[12].ok) return { pintado: false, aviso: 'Aléjate un poco: que se vean tus hombros' };
        const e = ejes(P[11], P[12]);
        // Largo del torso medido a lo largo del cuerpo (sirve aunque la persona se incline)
        const caderas = medio(P[23], P[24]);
        const largoTorso = (caderas.x - e.centro.x) * e.d.x + (caderas.y - e.centro.y) * e.d.y;
        const conCadera = caderas.ok && largoTorso > e.ancho * 0.6;
        const h = (conCadera ? largoTorso : e.ancho * 1.3) * 1.25;
        pintarCaja(ctx, t, todo, e.centro.x + e.d.x * h * 0.38, e.centro.y + e.d.y * h * 0.38, e.ancho * 2, h, e.ang);

        if (this.zona === 'abrigo') {
          // Mangas: los costados de la foto de la prenda se estiran a lo largo de cada brazo
          const brazos = [[11, 13, 15], [12, 14, 16]].sort((a, b) => P[a[0]].x - P[b[0]].x);
          brazos.forEach(([hombro, codo, muneca], lado) => {
            if (!P[codo].ok) return;
            const x = lado === 0 ? 0 : tw * 0.76;
            pintarTira(ctx, t, [x, 0, tw * 0.24, th * 0.55], P[hombro], P[codo], e.ancho * 0.5);
            if (P[muneca].ok) pintarTira(ctx, t, [x, th * 0.45, tw * 0.24, th * 0.55], P[codo], P[muneca], e.ancho * 0.45);
          });
        }
        return { pintado: true, aviso: conCadera ? null : 'Aléjate un poco más para que se vea tu cadera' };
      }

      case 'vestido': {
        if (!P[11].ok || !P[12].ok) return { pintado: false, aviso: 'Aléjate: que se vea de los hombros a las rodillas' };
        const e = ejes(P[11], P[12]);
        const rodillas = medio(P[25], P[26]);
        const largo = (rodillas.x - e.centro.x) * e.d.x + (rodillas.y - e.centro.y) * e.d.y;
        if (!rodillas.ok || largo < e.ancho) return { pintado: false, aviso: 'Aléjate hasta que se vean tus rodillas' };
        const h = largo * 1.2;
        pintarCaja(ctx, t, todo, e.centro.x + e.d.x * h * 0.42, e.centro.y + e.d.y * h * 0.42, e.ancho * 2.1, h, e.ang);
        return { pintado: true, aviso: null };
      }

      case 'inferior': {
        if (![23, 24, 25, 26].every((i) => P[i].ok)) {
          return { pintado: false, aviso: 'Aléjate hasta que se vean tu cadera y tus rodillas' };
        }
        const e = ejes(P[23], P[24]);
        // Cintura: la parte de arriba de la foto, a lo ancho de la cadera
        pintarCaja(ctx, t, [0, 0, tw, th * 0.25], e.centro.x + e.d.x * e.ancho * 0.05, e.centro.y + e.d.y * e.ancho * 0.05, e.ancho * 2.4, e.ancho * 1.2, e.ang);
        // Cada mitad de la foto sigue a una pierna (muslo y canilla por separado)
        const piernas = [[23, 25, 27], [24, 26, 28]].sort((a, b) => P[a[0]].x - P[b[0]].x);
        let conTobillos = true;
        piernas.forEach(([cadera, rodilla, tobillo], lado) => {
          const x = lado === 0 ? 0 : tw * 0.5;
          pintarTira(ctx, t, [x, th * 0.12, tw * 0.5, th * 0.48], P[cadera], P[rodilla], e.ancho * 1.25);
          if (P[tobillo].ok) pintarTira(ctx, t, [x, th * 0.55, tw * 0.5, th * 0.45], P[rodilla], P[tobillo], e.ancho);
          else conTobillos = false;
        });
        return { pintado: true, aviso: conTobillos ? null : 'Aléjate un poco más para que se vean tus tobillos' };
      }

      case 'calzado': {
        let pintado = false;
        let tope = Infinity;
        for (const [tobillo, talon, punta] of [[27, 29, 31], [28, 30, 32]]) {
          if (!P[tobillo].ok || !P[punta].ok) continue;
          const pie = Math.max(dist(P[talon], P[punta]), dist(P[tobillo], P[punta]), 1);
          const w = pie * 2;
          const h = Math.max(w * (th / tw), pie * 1.6);
          const c = medio(P[tobillo], P[punta]);
          pintarCaja(ctx, t, todo, c.x, c.y, w, h, 0);
          tope = Math.min(tope, P[tobillo].y - pie * 0.2);
          pintado = true;
        }
        // Nada por encima de los tobillos: la silueta también incluye las piernas
        if (pintado) ctx.clearRect(0, 0, ctx.canvas.width, Math.max(0, tope));
        return { pintado, aviso: pintado ? null : 'Apunta la cámara a tus pies (que se vean enteros)' };
      }
    }
  }

  // Borra de la capa de la prenda la cara, el cuello y las manos
  private borrarPartes(ctx: CanvasRenderingContext2D, P: Punto[]): void {
    if (this.zona === 'calzado') return;
    ctx.fillStyle = '#000';
    if (this.zona !== 'inferior') {
      const e = ejes(P[11], P[12]);
      const punto = (a: number, b: number): [number, number] => [
        e.centro.x + (e.u.x * a + e.d.x * b) * e.ancho,
        e.centro.y + (e.u.y * a + e.d.y * b) * e.ancho,
      ];
      // Borde difuminado para que el corte no se note
      ctx.filter = `blur(${Math.max(2, Math.round(e.ancho * 0.03))}px)`;
      // Cuello: escote redondo que baja hasta la línea de los hombros...
      const [ex, ey] = punto(0, -0.28);
      ctx.beginPath();
      ctx.ellipse(ex, ey, e.ancho * 0.19, e.ancho * 0.3, e.ang, 0, Math.PI * 2);
      ctx.fill();
      // ...y por encima, toda la franja hacia la cabeza
      ctx.beginPath();
      ctx.moveTo(...punto(-0.19, -0.28));
      ctx.lineTo(...punto(0.19, -0.28));
      ctx.lineTo(...punto(0.19, -4));
      ctx.lineTo(...punto(-0.19, -4));
      ctx.closePath();
      ctx.fill();
      // Cara: elipse que va de las orejas a la boca
      const orejas = medio(P[7], P[8]);
      const boca = medio(P[9], P[10]);
      if (orejas.ok && boca.ok) {
        const entreOrejas = dist(P[7], P[8]);
        ctx.beginPath();
        ctx.ellipse(
          (orejas.x + boca.x) / 2,
          (orejas.y + boca.y) / 2,
          entreOrejas * 0.62,
          entreOrejas * 0.85,
          Math.atan2(P[8].y - P[7].y, P[8].x - P[7].x),
          0,
          Math.PI * 2,
        );
        ctx.fill();
      }
      ctx.filter = 'none';
    }
    // Manos: óvalo de borde suave desde la muñeca hacia los dedos (la manga llega a la muñeca).
    // Solo si la mano se ve clara: una mano tapada mal estimada dejaría un hueco en la prenda.
    for (const [muneca, indice] of [[15, 19], [16, 20]]) {
      if (!P[muneca].ok || P[muneca].v < 0.8) continue;
      const m = P[muneca];
      const i = P[indice];
      const r = Math.max(dist(m, i), 4) * 1.15;
      ctx.save();
      ctx.translate(m.x + (i.x - m.x) * 0.95, m.y + (i.y - m.y) * 0.95);
      ctx.rotate(Math.atan2(i.y - m.y, i.x - m.x));
      ctx.scale(1, 0.55);
      const degradado = ctx.createRadialGradient(0, 0, r * 0.45, 0, 0, r);
      degradado.addColorStop(0, 'rgba(0, 0, 0, 1)');
      degradado.addColorStop(1, 'rgba(0, 0, 0, 0)');
      ctx.fillStyle = degradado;
      ctx.beginPath();
      ctx.arc(0, 0, r, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();
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
