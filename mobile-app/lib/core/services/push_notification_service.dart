import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart' show TargetPlatform, defaultTargetPlatform, kIsWeb;

import 'api_service.dart';

// El sistema operativo ya muestra la notificación usando el campo "notification"
// del mensaje cuando la app está en segundo plano o cerrada; este handler solo
// existe porque el plugin lo exige para poder despertar la app en ese caso.
@pragma('vm:entry-point')
Future<void> manejarMensajeEnSegundoPlano(RemoteMessage mensaje) async {}

// Notificaciones push (solo app móvil, por ahora solo Android) para cambios de
// estado de reserva/venta, nuevas prendas/colecciones publicadas, y avisos de
// disponibilidad a Administradores. La config de Firebase se toma del
// android/app/google-services.json nativo (plugin de Gradle), no hace falta
// pasar nada por --dart-define. Si ese archivo no está o falla la inicialización,
// todos los métodos no hacen nada: la app sigue funcionando normal, solo sin push.
class PushNotificationService {
  static final PushNotificationService _instance = PushNotificationService._internal();
  factory PushNotificationService() => _instance;
  PushNotificationService._internal();

  bool _inicializado = false;

  bool get _esAndroid => !kIsWeb && defaultTargetPlatform == TargetPlatform.android;

  Future<void> inicializar() async {
    if (!_esAndroid) return;
    try {
      await Firebase.initializeApp();
      FirebaseMessaging.onBackgroundMessage(manejarMensajeEnSegundoPlano);
      await FirebaseMessaging.instance.requestPermission();
      FirebaseMessaging.instance.onTokenRefresh.listen(_registrarToken);
      _inicializado = true;
    } catch (_) {
      // google-services.json ausente, Play Services no disponible, etc.: se ignora.
    }
  }

  // Se llama después de un login exitoso para asociar este dispositivo al usuario.
  Future<void> registrarTokenSiCorresponde() async {
    if (!_inicializado) return;
    try {
      final token = await FirebaseMessaging.instance.getToken();
      if (token != null) await _registrarToken(token);
    } catch (_) {}
  }

  Future<void> _registrarToken(String token) async {
    try {
      await ApiService().post('/api/v1/notificaciones/token', {
        'token': token,
        'plataforma': 'android',
      });
    } catch (_) {}
  }
}
