import { Routes } from '@angular/router';
import { Login } from './features/auth/login/login';
import { Listado } from './features/catalogo/listado/listado';
import { MisReservas } from './features/reservas/mis-reservas/mis-reservas';
import { Carrito } from './features/ventas/carrito/carrito';
import { Dashboard } from './features/admin/dashboard/dashboard';

export const routes: Routes = [
  { path: '', redirectTo: 'catalogo', pathMatch: 'full' },
  { path: 'login', component: Login },
  { path: 'catalogo', component: Listado },
  { path: 'reservas', component: MisReservas },
  { path: 'carrito', component: Carrito },
  { path: 'admin', component: Dashboard },
];
