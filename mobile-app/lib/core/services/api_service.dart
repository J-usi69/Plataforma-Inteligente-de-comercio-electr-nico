import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;

import '../config/env.dart';
import '../offline/api_local.dart';
import '../offline/sincronizacion_service.dart';

/// Respuesta de error del servidor. toString() conserva el formato de siempre (`Exception: <detalle>`),
/// que las pantallas muestran quitando el prefijo.
class ApiException implements Exception {
  final int status;
  final String mensaje;
  const ApiException(this.status, this.mensaje);

  @override
  String toString() => 'Exception: $mensaje';
}

/// El pedido no llegó al servidor y no se puede responder con lo guardado en el teléfono.
class SinConexion implements Exception {
  final String mensaje;
  const SinConexion(this.mensaje);

  @override
  String toString() => 'Exception: $mensaje';
}

// 502/503/504: el proxy (Railway) no llegó al backend
const _sinServidor = {502, 503, 504};

/// El pedido no llegó al servidor (sin red, servidor caído o sin respuesta a tiempo).
bool sinConexion(Object error) =>
    error is http.ClientException ||
    error is TimeoutException ||
    (error is ApiException && _sinServidor.contains(error.status));

class ApiService {
  static final ApiService _instance = ApiService._internal();
  factory ApiService() => _instance;
  ApiService._internal();

  // La sesión queda cifrada en el Keystore de Android (o el Keychain de iOS): sobrevive al cierre
  // de la app, que es lo que permite trabajar sin conexión con la sesión ya iniciada
  static const _almacenSeguro = FlutterSecureStorage();

  String baseUrl = Env.apiUrl;
  String? token;
  Map<String, dynamic>? currentUser;

  /// Empresa (tenant) con la que trabaja la app: viaja en la cabecera X-Tienda.
  String tienda = Env.tienda;

  /// Marca y funciones del plan de la empresa (GET /api/v1/tienda). La app toma sus colores y su
  /// logo: el tema escucha este valor.
  final marca = ValueNotifier<Map<String, dynamic>?>(null);
  Map<String, dynamic>? get tiendaInfo => marca.value;
  set tiendaInfo(Map<String, dynamic>? info) => marca.value = info;

  void setToken(String? newToken) {
    token = newToken;
  }

  void setCurrentUser(Map<String, dynamic>? user) {
    currentUser = user;
  }

  bool get isLoggedIn => token != null && currentUser != null;

  String get tiendaNombre => tiendaInfo?['nombre'] as String? ?? 'FashionStore';

  /// Si el plan de la empresa incluye la función. Sin saberlo todavía (nunca hubo conexión), se
  /// permite: el backend igual rechaza lo que el plan no incluye.
  bool tiene(String funcion) {
    final funciones = tiendaInfo?['funciones'];
    return funciones is! Map || funciones[funcion] != false;
  }

  List<String> get roles => ((currentUser?['roles'] as List?) ?? const []).map((r) => '$r').toList();
  bool get esPersonal => roles.any(const {'Cajero', 'Encargado', 'Administrador'}.contains);
  bool get puedeCobrarEnCaja => roles.any(const {'Cajero', 'Administrador'}.contains);

  Map<String, String> get _headers {
    final map = <String, String>{
      'Content-Type': 'application/json',
      'Accept': 'application/json',
      'X-Tienda': tienda,
    };
    if (token != null) {
      map['Authorization'] = 'Bearer $token';
    }
    return map;
  }

  Uri _uri(String path) {
    if (!path.startsWith('/')) path = '/$path';
    return Uri.parse('$baseUrl$path');
  }

  // Sin timeout, un corte de red silencioso (ej. el tunel de `adb reverse`
  // cayendose) dejaba la pantalla cargando para siempre en vez de mostrar
  // un error.
  static const _timeout = Duration(seconds: 15);

  Future<dynamic> get(String path) => _pedir('GET', path);

  Future<dynamic> post(String path, Map<String, dynamic> body) => _pedir('POST', path, body);

  Future<dynamic> put(String path, Map<String, dynamic> body) => _pedir('PUT', path, body);

  Future<dynamic> delete(String path) => _pedir('DELETE', path);

  /// Operación sin conexión transparente: si el pedido no llega al servidor, el catálogo y las
  /// reservas responden con lo guardado en SQLite (ApiLocal) y las pantallas siguen igual.
  Future<dynamic> _pedir(String metodo, String path, [Map<String, dynamic>? body]) async {
    final local = ApiLocal();
    final sync = SincronizacionService();
    // Ya se sabe que no hay conexión: lo que se puede responder con lo guardado no espera al timeout
    if (!sync.enLinea && sync.tieneDatos && local.atiende(metodo, path)) {
      return local.responder(metodo, path, body);
    }
    try {
      final datos = await directo(metodo, path, body: body);
      sync.marcarEnLinea();
      return local.esMisReservas(metodo, path) ? await local.conPendientes(datos) : datos;
    } catch (e) {
      if (!sinConexion(e)) rethrow;
      // Una escritura que no tuvo respuesta a tiempo pudo haber llegado: no se repite por la cola
      if (metodo != 'GET' && e is TimeoutException) {
        throw const SinConexion(
          'El servidor no respondió a tiempo. Revisá si quedó registrada antes de volver a intentarlo.',
        );
      }
      sync.marcarSinConexion();
      if (local.atiende(metodo, path)) return local.responder(metodo, path, body);
      throw const SinConexion('Sin conexión: esto necesita Internet. El catálogo y las reservas siguen funcionando.');
    }
  }

  /// Pedido al servidor sin respuesta local (lo usa la sincronización).
  Future<dynamic> directo(String metodo, String path, {Map<String, dynamic>? body, Duration timeout = _timeout}) async {
    final uri = _uri(path);
    final cuerpo = body == null ? null : jsonEncode(body);
    final respuesta = switch (metodo) {
      'GET' => http.get(uri, headers: _headers),
      'POST' => http.post(uri, headers: _headers, body: cuerpo),
      'PUT' => http.put(uri, headers: _headers, body: cuerpo),
      'DELETE' => http.delete(uri, headers: _headers),
      _ => throw ArgumentError.value(metodo, 'metodo'),
    };
    return _decode(await respuesta.timeout(timeout));
  }

  dynamic _decode(http.Response response) {
    if (response.statusCode >= 200 && response.statusCode < 300) {
      if (response.body.isEmpty) return null;
      return jsonDecode(utf8.decode(response.bodyBytes));
    }
    String message = 'Error ${response.statusCode}';
    try {
      final decoded = jsonDecode(utf8.decode(response.bodyBytes));
      if (decoded is Map && decoded.containsKey('detail')) {
        message = decoded['detail'].toString();
      }
    } catch (_) {}
    throw ApiException(response.statusCode, message);
  }

  // --- Sesión y empresa ---

  /// Al arrancar la app: la empresa, la sesión y la marca guardadas.
  Future<void> restaurarSesion() async {
    try {
      final guardado = await _almacenSeguro.readAll();
      tienda = guardado['tienda'] ?? Env.tienda;
      final usuario = guardado['usuario'];
      if (guardado['token'] != null && usuario != null) {
        token = guardado['token'];
        currentUser = Map<String, dynamic>.from(jsonDecode(usuario) as Map);
      }
      final info = guardado['tienda_info'];
      final marca = info == null ? null : Map<String, dynamic>.from(jsonDecode(info) as Map);
      tiendaInfo = marca?['slug'] == tienda ? marca : null;
    } catch (_) {
      // Almacén ilegible (p. ej. un respaldo restaurado en otro teléfono): se empieza sin sesión
      token = null;
      currentUser = null;
    }
  }

  Future<void> _guardarSesion() async {
    try {
      await _almacenSeguro.write(key: 'tienda', value: tienda);
      if (isLoggedIn) {
        await _almacenSeguro.write(key: 'token', value: token);
        await _almacenSeguro.write(key: 'usuario', value: jsonEncode(currentUser));
      } else {
        await _almacenSeguro.delete(key: 'token');
        await _almacenSeguro.delete(key: 'usuario');
      }
    } catch (_) {}
  }

  /// Marca, funciones del plan y vigencia de la suscripción de la empresa (público).
  Future<Map<String, dynamic>> cargarTienda({Duration timeout = _timeout}) async {
    final info = Map<String, dynamic>.from(await directo('GET', '/api/v1/tienda', timeout: timeout) as Map);
    tiendaInfo = info;
    try {
      await _almacenSeguro.write(key: 'tienda_info', value: jsonEncode(info));
    } catch (_) {}
    return info;
  }

  /// Cambia la empresa con la que trabaja la app (al iniciar sesión). Falla si no existe.
  Future<void> cambiarTienda(String slug) async {
    final anterior = tienda;
    final marcaAnterior = tiendaInfo;
    tienda = slug;
    try {
      await cargarTienda();
    } catch (_) {
      tienda = anterior;
      tiendaInfo = marcaAnterior;
      rethrow;
    }
    await _guardarSesion();
  }

  /// Al arrancar con una sesión guardada: si el servidor dice que venció, se cierra (las
  /// operaciones pendientes quedan para cuando vuelva a entrar). Sin conexión se conserva.
  Future<void> validarSesion() async {
    if (!isLoggedIn) return;
    try {
      await getProfile();
    } on ApiException catch (e) {
      if (e.status != 401) return;
      setToken(null);
      setCurrentUser(null);
      await _guardarSesion();
      await SincronizacionService().alCambiarUsuario();
    } catch (_) {}
  }

  // --- Métodos de Casos de Uso CU-01 a CU-08 ---

  // CU-01: Registro de Cliente
  Future<Map<String, dynamic>> register({
    required String correo,
    required String password,
    String? celular,
  }) async {
    final body = {
      'correo': correo,
      'password': password,
      if (celular != null && celular.isNotEmpty) 'celular': celular,
    };
    final res = await post('/api/v1/auth/register', body);
    return Map<String, dynamic>.from(res);
  }

  // CU-02: Login
  Future<Map<String, dynamic>> login({
    required String login,
    required String password,
  }) async {
    final res = await post('/api/v1/auth/login', {
      'login': login,
      'password': password,
    });
    final map = Map<String, dynamic>.from(res);
    setToken(map['access_token'] as String?);
    setCurrentUser(Map<String, dynamic>.from(map['usuario'] as Map));
    await _guardarSesion();
    // Baja el paquete para trabajar sin conexión y envía lo que este usuario dejó pendiente
    unawaited(SincronizacionService().alCambiarUsuario());
    return map;
  }

  // CU-03: Logout
  Future<void> logout() async {
    try {
      if (token != null) {
        await post('/api/v1/auth/logout', {});
      }
    } catch (_) {}
    setToken(null);
    setCurrentUser(null);
    await _guardarSesion();
    await SincronizacionService().alCambiarUsuario();
  }

  // CU-01: Perfil
  Future<Map<String, dynamic>> getProfile() async {
    final res = await get('/api/v1/auth/me');
    final map = Map<String, dynamic>.from(res);
    setCurrentUser(map);
    await _guardarSesion();
    return map;
  }

  // CU-06: Sucursales
  Future<List<dynamic>> getSucursales({int? ciudadId}) async {
    final path = ciudadId != null
        ? '/api/v1/sucursales?ciudad_id=$ciudadId'
        : '/api/v1/sucursales';
    final res = await get(path);
    return res is List ? res : [];
  }

  // CU-06: Ciudades
  Future<List<dynamic>> getCiudades() async {
    final res = await get('/api/v1/sucursales/ciudades');
    return res is List ? res : [];
  }

  // CU-07: Proveedores
  Future<List<dynamic>> getProveedores() async {
    final res = await get('/api/v1/proveedores');
    return res is List ? res : [];
  }

  // CU-08 / CU-12: Catálogo de Prendas (con filtros)
  Future<List<dynamic>> getPrendas({int? categoriaId, int? tallaId, int? colorId}) async {
    final params = <String, String>{};
    if (categoriaId != null) params['categoria_id'] = '$categoriaId';
    if (tallaId != null) params['talla_id'] = '$tallaId';
    if (colorId != null) params['color_id'] = '$colorId';
    final query = params.isEmpty ? '' : '?${Uri(queryParameters: params).query}';
    final res = await get('/api/v1/prendas$query');
    return res is List ? res : [];
  }

  // CU-08: Categorías
  Future<List<dynamic>> getCategorias() async {
    final res = await get('/api/v1/prendas/categorias');
    return res is List ? res : [];
  }

  // CU-14: Vestidor virtual (RA) - capacidades del servidor
  Future<Map<String, dynamic>> getTryOnCapabilities() async {
    final res = await get('/api/v1/vestidor-ar/capabilities');
    return Map<String, dynamic>.from(res);
  }

  // CU-14: Crear generación del vestidor virtual (foto de la persona + prenda)
  Future<Map<String, dynamic>> createTryOnJob({
    required int prendaId,
    required List<int> personaBytes,
    required String personaFilename,
    int? varianteId,
  }) async {
    final request = http.MultipartRequest('POST', _uri('/api/v1/vestidor-ar/jobs'));
    request.headers['X-Tienda'] = tienda;
    if (token != null) {
      request.headers['Authorization'] = 'Bearer $token';
    }
    request.fields['prenda_id'] = prendaId.toString();
    if (varianteId != null) {
      request.fields['variante_id'] = varianteId.toString();
    }
    request.files.add(
      http.MultipartFile.fromBytes('persona', personaBytes, filename: personaFilename),
    );

    final streamedResponse = await request.send();
    final response = await http.Response.fromStream(streamedResponse);
    return Map<String, dynamic>.from(_decode(response) as Map);
  }

  // CU-14: Consultar estado de una generación del vestidor virtual
  Future<Map<String, dynamic>> getTryOnJob(String jobId) async {
    final res = await get('/api/v1/vestidor-ar/jobs/$jobId');
    return Map<String, dynamic>.from(res);
  }

  // CU-09: Tallas y colores (para filtros del catálogo)
  Future<List<dynamic>> getTallas() async {
    final res = await get('/api/v1/catalogo-maestro/tallas');
    return res is List ? res : [];
  }

  Future<List<dynamic>> getColores() async {
    final res = await get('/api/v1/catalogo-maestro/colores');
    return res is List ? res : [];
  }

  // CU-11: Variantes de una prenda (talla + color)
  Future<List<dynamic>> getVariantes(int prendaId) async {
    final res = await get('/api/v1/prendas/$prendaId/variantes');
    return res is List ? res : [];
  }

  // CU-13: Disponibilidad de una variante por sucursal
  Future<List<dynamic>> getDisponibilidad(int varianteId) async {
    final res = await get('/api/v1/inventario/disponibilidad/$varianteId');
    return res is List ? res : [];
  }

  // CU-15: Crear una reserva (sin conexión queda en la cola del teléfono: Parcial 2, CU-10)
  Future<Map<String, dynamic>> crearReserva({
    required int sucursalId,
    required int varianteId,
    required int cantidad,
    String? horarioAtencion,
  }) async {
    final res = await post('/api/v1/reservas', {
      'sucursal_id': sucursalId,
      if (horarioAtencion != null && horarioAtencion.isNotEmpty) 'horario_atencion': horarioAtencion,
      'detalles': [
        {'variante_id': varianteId, 'cantidad': cantidad},
      ],
    });
    return Map<String, dynamic>.from(res);
  }

  // CU-16: Consultar mis reservas
  Future<List<dynamic>> getMisReservas() async {
    final res = await get('/api/v1/reservas');
    return res is List ? res : [];
  }

  // CU-16: Cancelar una reserva
  Future<Map<String, dynamic>> cancelarReserva(int reservaId) async {
    final res = await post('/api/v1/reservas/$reservaId/cancelar', {});
    return Map<String, dynamic>.from(res);
  }

  // --- Ventas y Pagos Digitales Móviles ---

  // Crear venta digital desde app móvil (retiro en sucursal)
  Future<Map<String, dynamic>> crearVentaDigital({
    required int sucursalId,
    required List<Map<String, dynamic>> detalles,
  }) async {
    final body = {
      'sucursal_id': sucursalId,
      'detalles': detalles,
    };
    final res = await post('/api/v1/ventas/digital', body);
    return Map<String, dynamic>.from(res);
  }

  // Procesar pago digital (Tarjeta ya confirmada con Stripe)
  Future<Map<String, dynamic>> pagarVentaDigital({
    required int ventaId,
    required String metodoPago,
    String? stripePaymentIntentId,
  }) async {
    final body = {
      'metodo_pago': metodoPago,
      if (stripePaymentIntentId != null)
        'stripe_payment_intent_id': stripePaymentIntentId,
    };
    final res = await post('/api/v1/ventas/$ventaId/pagar-digital', body);
    return Map<String, dynamic>.from(res);
  }

  // Crea un PaymentIntent real en Stripe para el pago con tarjeta; devuelve el client_secret.
  Future<String> crearIntentoPagoStripe(int ventaId) async {
    final res = await post('/api/v1/ventas/$ventaId/crear-intento-pago', {});
    return res['client_secret'] as String;
  }

  // Pago con QR (Libélula). Devuelve qr_url (URL o data URI), url_pasarela, monto y modo_prueba
  // (backend sin appkey de Libélula: QR de demostración y pago con "Simular pago").
  Future<Map<String, dynamic>> generarQrLibelula(int ventaId) async {
    final res = await post('/api/v1/ventas/$ventaId/qr-libelula', {});
    return Map<String, dynamic>.from(res);
  }

  Future<bool> qrLibelulaPagado(int ventaId) async {
    final res = await get('/api/v1/ventas/$ventaId/qr-libelula/estado');
    return res['pagado'] == true;
  }

  Future<void> simularPagoQrLibelula(int ventaId) async {
    await post('/api/v1/ventas/$ventaId/qr-libelula/simular-pago', {});
  }

  // Obtener comprobante digital oficial de venta
  Future<Map<String, dynamic>> getComprobanteVenta(int ventaId) async {
    final res = await get('/api/v1/ventas/comprobante/$ventaId');
    return Map<String, dynamic>.from(res);
  }

  // Consultar historial de compras del cliente
  Future<List<dynamic>> getMisCompras() async {
    final res = await get('/api/v1/ventas/mis-compras');
    return res is List ? res : [];
  }

  // --- Asistente de IA para el Cliente (CU-28, CU-29) ---

  // CU-28: Recomendaciones de prendas según historial del cliente
  Future<Map<String, dynamic>> getRecomendaciones() async {
    final res = await post('/api/v1/ia/recomendaciones', {});
    return Map<String, dynamic>.from(res);
  }

  // CU-29: Chat con el asistente virtual. Funciona con o sin sesión iniciada.
  // `historial` son los turnos previos de esta conversación (para que el
  // asistente tenga memoria), como [{'rol': 'user'|'asistente', 'contenido': '...'}].
  Future<String> enviarMensajeChat(String mensaje, {List<Map<String, String>>? historial}) async {
    final res = await post('/api/v1/ia/chat', {
      'mensaje': mensaje,
      if (historial != null && historial.isNotEmpty) 'historial': historial,
    });
    return Map<String, dynamic>.from(res)['respuesta'] as String;
  }
}
