import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, throwError } from 'rxjs';
import { TiendaService } from '../services/tienda.service';

/** Cada pedido a la API va a la empresa de la URL (cabecera X-Tienda). Si el pedido ya trae su
 * propia X-Tienda (el alta de una empresa nueva habla con la suya), se respeta.
 * Un 402 es un rechazo por el plan o por la suscripción vencida: se avisa en toda la web. */
export const tiendaInterceptor: HttpInterceptorFn = (req, next) => {
  const tienda = inject(TiendaService);
  const esApi = req.url.startsWith('/api/');
  const pedido =
    esApi && tienda.slug && !req.headers.has('X-Tienda') ? req.clone({ setHeaders: { 'X-Tienda': tienda.slug } }) : req;

  return next(pedido).pipe(
    catchError((err: unknown) => {
      if (esApi && err instanceof HttpErrorResponse && err.status === 402) {
        tienda.avisoPlan.set(err.error?.detail ?? 'Esta función no está incluida en el plan de la tienda.');
      }
      return throwError(() => err);
    }),
  );
};
