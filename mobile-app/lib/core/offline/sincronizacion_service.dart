// Sincronización de la operación sin conexión (CU-08 y CU-13): descarga el paquete para trabajar
// sin Internet, registra reservas y ventas en el teléfono y las envía al backend cuando hay
// conexión (al volver la red, al abrir la app, cada minuto y a pedido). Una operación nunca se
// borra por haberse enviado: queda con el estado que respondió el servidor. Igual que la PWA.
import 'dart:async';
import 'dart:math';

import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';

import '../services/api_service.dart';
import 'almacen_local.dart';
import 'modelos.dart';
import 'reglas.dart';

const _porLote = 50;
const _cadaMinuto = Duration(minutes: 1);
const _probarConexionCada = Duration(seconds: 15);
const _renovarPaquete = Duration(minutes: 10); // con conexión, se renueva si tiene más de 10 minutos

String mensajeDeError(Object error, String porDefecto) {
  if (error is TimeoutException) return 'El servidor no respondió a tiempo.';
  if (sinConexion(error)) return 'No hay conexión con el servidor.';
  if (error is ApiException) {
    if (error.status == 401) return 'Tu sesión venció: iniciá sesión de nuevo para enviar las operaciones.';
    return error.mensaje;
  }
  return porDefecto;
}

class SincronizacionService extends ChangeNotifier with WidgetsBindingObserver {
  static final SincronizacionService _instance = SincronizacionService._internal();
  factory SincronizacionService() => _instance;
  SincronizacionService._internal();

  /// Reemplazable en los tests por una base en memoria.
  AlmacenLocal almacen = AlmacenLocal();

  bool enLinea = true;
  bool sincronizando = false;
  bool descargando = false;
  String? ultimoError;
  InfoPaquete? info;
  List<OperacionLocal> _todas = [];

  /// Resultado de cada sincronización que tuvo respuestas del servidor (CU-13, paso 5).
  final _avisos = StreamController<String>.broadcast();
  Stream<String> get avisos => _avisos.stream;

  bool _iniciado = false;
  Future<void>? _enCurso;

  ApiService get _api => ApiService();
  int? get _usuarioId => _api.currentUser?['id'] as int?;

  bool get tieneDatos => info != null;
  bool get disponible => _api.isLoggedIn && _api.tiene('operacion_offline');

  /// Las de la sesión actual: las de otro usuario del teléfono esperan a que él inicie sesión.
  List<OperacionLocal> get operaciones =>
      _todas.where((op) => op.usuarioId == _usuarioId && op.tienda == _api.tienda).toList();
  int get pendientes => operaciones.where((op) => pendienteDeEnvio(op.estado)).length;
  int get enConflicto => operaciones.where((op) => op.estado == 'conflicto').length;
  bool get desactualizado => info != null && paqueteDesactualizado(info!.generadoEn, info!.vigenciaHoras);

  /// Una vez, al arrancar la app (con la sesión guardada ya restaurada).
  Future<void> iniciar() async {
    if (_iniciado) return;
    _iniciado = true;
    WidgetsBinding.instance.addObserver(this);
    final conectividad = Connectivity();
    conectividad.onConnectivityChanged.listen((redes) {
      if (redes.every((r) => r == ConnectivityResult.none)) {
        _ponerEnLinea(false);
      } else {
        unawaited(probarConexion());
      }
    });
    Timer.periodic(_cadaMinuto, (_) {
      if (enLinea && (pendientes > 0 || enConflicto > 0)) unawaited(sincronizar());
    });
    // Con wifi sin Internet o con el servidor caído la red dice "conectado": si los pedidos
    // fallan se pasa a sin conexión y se prueba de a ratos si el servidor volvió
    Timer.periodic(_probarConexionCada, (_) {
      if (!enLinea) unawaited(probarConexion());
    });
    if ((await conectividad.checkConnectivity()).every((r) => r == ConnectivityResult.none)) {
      _ponerEnLinea(false);
    }
    await alCambiarUsuario();
    if (enLinea) unawaited(probarConexion());
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) unawaited(probarConexion());
  }

  /// Un pedido no llegó al servidor: se trabaja con lo guardado hasta que vuelva la conexión.
  void marcarSinConexion() => _ponerEnLinea(false);

  /// El servidor respondió: si estábamos sin conexión, se envía lo pendiente.
  void marcarEnLinea() {
    if (enLinea) return;
    _ponerEnLinea(true);
    unawaited(alRecuperarConexion());
  }

  void _ponerEnLinea(bool valor) {
    if (enLinea == valor) return;
    enLinea = valor;
    notifyListeners();
  }

  /// ¿Responde el servidor? (al arrancar, al volver a la app, al cambiar la red y, sin conexión,
  /// cada 15 s). De paso actualiza la marca y las funciones del plan de la empresa.
  Future<void> probarConexion() async {
    try {
      await _api.cargarTienda(timeout: const Duration(seconds: 5));
    } catch (e) {
      if (sinConexion(e)) {
        _ponerEnLinea(false);
        return;
      } // cualquier otra respuesta del servidor ya es conexión
    }
    marcarEnLinea();
  }

  /// Al iniciar o cerrar sesión, al cambiar de empresa y al arrancar con una sesión guardada.
  Future<void> alCambiarUsuario() async {
    if (!_api.isLoggedIn) {
      // El paquete tiene datos de clientes: no queda en el teléfono. Las operaciones sí
      await almacen.borrarPaquete();
      await cargarLocal();
      return;
    }
    await cargarLocal();
    if (enLinea) await alRecuperarConexion();
  }

  Future<void> alRecuperarConexion() async {
    if (!disponible) return;
    await sincronizar();
    final actual = info;
    final viejo = actual == null || DateTime.now().difference(DateTime.parse(actual.generadoEn)) > _renovarPaquete;
    if (viejo) await descargarPaquete();
  }

  /// Lee lo guardado. Un paquete de otra sesión (otras sucursales autorizadas) no se usa.
  Future<void> cargarLocal() async {
    final guardado = await almacen.leerInfo();
    _todas = await almacen.operaciones();
    info = guardado != null && guardado.usuarioId == _usuarioId && guardado.tienda == _api.tienda ? guardado : null;
    notifyListeners();
  }

  /// CU-08: baja catálogo, existencias y sucursales autorizadas, y los guarda en SQLite.
  Future<bool> descargarPaquete() async {
    final usuarioId = _usuarioId;
    if (usuarioId == null || !_api.tiene('operacion_offline')) return false;
    descargando = true;
    notifyListeners();
    try {
      final paquete = Map<String, dynamic>.from(
        await _api.directo('GET', '/api/v1/sync/paquete', timeout: const Duration(seconds: 30)) as Map,
      );
      // Lo que el servidor todavía no conoce se vuelve a descontar del stock recién bajado
      final sinEnviar = (await almacen.operaciones())
          .where((op) => op.usuarioId == usuarioId && op.tienda == paquete['tienda'] && pendienteDeEnvio(op.estado))
          .toList();
      await almacen.guardarPaquete(paquete, usuarioId, sinEnviar);
      await cargarLocal();
      ultimoError = null;
      return true;
    } catch (e) {
      _registrarFalla(e, 'No se pudieron descargar los datos para trabajar sin conexión.');
      return false;
    } finally {
      descargando = false;
      notifyListeners();
    }
  }

  /// Guarda la operación en el teléfono (con su efecto en el stock local) y, si hay conexión, la
  /// envía enseguida. Con o sin red, el camino es el mismo: la cola.
  Future<OperacionLocal> registrar(String tipo, int sucursalId, Map<String, dynamic> datos) async {
    final actual = info;
    final usuarioId = _usuarioId;
    if (actual == null || usuarioId == null) {
      throw const SinConexion('Primero conectate una vez para descargar los datos de trabajo sin conexión.');
    }
    final op = await almacen.registrar(OperacionLocal(
      id: nuevoId(),
      tipo: tipo,
      tienda: actual.tienda,
      sucursalId: sucursalId,
      registradaEn: DateTime.now().toUtc().toIso8601String(),
      dispositivo: 'movil:${defaultTargetPlatform.name}',
      datos: datos,
      usuarioId: usuarioId,
      resumen: resumenDe(tipo, datos),
    ));
    await cargarLocal();
    if (enLinea) unawaited(sincronizar());
    return op;
  }

  /// Una sola sincronización a la vez: si ya hay una en curso, se espera esa.
  Future<void> sincronizar() => _enCurso ??= _enviarPendientes().whenComplete(() => _enCurso = null);

  Future<void> _enviarPendientes() async {
    final usuarioId = _usuarioId;
    if (usuarioId == null || !_api.tiene('operacion_offline')) return;
    sincronizando = true;
    notifyListeners();
    final cuenta = <String, int>{};
    try {
      final pendientes = (await almacen.operaciones())
          .where((op) => op.usuarioId == usuarioId && op.tienda == _api.tienda && pendienteDeEnvio(op.estado))
          .toList();
      for (var i = 0; i < pendientes.length; i += _porLote) {
        final ahora = DateTime.now().toUtc().toIso8601String();
        final lote = pendientes
            .sublist(i, min(i + _porLote, pendientes.length))
            .map((op) => op.copiarCon(estado: 'enviada', intentos: op.intentos + 1, ultimoIntento: ahora))
            .toList();
        await almacen.actualizar(lote); // si la respuesta no llega, quedan "enviadas" y se reenvían igual
        await cargarLocal();
        final respuesta = await _api.directo(
          'POST',
          '/api/v1/sync/operaciones',
          body: {'operaciones': lote.map(sobreParaEnviar).toList()},
          timeout: const Duration(seconds: 60),
        );
        final porId = {
          for (final r in respuesta['resultados'] as List) r['id'] as String: Map<String, dynamic>.from(r as Map),
        };
        final respondidas = lote.map((op) {
          final r = porId[op.id];
          if (r == null) return op;
          final estado = estadoTrasResultado(r['estado'] as String);
          cuenta[estado] = (cuenta[estado] ?? 0) + 1;
          return op.copiarCon(estado: estado, resultado: _resultadoDe(r));
        }).toList();
        await almacen.actualizar(respondidas);
        await cargarLocal();
      }
      await _actualizarConflictos(cuenta);
      ultimoError = null;
    } catch (e) {
      // Sin red, servidor caído, suscripción vencida (402) o sesión vencida (401): todo queda
      // guardado como estaba y se reintenta más tarde
      _registrarFalla(e, 'No se pudieron enviar las operaciones: se reintentará.');
    } finally {
      sincronizando = false;
      notifyListeners();
    }
    final aviso = _textoDelResultado(cuenta);
    if (aviso != null) _avisos.add(aviso);
    if ((cuenta['confirmada'] ?? 0) > 0) await descargarPaquete(); // stock al día con lo confirmado
  }

  /// Los conflictos los resuelve el Administrador de Empresa: se pregunta si ya decidió.
  Future<void> _actualizarConflictos(Map<String, int> cuenta) async {
    final enConflicto = operaciones.where((op) => op.estado == 'conflicto').take(100).toList();
    if (enConflicto.isEmpty) return;
    final ids = enConflicto.map((op) => 'ids=${op.id}').join('&');
    final estado = await _api.directo('GET', '/api/v1/sync/estado?$ids', timeout: const Duration(seconds: 30));
    final porId = {
      for (final r in estado['resultados'] as List) r['id'] as String: Map<String, dynamic>.from(r as Map),
    };
    final resueltas = <OperacionLocal>[];
    for (final op in enConflicto) {
      final r = porId[op.id];
      if (r == null || r['estado'] == 'conflicto') continue;
      final nuevo = estadoTrasResultado(r['estado'] as String);
      cuenta[nuevo] = (cuenta[nuevo] ?? 0) + 1;
      resueltas.add(op.copiarCon(estado: nuevo, resultado: _resultadoDe(r)));
    }
    if (resueltas.isNotEmpty) {
      await almacen.actualizar(resueltas);
      await cargarLocal();
    }
  }

  Map<String, dynamic> _resultadoDe(Map<String, dynamic> r) => {
        'codigo': r['codigo'],
        'mensaje': r['mensaje'],
        'referencia_tipo': r['referencia_tipo'],
        'referencia_id': r['referencia_id'],
        'procesada_en': r['procesada_en'],
      };

  String? _textoDelResultado(Map<String, int> cuenta) {
    String parte(String estado, String singular, String plural) {
      final n = cuenta[estado] ?? 0;
      return n == 0 ? '' : '$n ${n == 1 ? singular : plural}';
    }

    final partes = [
      parte('confirmada', 'confirmada', 'confirmadas'),
      parte('rechazada', 'rechazada', 'rechazadas'),
      parte('conflicto', 'en conflicto', 'en conflicto'),
    ].where((p) => p.isNotEmpty).toList();
    return partes.isEmpty ? null : 'Operaciones sincronizadas: ${partes.join(', ')}.';
  }

  void _registrarFalla(Object error, String porDefecto) {
    if (sinConexion(error)) _ponerEnLinea(false);
    ultimoError = mensajeDeError(error, porDefecto);
  }
}
