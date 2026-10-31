import { HttpErrorResponse, HttpInterceptorFn, HttpResponse } from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, from, map, throwError } from 'rxjs';
import { ApiLocal } from './api-local';
import { SincronizacionService, sinConexion } from './sincronizacion.service';

/** Sin conexión el sistema sigue funcionando igual: lo que el catálogo, las reservas y la caja
 * piden a la API lo contesta ApiLocal desde IndexedDB, y lo que registran entra a la cola. Con
 * conexión todo va al servidor; si un pedido de lectura no llega, se contesta con lo guardado. */
export const offlineInterceptor: HttpInterceptorFn = (req, next) => {
  const local = inject(ApiLocal);
  const sync = inject(SincronizacionService);
  if (!sync.disponible() || !local.atiende(req)) {
    return next(req);
  }
  if (local.soloLocal(req) || !sync.enLinea()) {
    return from(local.responder(req));
  }
  return next(req).pipe(
    map((evento) => (evento instanceof HttpResponse && local.esMisReservas(req) ? local.conPendientes(evento) : evento)),
    catchError((err: unknown) => {
      if (!sinConexion(err)) {
        return throwError(() => err);
      }
      sync.marcarSinConexion();
      if (req.method === 'GET') {
        return from(local.responder(req)); // se lee de lo guardado
      }
      // Una escritura que no llegó no se repite sola (podría haber llegado sin respuesta): el
      // siguiente intento ya va a la cola, que no duplica
      return throwError(
        () => new HttpErrorResponse({ status: 503, error: { detail: 'Se cortó la conexión. Intentá de nuevo: quedará guardado en este dispositivo y se enviará solo.' } }),
      );
    }),
  );
};
