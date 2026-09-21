import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart' show TargetPlatform, defaultTargetPlatform, kIsWeb;
import 'package:flutter_local_notifications/flutter_local_notifications.dart';

import 'api_service.dart';

// El sistema operativo ya muestra la notificación usando el campo "notification"
// del mensaje cuando la app está en segundo plano o cerrada; este handler solo
// existe porque el plugin lo exige para poder despertar la app en ese caso.
@pragma('vm:entry-point')
Future<void> manejarMensajeEnSegundoPlano(RemoteMessage mensaje) async {}

const _canalAndroid = AndroidNotificationChannel(
  'fashionstore_default',
  'Notificaciones de FashionStore',
  description: 'Avisos de reservas, ventas y novedades del catálogo',
  importance: Importance.high,
);

// Notificaciones push (solo app móvil, por ahora solo Android) para cambios de
// estado de reserva/venta, nuevas prendas/colecciones publicadas, y avisos de
// disponibilidad a Administradores. La config de Firebase se toma del
// android/app/google-services.json nativo (plugin de Gradle), no hace falta
// pasar nada por --dart-define. Si ese archivo no está o falla la inicialización,
// todos los métodos no hacen nada: la app sigue funcionando normal, solo sin push.
//
// Con la app en segundo plano o cerrada, Android muestra el push solo con lo que
// manda FCM. Pero con la app ABIERTA, FCM no muestra nada por su cuenta -hay que
// mostrarlo nosotros a mano con flutter_local_notifications al recibir onMessage.
class PushNotificationService {
  static final PushNotificationService _instance = PushNotificationService._internal();
  factory PushNotificationService() => _instance;
  PushNotificationService._internal();

  bool _inicializado = false;
  final _notificacionesLocales = FlutterLocalNotificationsPlugin();

  bool get _esAndroid => !kIsWeb && defaultTargetPlatform == TargetPlatform.android;

  Future<void> inicializar() async {
    if (!_esAndroid) return;
    try {
      await Firebase.initializeApp();
      await _inicializarNotificacionesLocales();
      FirebaseMessaging.onBackgroundMessage(manejarMensajeEnSegundoPlano);
      await FirebaseMessaging.instance.requestPermission();
      FirebaseMessaging.instance.onTokenRefresh.listen(_registrarToken);
      FirebaseMessaging.onMessage.listen(_mostrarNotificacionEnPrimerPlano);
      _inicializado = true;
    } catch (_) {
      // google-services.json ausente, Play Services no disponible, etc.: se ignora.
    }
  }

  Future<void> _inicializarNotificacionesLocales() async {
    const configAndroid = AndroidInitializationSettings('@mipmap/ic_launcher');
    await _notificacionesLocales.initialize(
      const InitializationSettings(android: configAndroid),
    );
    await _notificacionesLocales
        .resolvePlatformSpecificImplementation<AndroidFlutterLocalNotificationsPlugin>()
        ?.createNotificationChannel(_canalAndroid);
  }

  Future<void> _mostrarNotificacionEnPrimerPlano(RemoteMessage mensaje) async {
    final notificacion = mensaje.notification;
    if (notificacion == null) return;
    await _notificacionesLocales.show(
      mensaje.hashCode,
      notificacion.title,
      notificacion.body,
      NotificationDetails(
        android: AndroidNotificationDetails(
          _canalAndroid.id,
          _canalAndroid.name,
          channelDescription: _canalAndroid.description,
          importance: Importance.high,
          priority: Priority.high,
        ),
      ),
    );
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
