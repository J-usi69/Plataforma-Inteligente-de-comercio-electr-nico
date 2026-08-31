import 'package:go_router/go_router.dart';

import '../features/auth/login_screen.dart';
import '../features/catalogo/catalogo_screen.dart';
import '../features/reservas/reservas_screen.dart';
import '../features/ventas/carrito_screen.dart';
import '../features/vestidor_ar/vestidor_ar_screen.dart';

final GoRouter appRouter = GoRouter(
  initialLocation: '/catalogo',
  routes: [
    GoRoute(path: '/login', builder: (context, state) => const LoginScreen()),
    GoRoute(path: '/catalogo', builder: (context, state) => const CatalogoScreen()),
    GoRoute(path: '/reservas', builder: (context, state) => const ReservasScreen()),
    GoRoute(path: '/carrito', builder: (context, state) => const CarritoScreen()),
    GoRoute(path: '/vestidor-ar', builder: (context, state) => const VestidorArScreen()),
  ],
);
