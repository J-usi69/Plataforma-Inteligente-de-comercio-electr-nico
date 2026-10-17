import { Routes } from '@angular/router';
import { Dashboard } from './features/admin/dashboard/dashboard';
import { Login } from './features/auth/login/login';
import { Listado } from './features/catalogo/listado/listado';
import { GestionarReservas } from './features/encargado/gestionar-reservas/gestionar-reservas';
import { PanelProveedor } from './features/proveedor/panel-proveedor/panel-proveedor';
import { MisReservas } from './features/reservas/mis-reservas/mis-reservas';
import { CajaPos } from './features/ventas/caja-pos/caja-pos';
import { Carrito } from './features/ventas/carrito/carrito';
import { MisCompras } from './features/ventas/mis-compras/mis-compras';

export const routes: Routes = [
  { path: '', redirectTo: 'catalogo', pathMatch: 'full' },
  { path: 'login', component: Login },
  { path: 'catalogo', component: Listado },
  { path: 'reservas', component: MisReservas },
  { path: 'carrito', component: Carrito },
  { path: 'mis-compras', component: MisCompras },
  { path: 'encargado', component: GestionarReservas },
  { path: 'caja', component: CajaPos },
  { path: 'proveedor', component: PanelProveedor },
  {
    path: 'admin/plan',
    loadComponent: () => import('./features/admin/mi-plan/mi-plan').then((m) => m.MiPlan),
  },
  { path: 'admin', component: Dashboard },
  // SaaS: alta pública de empresas y panel del superadmin (son de la plataforma, no de una empresa)
  {
    path: 'crear-tienda',
    loadComponent: () => import('./features/plataforma/registro-tienda/registro-tienda').then((m) => m.RegistroTienda),
  },
  {
    path: 'plataforma',
    loadComponent: () => import('./features/plataforma/panel-plataforma/panel-plataforma').then((m) => m.PanelPlataforma),
  },
  // CU-14: probador AR (MediaPipe) a pantalla completa, lo abre la app móvil dentro de un WebView
  {
    path: 'probador-ar',
    loadComponent: () => import('./features/catalogo/probador-ar/probador-ar').then((m) => m.ProbadorAr),
  },
];
