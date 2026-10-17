import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { AuthService } from '../services/auth.service';
import { PlataformaService } from '../services/plataforma.service';

/** La API de la plataforma usa la sesión del superadmin; todo lo demás, la sesión de la empresa.
 * Si el pedido ya trae su propio token (alta de una empresa nueva), se respeta. */
export const authInterceptor: HttpInterceptorFn = (req, next) => {
  if (req.headers.has('Authorization')) {
    return next(req);
  }
  const deLaPlataforma = req.url.startsWith('/api/v1/plataforma/');
  const token = deLaPlataforma ? inject(PlataformaService).token() : inject(AuthService).token();
  return next(token ? req.clone({ setHeaders: { Authorization: `Bearer ${token}` } }) : req);
};
