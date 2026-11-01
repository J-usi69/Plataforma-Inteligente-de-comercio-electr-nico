// API local: sin conexión, responde desde SQLite lo mismo que respondería el backend en las rutas
// que usan el catálogo y las reservas. Las pantallas no cambian: piden a la API como siempre y, si
// no hay red, contesta este servicio. Una reserva entra a la cola de SincronizacionService y viaja
// sola al volver la conexión (CU-09 y CU-10). Igual que la PWA (api-local.ts).
import '../services/api_service.dart';
import 'modelos.dart';
import 'reglas.dart';
import 'sincronizacion_service.dart';

typedef _Responder = Future<dynamic> Function(RegExpMatch coincidencia, Uri uri, Map<String, dynamic>? cuerpo);

const _reservaSinRespuestaFinal = {'registrada', 'enviada', 'conflicto'};

class ApiLocal {
  static final ApiLocal _instance = ApiLocal._internal();
  factory ApiLocal() => _instance;
  ApiLocal._internal();

  SincronizacionService get _sync => SincronizacionService();

  late final List<(String, RegExp, _Responder)> _rutas = [
    ('GET', RegExp(r'^/api/v1/prendas$'), (_, uri, _) {
      int? numero(String clave) => int.tryParse(uri.queryParameters[clave] ?? '');
      return _sync.almacen.prendas(
        categoriaId: numero('categoria_id'),
        tallaId: numero('talla_id'),
        colorId: numero('color_id'),
        buscar: uri.queryParameters['buscar'],
      );
    }),
    ('GET', RegExp(r'^/api/v1/prendas/categorias$'), (_, _, _) => _sync.almacen.categorias()),
    ('GET', RegExp(r'^/api/v1/prendas/(\d+)/variantes$'), (m, _, _) => _sync.almacen.variantes(int.parse(m.group(1)!))),
    ('GET', RegExp(r'^/api/v1/prendas/(\d+)$'), (m, _, _) async {
      return await _sync.almacen.prenda(int.parse(m.group(1)!)) ?? _noEsta('La prenda');
    }),
    ('GET', RegExp(r'^/api/v1/catalogo-maestro/tallas$'), (_, _, _) => _sync.almacen.tallas()),
    ('GET', RegExp(r'^/api/v1/catalogo-maestro/colores$'), (_, _, _) => _sync.almacen.colores()),
    ('GET', RegExp(r'^/api/v1/sucursales$'), (_, _, _) => _sync.almacen.sucursales()),
    // Las sucursales guardadas traen el nombre de la ciudad, no su id: sin conexión no se filtra
    ('GET', RegExp(r'^/api/v1/sucursales/ciudades$'), (_, _, _) async => <dynamic>[]),
    ('GET', RegExp(r'^/api/v1/inventario/disponibilidad/(\d+)$'),
        (m, _, _) => _sync.almacen.disponibilidad(int.parse(m.group(1)!))),
    ('GET', RegExp(r'^/api/v1/reservas$'), (_, _, _) => reservasPendientes()),
    ('POST', RegExp(r'^/api/v1/reservas$'), (_, _, cuerpo) => _reservar(cuerpo ?? const {})),
  ];

  (_Responder, RegExpMatch, Uri)? _ruta(String metodo, String path) {
    final uri = Uri.parse(path);
    for (final (m, patron, responder) in _rutas) {
      if (m != metodo) continue;
      final coincidencia = patron.firstMatch(uri.path);
      if (coincidencia != null) return (responder, coincidencia, uri);
    }
    return null;
  }

  /// La ruta se puede responder sin conexión.
  bool atiende(String metodo, String path) => _ruta(metodo, path) != null;

  bool esMisReservas(String metodo, String path) => metodo == 'GET' && Uri.parse(path).path == '/api/v1/reservas';

  Future<dynamic> responder(String metodo, String path, Map<String, dynamic>? cuerpo) async {
    final (responder, coincidencia, uri) = _ruta(metodo, path)!;
    if (!_sync.tieneDatos) {
      throw const SinConexion(
        'No hay conexión y este teléfono todavía no tiene los datos guardados: conectate una vez para descargarlos.',
      );
    }
    return responder(coincidencia, uri, cuerpo);
  }

  /// "Mis reservas" con conexión: las del servidor más las que todavía no se enviaron.
  Future<dynamic> conPendientes(dynamic respuesta) async {
    if (!_sync.operaciones.any((op) => op.tipo == 'reserva' && _reservaSinRespuestaFinal.contains(op.estado))) {
      return respuesta;
    }
    return [...await reservasPendientes(), ...(respuesta as List? ?? const [])];
  }

  /// Las reservas hechas en este teléfono que el servidor todavía no confirmó.
  Future<List<Map<String, dynamic>>> reservasPendientes() async {
    final ops = _sync.operaciones
        .where((op) => op.tipo == 'reserva' && _reservaSinRespuestaFinal.contains(op.estado))
        .toList()
        .reversed
        .toList();
    if (ops.isEmpty) return [];
    final variantes = await _sync.almacen.describirVariantes(
      ops.expand((op) => (op.datos['detalles'] as List).map((l) => l['variante_id'] as int)),
    );
    final sucursales = {for (final s in await _sync.almacen.sucursales()) s['id'] as int: s['nombre']};
    return ops.map((op) => _reservaDe(op, variantes, sucursales)).toList();
  }

  Map<String, dynamic> _reservaDe(OperacionLocal op, Map<int, Map<String, dynamic>> variantes, Map<int, Object?> sucursales) {
    var indice = 0;
    final detalles = (op.datos['detalles'] as List).map((l) {
      final v = variantes[l['variante_id']];
      final unitario = (v?['precio_base'] as num?)?.toDouble() ?? 0;
      return {
        'id': -(++indice),
        'variante_id': l['variante_id'],
        'cantidad': l['cantidad'],
        'precio_unitario': unitario,
        'subtotal': redondear(unitario * (l['cantidad'] as int)),
        'prenda_id': v?['prenda_id'],
        'prenda_nombre': v?['prenda_nombre'] ?? 'Prenda',
        'talla_nombre': v?['talla_nombre'],
        'color_nombre': v?['color_nombre'],
        'codigo_barras': v?['codigo_barras'],
      };
    }).toList();
    return {
      'id': -op.orden,
      'usuario_id': op.usuarioId,
      'sucursal_id': op.sucursalId,
      'sucursal_nombre': sucursales[op.sucursalId],
      'fecha_reserva': op.registradaEn,
      'horario_atencion': op.datos['horario_atencion'],
      'estado': 'pendiente',
      'total_estimado': redondear(detalles.fold<double>(0, (s, l) => s + (l['subtotal'] as double))),
      'detalles': detalles,
      'sincronizacion': op.estado,
      'operacion_id': op.id,
    };
  }

  // --- Escrituras: entran a la cola ---------------------------------------------------

  Future<Map<String, dynamic>> _reservar(Map<String, dynamic> cuerpo) async {
    final sucursalId = cuerpo['sucursal_id'] as int;
    final sucursales = await _sync.almacen.sucursales();
    if (!sucursales.any((s) => s['id'] == sucursalId)) {
      throw const ApiException(400, 'La sucursal no está entre las guardadas en este teléfono.');
    }
    final lineas = (cuerpo['detalles'] as List).map((l) => Map<String, dynamic>.from(l as Map)).toList();
    for (final l in lineas) {
      final stock = await _sync.almacen.stock(l['variante_id'] as int, sucursalId);
      if (stock < (l['cantidad'] as int)) {
        throw ApiException(
          400,
          'Stock insuficiente en la sucursal elegida según los datos guardados '
          '(disponible: $stock, solicitado: ${l['cantidad']}). Ajustá la cantidad.',
        );
      }
    }
    // Como en el servidor, quien reserva desde el catálogo reserva para sí: el personal necesita
    // indicar el cliente (su propio id), un cliente no
    final usuario = ApiService().currentUser!;
    final datos = <String, dynamic>{
      'cliente_id': ApiService().esPersonal ? usuario['id'] : null,
      'detalles': lineas.map((l) => {'variante_id': l['variante_id'], 'cantidad': l['cantidad']}).toList(),
      'horario_atencion': cuerpo['horario_atencion'],
    };
    final op = await _sync.registrar('reserva', sucursalId, datos);
    final variantes = await _sync.almacen.describirVariantes(lineas.map((l) => l['variante_id'] as int));
    return _reservaDe(op, variantes, {for (final s in sucursales) s['id'] as int: s['nombre']});
  }

  Never _noEsta(String que) => throw ApiException(404, '$que no está entre los datos guardados en este teléfono.');
}
