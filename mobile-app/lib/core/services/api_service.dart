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

  Future<dynamic> get(String path) async {
    final response = await http.get(_uri(path), headers: _headers);
    return _decode(response);
  }

  Future<dynamic> post(String path, Map<String, dynamic> body) async {
    final response = await http.post(
      _uri(path),
      headers: _headers,
      body: jsonEncode(body),
    );
    return _decode(response);
  }

  Future<dynamic> put(String path, Map<String, dynamic> body) async {
    final response = await http.put(
      _uri(path),
      headers: _headers,
      body: jsonEncode(body),
    );
    return _decode(response);
  }

  Future<dynamic> delete(String path) async {
    final response = await http.delete(_uri(path), headers: _headers);
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

  // CU-08: Catálogo de Prendas
  Future<List<dynamic>> getPrendas({int? categoriaId}) async {
    final path = categoriaId != null
        ? '/api/v1/prendas?categoria_id=$categoriaId'
        : '/api/v1/prendas';
    final res = await get(path);
    return res is List ? res : [];
  }

  // CU-08: Categorías
  Future<List<dynamic>> getCategorias() async {
    final res = await get('/api/v1/prendas/categorias');
    return res is List ? res : [];
  }
}
