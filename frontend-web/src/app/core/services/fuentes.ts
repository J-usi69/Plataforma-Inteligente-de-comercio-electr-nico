import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import {
  CatalogoReporte,
  FormatoReporte,
  OpcionesReporte,
  ReporteIAPlataforma,
  ReportePlataforma,
  Restauracion,
} from '../models/tienda.model';

/** De dónde salen los reportes personalizables: la plataforma (todas las empresas) o una empresa
 * (solo la suya). Las dos APIs tienen la misma forma, así que el constructor es el mismo. */
export interface FuenteReportes {
  catalogo(): Observable<CatalogoReporte[]>;
  reporte(tipo: string, opciones: OpcionesReporte): Observable<ReportePlataforma>;
  /** Reporte por comando (texto o voz): la IA lo traduce a las opciones del constructor. */
  reporteIA(pedido: string): Observable<ReporteIAPlataforma>;
  exportar(tipo: string, formato: FormatoReporte, opciones: OpcionesReporte): Observable<Blob>;
  enviar(tipo: string, destinatario: string, formato: FormatoReporte, opciones: OpcionesReporte): Observable<{ enviado: boolean }>;
}

/** Respaldo y restauración: de una empresa o del sistema completo. */
export interface FuenteRespaldo {
  descargar(): Observable<Blob>;
  /** simular: verifica el archivo y devuelve qué se restauraría, sin cambiar nada. */
  restaurar(archivo: File, simular: boolean): Observable<Restauracion>;
}

function criterioATexto(c: { columna: string; operador: string; valor: string }): string {
  return `${c.columna}|${c.operador}|${c.valor.trim()}`;
}

/** Las opciones del constructor como parámetros de la URL (las listas se repiten). */
export function parametrosDe(opciones: OpcionesReporte): HttpParams {
  let params = new HttpParams();
  if (opciones.desde) params = params.set('desde', opciones.desde);
  if (opciones.hasta) params = params.set('hasta', opciones.hasta);
  for (const columna of opciones.columnas) params = params.append('columnas', columna);
  for (const criterio of opciones.criterios.filter((c) => c.valor.trim())) params = params.append('criterio', criterioATexto(criterio));
  if (opciones.orden) params = params.set('orden', opciones.orden);
  if (opciones.descendente !== undefined) params = params.set('descendente', String(opciones.descendente));
  return params;
}

/** base: /api/v1/plataforma/reportes o /api/v1/reportes/personalizados */
export function reportesHttp(http: HttpClient, base: string): FuenteReportes {
  return {
    catalogo: () => http.get<CatalogoReporte[]>(base),
    reporte: (tipo, opciones) => http.get<ReportePlataforma>(`${base}/${tipo}`, { params: parametrosDe(opciones) }),
    reporteIA: (pedido) => http.post<ReporteIAPlataforma>(`${base}/ia`, { pedido }),
    exportar: (tipo, formato, opciones) =>
      http.get(`${base}/${tipo}/exportar`, { params: parametrosDe(opciones).set('formato', formato), responseType: 'blob' }),
    enviar: (tipo, destinatario, formato, opciones) =>
      http.post<{ enviado: boolean }>(`${base}/${tipo}/enviar`, {
        destinatario,
        formato,
        desde: opciones.desde || null,
        hasta: opciones.hasta || null,
        columnas: opciones.columnas,
        criterios: opciones.criterios.filter((c) => c.valor.trim()).map(criterioATexto),
        orden: opciones.orden || null,
        descendente: opciones.descendente ?? null,
      }),
  };
}

/** base: /api/v1/respaldo, /api/v1/plataforma/respaldo o /api/v1/plataforma/tiendas/<id>/respaldo */
export function respaldoHttp(http: HttpClient, base: string): FuenteRespaldo {
  return {
    descargar: () => http.get(base, { responseType: 'blob' }),
    restaurar: (archivo, simular) => {
      const datos = new FormData();
      datos.append('archivo', archivo, archivo.name);
      datos.append('simular', String(simular));
      return http.post<Restauracion>(`${base}/restaurar`, datos);
    },
  };
}
