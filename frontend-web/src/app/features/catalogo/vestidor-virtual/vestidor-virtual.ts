import { CommonModule } from '@angular/common';
import {
  Component,
  ElementRef,
  EventEmitter,
  Input,
  OnChanges,
  OnDestroy,
  Output,
  SimpleChanges,
  ViewChild,
  inject,
  signal,
} from '@angular/core';
import { Prenda } from '../../../core/models/user.model';
import { BusinessService } from '../../../core/services/business.service';

type EstadoVestidor = 'camara' | 'generando' | 'listo' | 'error';

const MAX_INTENTOS_POLLING = 45; // ~90s a 2s por intento, igual de margen que en la app móvil

@Component({
  selector: 'app-vestidor-virtual',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './vestidor-virtual.html',
  styles: [`
    .vestidor-video, .vestidor-foto {
      width: 100%;
      max-height: 420px;
      border-radius: 12px;
      background: #0f172a;
      object-fit: contain;
    }

    .vestidor-estado {
      text-align: center;
      padding: 2.5rem 1rem;
      color: #475569;
    }
  `],
})
export class VestidorVirtual implements OnChanges, OnDestroy {
  private readonly business = inject(BusinessService);

  @Input() prenda: Prenda | null = null;
  @Output() cerrar = new EventEmitter<void>();

  @ViewChild('video') videoRef?: ElementRef<HTMLVideoElement>;

  estado = signal<EstadoVestidor>('camara');
  mensajeError = signal<string | null>(null);
  resultUrl = signal<string | null>(null);
  camaraDisponible = signal(true);

  private stream: MediaStream | null = null;
  private pollTimer: ReturnType<typeof setInterval> | null = null;
  private intentosPolling = 0;

  get prendaTieneImagen(): boolean {
    return !!this.prenda?.imagen_url;
  }

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['prenda'] && this.prenda) {
      this.reiniciar();
    }
  }

  ngOnDestroy(): void {
    this.detenerCamara();
    this.detenerPolling();
  }

  private reiniciar(): void {
    this.detenerPolling();
    this.estado.set('camara');
    this.mensajeError.set(null);
    this.resultUrl.set(null);
    if (this.prendaTieneImagen) {
      this.iniciarCamara();
    }
  }

  private async iniciarCamara(): Promise<void> {
    this.detenerCamara();
    try {
      this.stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'user' },
        audio: false,
      });
      this.camaraDisponible.set(true);
      // El <video> se renderiza recién cuando estado() === 'camara'; esperamos al siguiente tick.
      setTimeout(() => {
        if (this.videoRef) {
          this.videoRef.nativeElement.srcObject = this.stream;
        }
      });
    } catch {
      // Sin permiso de cámara o sin dispositivo: se ofrece el input de archivo como respaldo.
      this.camaraDisponible.set(false);
    }
  }

  private detenerCamara(): void {
    this.stream?.getTracks().forEach((track) => track.stop());
    this.stream = null;
  }

  tomarFotoDesdeCamara(): void {
    const video = this.videoRef?.nativeElement;
    if (!video || !video.videoWidth) return;

    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext('2d')?.drawImage(video, 0, 0, canvas.width, canvas.height);
    canvas.toBlob((blob) => {
      if (blob) this.generar(blob);
    }, 'image/jpeg', 0.92);
  }

  onArchivoSeleccionado(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    input.value = '';
    if (file) this.generar(file);
  }

  private generar(foto: Blob): void {
    const prenda = this.prenda;
    if (!prenda) return;

    this.detenerCamara();
    this.estado.set('generando');
    this.mensajeError.set(null);
    this.resultUrl.set(null);

    this.business.crearVestidorJob(prenda.id, foto).subscribe({
      next: (job) => this.iniciarPolling(job.job_id),
      error: (err) => this.mostrarError(err?.error?.detail ?? 'No se pudo iniciar la generación del vestidor virtual.'),
    });
  }

  private iniciarPolling(jobId: string): void {
    this.detenerPolling();
    this.intentosPolling = 0;
    this.pollTimer = setInterval(() => {
      this.intentosPolling++;
      if (this.intentosPolling > MAX_INTENTOS_POLLING) {
        this.mostrarError('La generación está tardando demasiado. Intenta nuevamente en unos minutos.');
        return;
      }

      this.business.getVestidorJob(jobId).subscribe({
        next: (job) => {
          if (job.status === 'SUCCEEDED') {
            this.detenerPolling();
            this.resultUrl.set(job.result_url ?? null);
            this.estado.set('listo');
          } else if (job.status === 'FAILED' || job.status === 'CANCELLED') {
            this.mostrarError(this.traducirError(job.error) ?? 'La generación falló.');
          }
          // QUEUED / PROCESSING: se sigue esperando
        },
        error: (err) => this.mostrarError(err?.error?.detail ?? 'No se pudo consultar el estado de la generación.'),
      });
    }, 2000);
  }

  private traducirError(mensaje?: string | null): string | null {
    if (!mensaje) return mensaje ?? null;
    if (mensaje.includes('No detections found')) {
      return 'No se detectó una persona en la foto. Asegúrate de que tu rostro y cuerpo se vean con buena iluminación e inténtalo de nuevo.';
    }
    return mensaje;
  }

  private mostrarError(mensaje: string): void {
    this.detenerPolling();
    this.mensajeError.set(mensaje);
    this.estado.set('error');
  }

  private detenerPolling(): void {
    if (this.pollTimer) {
      clearInterval(this.pollTimer);
      this.pollTimer = null;
    }
  }

  probarOtraVez(): void {
    this.reiniciar();
  }

  cerrarModal(): void {
    this.detenerCamara();
    this.detenerPolling();
    this.cerrar.emit();
  }
}
