import { APP_BASE_HREF } from '@angular/common';
import { ApplicationConfig, inject, provideAppInitializer, provideBrowserGlobalErrorListeners } from '@angular/core';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { provideRouter } from '@angular/router';
import { routes } from './app.routes';
import { authInterceptor } from './core/interceptors/auth.interceptor';
import { tiendaInterceptor } from './core/interceptors/tienda.interceptor';
import { TiendaService, baseDeLaApp } from './core/services/tienda.service';

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    // /t/<empresa>/ como base: la misma app sirve a cada empresa en su dirección
    { provide: APP_BASE_HREF, useValue: baseDeLaApp() },
    provideRouter(routes),
    provideHttpClient(withInterceptors([tiendaInterceptor, authInterceptor])),
    // La marca y las funciones del plan se conocen antes de pintar la web (sin parpadeo de colores)
    provideAppInitializer(() => inject(TiendaService).cargar()),
  ],
};
