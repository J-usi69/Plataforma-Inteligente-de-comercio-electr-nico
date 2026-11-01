// Persistencia local de la app en SQLite (RF13): el paquete para trabajar sin conexión en tablas
// normalizadas, como lo manda el backend, y la cola de operaciones. Sobrevive al cierre y
// reinicio de la app; el paquete se borra al cerrar sesión (tiene datos de clientes), las
// operaciones no.
import 'package:path/path.dart' as p;
import 'package:sqflite/sqflite.dart';

import 'modelos.dart';
import 'reglas.dart';

const _esquema = [
  'CREATE TABLE meta (clave TEXT PRIMARY KEY, valor TEXT NOT NULL)',
  'CREATE TABLE sucursal (id INTEGER PRIMARY KEY, nombre TEXT NOT NULL, direccion TEXT NOT NULL, ciudad TEXT)',
  'CREATE TABLE categoria (id INTEGER PRIMARY KEY, nombre TEXT NOT NULL)',
  'CREATE TABLE talla (id INTEGER PRIMARY KEY, nombre TEXT NOT NULL)',
  'CREATE TABLE color (id INTEGER PRIMARY KEY, nombre TEXT NOT NULL, hex TEXT)',
  'CREATE TABLE prenda (id INTEGER PRIMARY KEY, nombre TEXT NOT NULL, descripcion TEXT, '
      'categoria_id INTEGER NOT NULL, precio_base REAL NOT NULL, imagen_url TEXT)',
  'CREATE TABLE variante (id INTEGER PRIMARY KEY, prenda_id INTEGER NOT NULL, talla_id INTEGER NOT NULL, '
      'color_id INTEGER NOT NULL, codigo_barras TEXT NOT NULL, imagen_url TEXT)',
  'CREATE INDEX variante_prenda ON variante (prenda_id)',
  'CREATE TABLE inventario (variante_id INTEGER NOT NULL, sucursal_id INTEGER NOT NULL, '
      'stock_disponible INTEGER NOT NULL, PRIMARY KEY (variante_id, sucursal_id))',
  'CREATE TABLE cliente (id INTEGER PRIMARY KEY, correo TEXT NOT NULL)',
  'CREATE TABLE operacion (orden INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT NOT NULL UNIQUE, '
      'tipo TEXT NOT NULL, tienda TEXT NOT NULL, sucursal_id INTEGER NOT NULL, registrada_en TEXT NOT NULL, '
      'dispositivo TEXT NOT NULL, datos TEXT NOT NULL, usuario_id INTEGER NOT NULL, estado TEXT NOT NULL, '
      'intentos INTEGER NOT NULL DEFAULT 0, ultimo_intento TEXT, resultado TEXT, resumen TEXT NOT NULL)',
];

const _tablasPaquete = ['meta', 'sucursal', 'categoria', 'talla', 'color', 'prenda', 'variante', 'inventario', 'cliente'];

class AlmacenLocal {
  /// [fabrica] y [ruta] permiten abrir la base en memoria en los tests.
  AlmacenLocal({this.fabrica, this.ruta});

  final DatabaseFactory? fabrica;
  final String? ruta;
  Future<Database>? _abierta;

  Future<Database> get _db => _abierta ??= _abrir();

  Future<Database> _abrir() async {
    final fabrica = this.fabrica ?? databaseFactory;
    final ruta = this.ruta ?? p.join(await fabrica.getDatabasesPath(), 'fashionstore_offline.db');
    return fabrica.openDatabase(
      ruta,
      options: OpenDatabaseOptions(
        version: 1,
        onCreate: (db, _) async {
          for (final sentencia in _esquema) {
            await db.execute(sentencia);
          }
        },
      ),
    );
  }

  Future<void> cerrar() async {
    final abierta = _abierta;
    _abierta = null;
    if (abierta != null) await (await abierta).close();
  }

  // --- Paquete ---------------------------------------------------------------------

  /// Reemplaza el paquete en una sola transacción: si algo falla queda el anterior completo
  /// (CU-08). Lo que el servidor todavía no recibió se vuelve a descontar del stock recién bajado.
  Future<void> guardarPaquete(Map<String, dynamic> paquete, int usuarioId, List<OperacionLocal> sinEnviar) async {
    final db = await _db;
    await db.transaction((txn) async {
      for (final tabla in _tablasPaquete) {
        await txn.delete(tabla);
      }
      final lote = txn.batch();
      List<Map<String, dynamic>> filas(String clave) =>
          (paquete[clave] as List? ?? const []).map((f) => Map<String, dynamic>.from(f as Map)).toList();
      for (final s in filas('sucursales')) {
        lote.insert('sucursal', {'id': s['id'], 'nombre': s['nombre'], 'direccion': s['direccion'], 'ciudad': s['ciudad']});
      }
      for (final tabla in const {'categorias': 'categoria', 'tallas': 'talla'}.entries) {
        for (final f in filas(tabla.key)) {
          lote.insert(tabla.value, {'id': f['id'], 'nombre': f['nombre']});
        }
      }
      for (final c in filas('colores')) {
        lote.insert('color', {'id': c['id'], 'nombre': c['nombre'], 'hex': c['hex']});
      }
      for (final pr in filas('prendas')) {
        lote.insert('prenda', {
          'id': pr['id'],
          'nombre': pr['nombre'],
          'descripcion': pr['descripcion'],
          'categoria_id': pr['categoria_id'],
          'precio_base': pr['precio_base'],
          'imagen_url': pr['imagen_url'],
        });
      }
      for (final v in filas('variantes')) {
        lote.insert('variante', {
          'id': v['id'],
          'prenda_id': v['prenda_id'],
          'talla_id': v['talla_id'],
          'color_id': v['color_id'],
          'codigo_barras': v['codigo_barras'],
          'imagen_url': v['imagen_url'],
        });
      }
      for (final i in filas('inventario')) {
        lote.insert('inventario', {
          'variante_id': i['variante_id'],
          'sucursal_id': i['sucursal_id'],
          'stock_disponible': i['stock_disponible'],
        });
      }
      for (final c in filas('clientes')) {
        lote.insert('cliente', {'id': c['id'], 'correo': c['correo']});
      }
      final meta = {
        'generado_en': paquete['generado_en'],
        'vigencia_horas': paquete['vigencia_horas'],
        'tienda': paquete['tienda'],
        'dias_para_cambio': paquete['dias_para_cambio'],
        'usuario_id': usuarioId,
      };
      meta.forEach((clave, valor) => lote.insert('meta', {'clave': clave, 'valor': '$valor'}));
      await lote.commit(noResult: true);
      for (final op in sinEnviar) {
        await _aplicarEnStock(txn, op);
      }
    });
  }

  Future<InfoPaquete?> leerInfo() async {
    final filas = await (await _db).query('meta');
    final meta = {for (final f in filas) f['clave'] as String: f['valor'] as String};
    if (!meta.containsKey('generado_en')) return null;
    return InfoPaquete(
      generadoEn: meta['generado_en']!,
      vigenciaHoras: int.parse(meta['vigencia_horas']!),
      tienda: meta['tienda']!,
      diasParaCambio: int.parse(meta['dias_para_cambio']!),
      usuarioId: int.parse(meta['usuario_id']!),
    );
  }

  Future<void> borrarPaquete() async {
    final db = await _db;
    await db.transaction((txn) async {
      for (final tabla in _tablasPaquete) {
        await txn.delete(tabla);
      }
    });
  }

  // --- Catálogo (mismas formas que responde el backend) -----------------------------

  Future<List<Map<String, dynamic>>> prendas({int? categoriaId, int? tallaId, int? colorId, String? buscar}) async {
    final donde = <String>[];
    final args = <Object?>[];
    if (categoriaId != null) {
      donde.add('p.categoria_id = ?');
      args.add(categoriaId);
    }
    if (buscar != null && buscar.trim().isNotEmpty) {
      donde.add('LOWER(p.nombre) LIKE ?');
      args.add('%${buscar.trim().toLowerCase()}%');
    }
    if (tallaId != null || colorId != null) {
      donde.add('EXISTS (SELECT 1 FROM variante v WHERE v.prenda_id = p.id'
          '${tallaId != null ? ' AND v.talla_id = ?' : ''}${colorId != null ? ' AND v.color_id = ?' : ''})');
      if (tallaId != null) args.add(tallaId);
      if (colorId != null) args.add(colorId);
    }
    final filas = await (await _db).rawQuery(
      'SELECT p.*, c.nombre AS categoria_nombre FROM prenda p LEFT JOIN categoria c ON c.id = p.categoria_id'
      '${donde.isEmpty ? '' : ' WHERE ${donde.join(' AND ')}'} ORDER BY p.nombre',
      args,
    );
    return filas
        .map((f) => {...f, 'estado': true, 'coleccion_id': null, 'proveedor_id': null, 'modelo_3d_url': null})
        .toList();
  }

  Future<Map<String, dynamic>?> prenda(int id) async {
    final filas = await prendas();
    for (final f in filas) {
      if (f['id'] == id) return f;
    }
    return null;
  }

  Future<List<Map<String, dynamic>>> categorias() async =>
      (await (await _db).query('categoria', orderBy: 'nombre')).map((c) => {...c, 'descripcion': null, 'estado': true}).toList();

  Future<List<Map<String, dynamic>>> tallas() async => (await _db).query('talla', orderBy: 'id');

  Future<List<Map<String, dynamic>>> colores() async => (await _db).query('color', orderBy: 'nombre');

  Future<List<Map<String, dynamic>>> clientes() async => (await _db).query('cliente', orderBy: 'correo');

  Future<List<Map<String, dynamic>>> sucursales() async {
    final filas = await (await _db).query('sucursal', orderBy: 'nombre');
    return filas
        .map((s) => {
              'id': s['id'],
              'nombre': s['nombre'],
              'direccion': s['direccion'],
              'ciudad_id': 0,
              'ciudad_nombre': s['ciudad'],
              'estado': true,
            })
        .toList();
  }

  Future<List<Map<String, dynamic>>> variantes(int prendaId) async {
    final filas = await (await _db).rawQuery(
      'SELECT v.*, t.nombre AS talla_nombre, c.nombre AS color_nombre FROM variante v '
      'LEFT JOIN talla t ON t.id = v.talla_id LEFT JOIN color c ON c.id = v.color_id '
      'WHERE v.prenda_id = ? ORDER BY t.id, c.nombre',
      [prendaId],
    );
    return filas.map((v) => {...v, 'estado': true}).toList();
  }

  /// En qué sucursales guardadas hay stock de una variante (como /inventario/disponibilidad).
  Future<List<Map<String, dynamic>>> disponibilidad(int varianteId) async {
    final filas = await (await _db).rawQuery(
      'SELECT s.id AS sucursal_id, s.nombre AS sucursal_nombre, s.ciudad AS ciudad_nombre, s.direccion, '
      'i.stock_disponible FROM inventario i JOIN sucursal s ON s.id = i.sucursal_id '
      'WHERE i.variante_id = ? AND i.stock_disponible > 0 ORDER BY s.nombre',
      [varianteId],
    );
    return filas.map((f) => {...f, 'ciudad_id': 0, 'ciudad_nombre': f['ciudad_nombre'] ?? ''}).toList();
  }

  Future<int> stock(int varianteId, int sucursalId) async {
    final filas = await (await _db).query(
      'inventario',
      columns: ['stock_disponible'],
      where: 'variante_id = ? AND sucursal_id = ?',
      whereArgs: [varianteId, sucursalId],
    );
    return filas.isEmpty ? 0 : filas.first['stock_disponible'] as int;
  }

  /// Para la caja: variantes por nombre de prenda o código de barras, con su stock en la sucursal.
  Future<List<Map<String, dynamic>>> buscarVariantes(String texto, int sucursalId) async {
    final t = texto.trim().toLowerCase();
    return (await _db).rawQuery(
      'SELECT v.id AS variante_id, v.codigo_barras, p.id AS prenda_id, p.nombre AS prenda_nombre, p.precio_base, '
      't.nombre AS talla_nombre, c.nombre AS color_nombre, COALESCE(i.stock_disponible, 0) AS stock '
      'FROM variante v JOIN prenda p ON p.id = v.prenda_id LEFT JOIN talla t ON t.id = v.talla_id '
      'LEFT JOIN color c ON c.id = v.color_id '
      'LEFT JOIN inventario i ON i.variante_id = v.id AND i.sucursal_id = ? '
      'WHERE LOWER(p.nombre) LIKE ? OR v.codigo_barras = ? ORDER BY p.nombre, t.id, c.nombre LIMIT 40',
      [sucursalId, '%$t%', texto.trim()],
    );
  }

  /// Nombre, talla, color y precio de las variantes de unas líneas (para mostrar una operación).
  Future<Map<int, Map<String, dynamic>>> describirVariantes(Iterable<int> ids) async {
    final lista = ids.toSet().toList();
    if (lista.isEmpty) return {};
    final filas = await (await _db).rawQuery(
      'SELECT v.id, v.codigo_barras, p.id AS prenda_id, p.nombre AS prenda_nombre, p.precio_base, '
      't.nombre AS talla_nombre, c.nombre AS color_nombre FROM variante v JOIN prenda p ON p.id = v.prenda_id '
      'LEFT JOIN talla t ON t.id = v.talla_id LEFT JOIN color c ON c.id = v.color_id '
      'WHERE v.id IN (${List.filled(lista.length, '?').join(', ')})',
      lista,
    );
    return {for (final f in filas) f['id'] as int: f};
  }

  // --- Operaciones -------------------------------------------------------------------

  /// Guarda la operación y descuenta su efecto del stock local, todo junto.
  Future<OperacionLocal> registrar(OperacionLocal op) async {
    final db = await _db;
    return db.transaction((txn) async {
      final orden = await txn.insert('operacion', op.aFila());
      await _aplicarEnStock(txn, op);
      return op.copiarCon(orden: orden);
    });
  }

  Future<List<OperacionLocal>> operaciones() async {
    final filas = await (await _db).query('operacion', orderBy: 'orden');
    return filas.map(OperacionLocal.desdeFila).toList();
  }

  Future<void> actualizar(List<OperacionLocal> ops) async {
    final lote = (await _db).batch();
    for (final op in ops) {
      final fila = op.aFila();
      lote.update(
        'operacion',
        {
          'estado': fila['estado'],
          'intentos': fila['intentos'],
          'ultimo_intento': fila['ultimo_intento'],
          'resultado': fila['resultado'],
        },
        where: 'id = ?',
        whereArgs: [op.id],
      );
    }
    await lote.commit(noResult: true);
  }

  Future<void> _aplicarEnStock(DatabaseExecutor db, OperacionLocal op) async {
    for (final e in efectoEnStock(op.tipo, op.datos).entries) {
      await db.rawUpdate(
        'UPDATE inventario SET stock_disponible = MAX(0, stock_disponible + ?) WHERE variante_id = ? AND sucursal_id = ?',
        [e.value, e.key, op.sucursalId],
      );
    }
  }
}
