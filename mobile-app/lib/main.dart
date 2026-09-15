import 'package:flutter/material.dart';
import 'package:flutter_stripe/flutter_stripe.dart';

import 'core/config/env.dart';
import 'core/router.dart';
import 'core/services/push_notification_service.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  Stripe.publishableKey = Env.stripePublishableKey;
  await Stripe.instance.applySettings();
  await PushNotificationService().inicializar();
  runApp(const FashionStoreApp());
}

class FashionStoreApp extends StatelessWidget {
  const FashionStoreApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp.router(
      title: 'FashionStore',
      theme: ThemeData(colorSchemeSeed: Colors.indigo, useMaterial3: true),
      routerConfig: appRouter,
    );
  }
}
