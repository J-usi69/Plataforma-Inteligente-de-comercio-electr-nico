import { APP_BASE_HREF } from '@angular/common';
import { ApplicationConfig, inject, isDevMode, provideAppInitializer, provideBrowserGlobalErrorListeners } from '@angular/core';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { provideRouter } from '@angular/router';
import { provideServiceWorker } from '@angular/service-worker';
import { routes } from './app.routes';
import { authInterceptor } from './core/interceptors/auth.interceptor';
import { offlineInterceptor } from './core/offline/offline.interceptor';
import { tiendaInterceptor } from './core/interceptors/tienda.interceptor';
import { TiendaService, baseDeLaApp } from './core/services/tienda.service';

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    // /t/<empresa>/ como base: la misma app sirve a cada empresa en su dirección
    { provide: APP_BASE_HREF, useValue: baseDeLaApp() },
    provideRouter(routes),
    // El último: sin conexión contesta la API local (IndexedDB) y lo registrado entra a la cola
    provideHttpClient(withInterceptors([tiendaInterceptor, authInterceptor, offlineInterceptor])),
    // La marca y las funciones del plan se conocen antes de pintar la web (sin parpadeo de colores)
    provideAppInitializer(() => inject(TiendaService).cargar()),
    // PWA: guarda la app (JS, CSS, íconos) para que abra sin Internet. Solo en producción: en
    // desarrollo cachearía cada cambio. Ver ngsw-config.json
    provideServiceWorker('ngsw-worker.js', {
      enabled: !isDevMode(),
      registrationStrategy: 'registerWhenStable:30000',
    }),
  ],
};
