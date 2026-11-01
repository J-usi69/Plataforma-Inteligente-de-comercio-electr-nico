import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_stripe/flutter_stripe.dart';

import 'core/config/env.dart';
import 'core/offline/sincronizacion_service.dart';
import 'core/router.dart';
import 'core/services/api_service.dart';
import 'core/services/push_notification_service.dart';
import 'features/offline/barra_conexion.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  Stripe.publishableKey = Env.stripePublishableKey;
  await Stripe.instance.applySettings();
  // Sesión, empresa y datos guardados antes de la primera pantalla: así la app abre igual sin
  // conexión, con la sesión iniciada y el catálogo guardado
  await ApiService().restaurarSesion();
  final sync = SincronizacionService();
  await sync.cargarLocal();
  await PushNotificationService().inicializar();
  runApp(const FashionStoreApp());
  unawaited(sync.iniciar());
  unawaited(ApiService().validarSesion());
}

class FashionStoreApp extends StatelessWidget {
  const FashionStoreApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp.router(
      title: 'FashionStore',
      theme: ThemeData(colorSchemeSeed: Colors.indigo, useMaterial3: true),
      routerConfig: appRouter,
      scaffoldMessengerKey: avisosGlobales,
      // Barra de conexión y operaciones pendientes al pie de todas las pantallas
      builder: (context, child) => ConBarraDeConexion(child: child ?? const SizedBox.shrink()),
    );
  }
}
