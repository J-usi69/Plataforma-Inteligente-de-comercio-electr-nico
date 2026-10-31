// Sincronización de la operación sin conexión: descarga el paquete para trabajar sin Internet,
// registra ventas, reservas y cambios en el dispositivo y los envía al backend cuando hay conexión
// (al volver la red, al abrir la app, cada minuto y a pedido). Una operación nunca se borra por
// haberse enviado: queda con el estado que respondió el servidor.
import { HttpClient, HttpErrorResponse, HttpParams } from '@angular/common/http';
import { Injectable, Injector, computed, effect, inject, signal, untracked } from '@angular/core';
import { TimeoutError, firstValueFrom, timeout } from 'rxjs';
import { AuthService } from '../services/auth.service';
import { TiendaService } from '../services/tienda.service';
import { AlmacenLocal, DatosLocales } from './almacen-local';
import {
  EstadoOperacionesOut,
  InfoPaquete,
  LoteOut,
  OperacionLocal,
  Paquete,
  TipoOperacion,
} from './modelos';
import {
  efectoEnStock,
  estadoTrasResultado,
  nuevoId,
  paqueteDesactualizado,
  pendienteDeEnvio,
  resumenDe,
  sobreParaEnviar,
} from './reglas';

const POR_LOTE = 50;
const CADA_MS = 60_000;
const PROBAR_CONEXION_MS = 15_000;
const RENOVAR_PAQUETE_MS = 10 * 60_000; // con conexión, el paquete se renueva si tiene más de 10 minutos

// 0: sin red. 504: el Service Worker no llegó a la red. 502/503: el proxy no llegó al backend
const SIN_SERVIDOR = new Set([0, 502, 503, 504]);

/** El pedido no llegó al servidor (sin red, servidor caído o sin respuesta a tiempo). */
export function sinConexion(err: unknown): boolean {
  return err instanceof TimeoutError || (err instanceof HttpErrorResponse && SIN_SERVIDOR.has(err.status));
}

export function mensajeDeError(err: unknown, porDefecto: string): string {
  if (err instanceof TimeoutError) return 'El servidor no respondió a tiempo.';
  if (err instanceof HttpErrorResponse) {
    if (SIN_SERVIDOR.has(err.status)) return 'No hay conexión con el servidor.';
    if (err.status === 401) return 'Tu sesión venció: iniciá sesión de nuevo para enviar las operaciones.';
    if (typeof err.error?.detail === 'string') return err.error.detail;
  }
  return porDefecto;
}

@Injectable({ providedIn: 'root' })
export class SincronizacionService {
  private readonly http = inject(HttpClient);
  private readonly auth = inject(AuthService);
  private readonly tienda = inject(TiendaService);
  private readonly injector = inject(Injector);
  readonly almacen = new AlmacenLocal(`fashionstore-offline:${this.tienda.slug ?? 'fashionstore'}`);

  readonly enLinea = signal(typeof navigator === 'undefined' ? true : navigator.onLine);
  readonly datos = signal<DatosLocales | null>(null);
  private readonly todas = signal<OperacionLocal[]>([]);
  readonly sincronizando = signal(false);
  readonly descargando = signal(false);
  readonly ultimoError = signal<string | null>(null);

  readonly disponible = computed(() => this.auth.isLoggedIn() && this.tienda.tiene('operacion_offline'));
  /** Las de la sesión actual: las de otro usuario de este equipo esperan a que él inicie sesión. */
  readonly operaciones = computed(() => {
    const usuario = this.auth.currentUser()?.id;
    return this.todas().filter((op) => op.usuario_id === usuario);
  });
  readonly pendientes = computed(() => this.operaciones().filter(pendienteDeEnvio).length);
  readonly enConflicto = computed(() => this.operaciones().filter((op) => op.estado === 'conflicto').length);
  readonly info = computed<InfoPaquete | null>(() => this.datos()?.info ?? null);
  readonly desactualizado = computed(() => {
    const info = this.info();
    return !!info && paqueteDesactualizado(info.generado_en, info.vigencia_horas);
  });

  private iniciado = false;
  private enCurso: Promise<void> | null = null;
  private primeraCarga: Promise<void> | null = null;

  /** Lo guardado ya está leído (la API local lo espera antes de contestar). */
  listo(): Promise<void> {
    return (this.primeraCarga ??= this.cargarLocal());
  }

  /** Un pedido no llegó al servidor: se trabaja con lo guardado hasta que vuelva la conexión. */
  marcarSinConexion(): void {
    this.enLinea.set(false);
  }

  /** Una vez, al arrancar la app. */
  iniciar(): void {
    if (this.iniciado) return;
    this.iniciado = true;
    window.addEventListener('online', () => {
      this.enLinea.set(true);
      void this.alRecuperarConexion();
    });
    window.addEventListener('offline', () => this.enLinea.set(false));
    setInterval(() => {
      if (this.enLinea() && (this.pendientes() > 0 || this.enConflicto() > 0)) void this.sincronizar();
    }, CADA_MS);
    // navigator.onLine dice "conectado" con wifi sin Internet o con el servidor caído: si los
    // pedidos fallan se pasa a sin conexión y se prueba de a ratos si el servidor volvió
    setInterval(() => {
      if (!this.enLinea()) void this.probarConexion();
    }, PROBAR_CONEXION_MS);
    void this.probarConexion();
    // Al iniciar o cerrar sesión (y al arrancar con una sesión guardada)
    effect(
      () => {
        const usuario = this.auth.currentUser()?.id ?? null;
        untracked(() => void this.alCambiarUsuario(usuario));
      },
      { injector: this.injector },
    );
  }

  private async alCambiarUsuario(usuarioId: number | null): Promise<void> {
    if (usuarioId === null) {
      // El paquete tiene datos de clientes: no queda en el equipo. Las operaciones sí
      await this.almacen.borrarPaquete();
      await this.cargarLocal();
      return;
    }
    await this.cargarLocal();
    if (this.enLinea()) await this.alRecuperarConexion();
  }

  /** Al arrancar y, sin conexión, cada 15 s: ¿responde el servidor? */
  private async probarConexion(): Promise<void> {
    try {
      await firstValueFrom(this.http.get('/api/v1/tienda').pipe(timeout(5_000)));
    } catch (err) {
      if (sinConexion(err)) {
        this.enLinea.set(false);
        return;
      } // cualquier otra respuesta del servidor ya es conexión
    }
    if (!this.enLinea()) {
      this.enLinea.set(true);
      await this.alRecuperarConexion();
    }
  }

  private registrarFalla(err: unknown, porDefecto: string): void {
    if (sinConexion(err)) this.enLinea.set(false);
    this.ultimoError.set(mensajeDeError(err, porDefecto));
  }

  private async alRecuperarConexion(): Promise<void> {
    if (!this.disponible()) return;
    await this.sincronizar();
    const info = this.info();
    const viejo = !info || Date.now() - new Date(info.generado_en).getTime() > RENOVAR_PAQUETE_MS;
    if (viejo) await this.descargarPaquete();
  }

  /** Lee lo guardado. Un paquete de otra sesión (otras sucursales autorizadas) no se muestra. */
  async cargarLocal(): Promise<void> {
    const [datos, ops] = await Promise.all([this.almacen.leerPaquete(), this.almacen.operaciones()]);
    const usuario = this.auth.currentUser()?.id;
    this.datos.set(datos && datos.info.usuario_id === usuario ? datos : null);
    this.todas.set(ops);
  }

  async descargarPaquete(): Promise<boolean> {
    const usuario = this.auth.currentUser();
    if (!usuario || !this.tienda.tiene('operacion_offline')) return false;
    this.descargando.set(true);
    try {
      const paquete = await firstValueFrom(this.http.get<Paquete>('/api/v1/sync/paquete').pipe(timeout(30_000)));
      // Lo que el servidor todavía no conoce se vuelve a descontar del stock recién bajado
      const sinEnviar = (await this.almacen.operaciones()).filter((op) => op.usuario_id === usuario.id && pendienteDeEnvio(op));
      await this.almacen.guardarPaquete(paquete, usuario.id, sinEnviar, (op) => efectoEnStock(op.tipo, op.datos));
      await this.cargarLocal();
      this.ultimoError.set(null);
      return true;
    } catch (err) {
      this.registrarFalla(err, 'No se pudieron descargar los datos para trabajar sin conexión.');
      return false;
    } finally {
      this.descargando.set(false);
    }
  }

  /** Guarda la operación en el dispositivo (con su efecto en el stock local) y, si hay conexión,
   * la envía enseguida. Con o sin red, el camino es el mismo: la cola. */
  async registrar(tipo: TipoOperacion, sucursalId: number, datos: OperacionLocal['datos']): Promise<OperacionLocal> {
    const info = this.info();
    const usuario = this.auth.currentUser();
    if (!info || !usuario) {
      throw new Error('Primero descargá los datos para trabajar sin conexión.');
    }
    const op = await this.almacen.registrar(
      {
        id: nuevoId(),
        orden: 0,
        tipo,
        tienda: info.tienda,
        sucursal_id: sucursalId,
        registrada_en: new Date().toISOString(),
        dispositivo: 'pwa-web',
        datos,
        usuario_id: usuario.id,
        estado: 'registrada',
        intentos: 0,
        ultimo_intento: null,
        resultado: null,
        resumen: resumenDe(tipo, datos),
      },
      efectoEnStock(tipo, datos),
    );
    await this.cargarLocal();
    if (this.enLinea()) void this.sincronizar();
    return op;
  }

  /** Una sola sincronización a la vez: si ya hay una en curso, se espera esa. */
  sincronizar(): Promise<void> {
    this.enCurso ??= this.enviarPendientes().finally(() => (this.enCurso = null));
    return this.enCurso;
  }

  private async enviarPendientes(): Promise<void> {
    const usuario = this.auth.currentUser();
    if (!usuario || !this.tienda.tiene('operacion_offline')) return;
    this.sincronizando.set(true);
    let confirmadas = 0;
    try {
      const pendientes = (await this.almacen.operaciones()).filter((op) => op.usuario_id === usuario.id && pendienteDeEnvio(op));
      for (let i = 0; i < pendientes.length; i += POR_LOTE) {
        const lote = pendientes.slice(i, i + POR_LOTE).map((op) => ({
          ...op,
          estado: 'enviada' as const,
          intentos: op.intentos + 1,
          ultimo_intento: new Date().toISOString(),
        }));
        await this.almacen.actualizar(lote); // si la respuesta no llega, quedan "enviadas" y se reenvían igual
        await this.cargarLocal();
        const respuesta = await firstValueFrom(
          this.http.post<LoteOut>('/api/v1/sync/operaciones', { operaciones: lote.map(sobreParaEnviar) }).pipe(timeout(60_000)),
        );
        const porId = new Map(respuesta.resultados.map((r) => [r.id, r]));
        const respondidas = lote.map((op) => {
          const r = porId.get(op.id);
          if (!r) return op;
          if (r.estado === 'confirmada') confirmadas++;
          const { codigo, mensaje, referencia_tipo, referencia_id } = r;
          return { ...op, estado: estadoTrasResultado(r), resultado: { codigo, mensaje, referencia_tipo, referencia_id } };
        });
        await this.almacen.actualizar(respondidas);
        await this.cargarLocal();
      }
      await this.actualizarConflictos();
      this.ultimoError.set(null);
    } catch (err) {
      // Sin red, servidor caído, suscripción vencida (402) o sesión vencida (401): todo queda
      // guardado como estaba y se reintenta más tarde
      this.registrarFalla(err, 'No se pudieron enviar las operaciones: se reintentará.');
    } finally {
      this.sincronizando.set(false);
    }
    if (confirmadas > 0) await this.descargarPaquete(); // stock y ventas al día con lo confirmado
  }

  /** Los conflictos los resuelve un encargado: se pregunta si ya decidió. */
  private async actualizarConflictos(): Promise<void> {
    const enConflicto = this.operaciones().filter((op) => op.estado === 'conflicto');
    if (!enConflicto.length) return;
    let params = new HttpParams();
    enConflicto.slice(0, 100).forEach((op) => (params = params.append('ids', op.id)));
    const estado = await firstValueFrom(this.http.get<EstadoOperacionesOut>('/api/v1/sync/estado', { params }).pipe(timeout(30_000)));
    const porId = new Map(estado.resultados.map((r) => [r.id, r]));
    const resueltas = enConflicto
      .filter((op) => porId.has(op.id) && porId.get(op.id)!.estado !== 'conflicto')
      .map((op) => {
        const { codigo, mensaje, referencia_tipo, referencia_id, estado: nuevo } = porId.get(op.id)!;
        return { ...op, estado: estadoTrasResultado({ estado: nuevo }), resultado: { codigo, mensaje, referencia_tipo, referencia_id } };
      });
    if (resueltas.length) {
      await this.almacen.actualizar(resueltas);
      await this.cargarLocal();
    }
  }
}
