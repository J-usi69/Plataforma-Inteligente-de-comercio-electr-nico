import 'dart:convert';
import 'package:http/http.dart' as http;
import '../config/env.dart';

class ApiService {
  static final ApiService _instance = ApiService._internal();
  factory ApiService() => _instance;
  ApiService._internal();

  String baseUrl = Env.apiUrl;
  String? token;
  Map<String, dynamic>? currentUser;

  void setToken(String? newToken) {
    token = newToken;
  }

  void setCurrentUser(Map<String, dynamic>? user) {
    currentUser = user;
  }

  bool get isLoggedIn => token != null && currentUser != null;

  Map<String, String> get _headers {
    final map = <String, String>{
      'Content-Type': 'application/json',
      'Accept': 'application/json',
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

  Future<dynamic> get(String path) async {
    final response = await http.get(_uri(path), headers: _headers).timeout(_timeout);
    return _decode(response);
  }

  Future<dynamic> post(String path, Map<String, dynamic> body) async {
    final response = await http
        .post(
          _uri(path),
          headers: _headers,
          body: jsonEncode(body),
        )
        .timeout(_timeout);
    return _decode(response);
  }

  Future<dynamic> put(String path, Map<String, dynamic> body) async {
    final response = await http
        .put(
          _uri(path),
          headers: _headers,
          body: jsonEncode(body),
        )
        .timeout(_timeout);
    return _decode(response);
  }

  Future<dynamic> delete(String path) async {
    final response = await http.delete(_uri(path), headers: _headers).timeout(_timeout);
    return _decode(response);
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
    throw Exception(message);
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
  }

  // CU-01: Perfil
  Future<Map<String, dynamic>> getProfile() async {
    final res = await get('/api/v1/auth/me');
    final map = Map<String, dynamic>.from(res);
    setCurrentUser(map);
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
  }) async {
    final request = http.MultipartRequest('POST', _uri('/api/v1/vestidor-ar/jobs'));
    if (token != null) {
      request.headers['Authorization'] = 'Bearer $token';
    }
    request.fields['prenda_id'] = prendaId.toString();
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

  // CU-15: Crear una reserva
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

  // Crear venta digital desde app móvil
  Future<Map<String, dynamic>> crearVentaDigital({
    required int sucursalId,
    required List<Map<String, dynamic>> detalles,
    String tipoEntrega = 'DOMICILIO',
    String? direccionEnvio,
  }) async {
    final body = {
      'sucursal_id': sucursalId,
      'tipo_entrega': tipoEntrega,
      if (direccionEnvio != null && direccionEnvio.isNotEmpty)
        'direccion_envio': direccionEnvio,
      'detalles': detalles,
    };
    final res = await post('/api/v1/ventas/digital', body);
    return Map<String, dynamic>.from(res);
  }

  // Procesar pago digital (QR Libélula o Tarjeta ya confirmada con Stripe)
  Future<Map<String, dynamic>> pagarVentaDigital({
    required int ventaId,
    required String metodoPago,
    String? pasarela,
    String? stripePaymentIntentId,
  }) async {
    final body = {
      'metodo_pago': metodoPago,
      if (pasarela != null) 'pasarela': pasarela,
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
}
