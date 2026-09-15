import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../features/asistente/chat_screen.dart';
import '../features/auth/login_screen.dart';
import '../features/auth/profile_screen.dart';
import '../features/auth/register_screen.dart';
import '../features/catalogo/catalogo_screen.dart';
import '../features/reservas/reservar_screen.dart';
import '../features/reservas/reservas_screen.dart';
import '../features/sucursales/sucursales_screen.dart';
import '../features/ventas/carrito_screen.dart';
import '../features/ventas/mis_compras_screen.dart';
import '../features/vestidor_ar/vestidor_ar_screen.dart';

// Permite que una pantalla (ej. CatalogoScreen) se entere cuando vuelve a
// quedar visible tras cerrarse una ruta apilada encima (ej. el login), para
// poder refrescar datos que dependen de la sesión sin esperar a un pull-to-refresh.
final RouteObserver<PageRoute> routeObserver = RouteObserver<PageRoute>();

final GoRouter appRouter = GoRouter(
  initialLocation: '/catalogo',
  observers: [routeObserver],
  routes: [
    GoRoute(path: '/login', builder: (context, state) => const LoginScreen()),
    GoRoute(path: '/register', builder: (context, state) => const RegisterScreen()),
    GoRoute(path: '/perfil', builder: (context, state) => const ProfileScreen()),
    GoRoute(path: '/catalogo', builder: (context, state) => const CatalogoScreen()),
    GoRoute(path: '/sucursales', builder: (context, state) => const SucursalesScreen()),
    GoRoute(path: '/reservas', builder: (context, state) => const ReservasScreen()),
    GoRoute(
      path: '/reservar',
      builder: (context, state) => ReservarScreen(
        prenda: state.extra as Map<String, dynamic>,
      ),
    ),
    GoRoute(path: '/carrito', builder: (context, state) => const CarritoScreen()),
    GoRoute(path: '/mis-compras', builder: (context, state) => const MisComprasScreen()),
    GoRoute(
      path: '/vestidor-ar',
      builder: (context, state) => VestidorArScreen(
        prenda: state.extra as Map<String, dynamic>?,
      ),
    ),
    GoRoute(path: '/asistente', builder: (context, state) => const ChatScreen()),
  ],
);
