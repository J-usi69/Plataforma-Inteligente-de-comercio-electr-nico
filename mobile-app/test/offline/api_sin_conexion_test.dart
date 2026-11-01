import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'package:fashionstore/core/offline/sincronizacion_service.dart';
import 'package:fashionstore/core/services/api_service.dart';

import 'datos_de_prueba.dart';

// Operación sin conexión transparente: las mismas llamadas de las pantallas, con la red cortada,
// responden con lo guardado en SQLite y las escrituras quedan en la cola hasta que vuelve.

http.Response _json(Object cuerpo, [int estado = 200]) =>
    http.Response(jsonEncode(cuerpo), estado, headers: {'content-type': 'application/json; charset=utf-8'});

MockClient _sinRed([void Function()? alPedir]) => MockClient((_) async {
      alPedir?.call();
      throw http.ClientException('Connection refused');
    });

/// El servidor de vuelta: responde cada operación enviada con el estado que se le indique.
MockClient _servidor({
  required List<Map<String, dynamic>> enviadas,
  String Function(Map<String, dynamic> op)? estadoDe,
  int stockPolera = 3,
}) =>
    MockClient((req) async {
      switch (req.url.path) {
        case '/api/v1/tienda':
          return _json({'slug': 'fashionstore', 'nombre': 'FashionStore'});
        case '/api/v1/sync/paquete':
          return _json(paqueteDePrueba(stockPolera: stockPolera));
        case '/api/v1/sync/operaciones':
          final ops = ((jsonDecode(req.body) as Map)['operaciones'] as List).cast<Map<String, dynamic>>();
          enviadas.addAll(ops);
          return _json({
            'recibido_en': '2026-11-01T12:00:00Z',
            'resultados': [
              for (final (i, op) in ops.indexed)
                {
                  'id': op['id'],
                  'tipo': op['tipo'],
                  'estado': estadoDe?.call(op) ?? 'confirmada',
                  'codigo': 'PRUEBA',
                  'mensaje': 'Respuesta de prueba',
                  'referencia_tipo': op['tipo'],
                  'referencia_id': 900 + i,
                  'duplicada': false,
                  'procesada_en': '2026-11-01T12:00:01Z',
                },
            ],
          });
      }
      return _json({'detail': 'Ruta no esperada en el test: ${req.url.path}'}, 404);
    });

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  final api = ApiService();
  final sync = SincronizacionService();

  setUp(() async {
    sync.almacen = almacenEnMemoria();
    sync.enLinea = true;
    api
      ..tienda = 'fashionstore'
      ..tiendaInfo = null
      ..setToken('token-de-prueba')
      ..setCurrentUser({'id': 7, 'correo': 'cliente@example.com', 'roles': ['Cliente']});
    await sync.almacen.guardarPaquete(paqueteDePrueba(), 7, const []);
    await sync.cargarLocal();
  });

  tearDown(() async {
    api
      ..setToken(null)
      ..setCurrentUser(null);
    // Espera la sincronización que haya quedado en curso; sin sesión no arranca otra (ni sale a la red real)
    await sync.sincronizar();
    await sync.almacen.cerrar();
  });

  test('sin red el catálogo responde con lo guardado y deja de esperar a la red', () async {
    var pedidos = 0;
    await http.runWithClient(() async {
      final prendas = await api.getPrendas(categoriaId: 10);
      expect(prendas.single['nombre'], 'Polera básica');
      expect(sync.enLinea, isFalse);

      expect(await api.getCategorias(), hasLength(2));
      expect(await api.getVariantes(100), hasLength(2));
      expect((await api.getDisponibilidad(1000)).single['sucursal_id'], 1);
    }, () => _sinRed(() => pedidos++));

    // Solo el primero intentó la red: los demás ya sabían que no había conexión
    expect(pedidos, 1);
  });

  test('un 502 del proxy cuenta como sin conexión', () async {
    await http.runWithClient(() async {
      expect(await api.getPrendas(), hasLength(2));
      expect(sync.enLinea, isFalse);
    }, () => MockClient((_) async => _json({'detail': 'Bad Gateway'}, 502)));
  });

  test('un error de verdad del servidor no se tapa con lo guardado', () async {
    await http.runWithClient(() async {
      await expectLater(api.getPrendas(), throwsA(isA<ApiException>().having((e) => e.status, 'status', 500)));
      expect(sync.enLinea, isTrue);
    }, () => MockClient((_) async => _json({'detail': 'Error interno'}, 500)));
  });

  test('sin paquete descargado avisa que hace falta conectarse una vez', () async {
    await sync.almacen.borrarPaquete();
    await sync.cargarLocal();
    await http.runWithClient(() async {
      await expectLater(
        api.getPrendas(),
        throwsA(isA<SinConexion>().having((e) => e.mensaje, 'mensaje', contains('conectate una vez'))),
      );
    }, () => _sinRed());
  });

  test('lo que necesita Internet falla con un mensaje claro', () async {
    await http.runWithClient(() async {
      await expectLater(
        api.getMisCompras(),
        throwsA(isA<SinConexion>().having((e) => e.mensaje, 'mensaje', contains('necesita Internet'))),
      );
    }, () => _sinRed());
  });

  test('una reserva sin conexión queda en la cola, descuenta stock y se confirma al volver', () async {
    late Map<String, dynamic> reserva;
    await http.runWithClient(() async {
      reserva = await api.crearReserva(sucursalId: 1, varianteId: 1000, cantidad: 2);
      expect(reserva['sincronizacion'], 'registrada');
      expect(reserva['estado'], 'pendiente');
      expect(reserva['total_estimado'], 100.0);
      expect(reserva['detalles'].single['prenda_nombre'], 'Polera básica');
      expect(sync.pendientes, 1);
      expect(await sync.almacen.stock(1000, 1), 1);

      // Aparece en "Mis reservas" aunque no haya red
      expect((await api.getMisReservas()).single['operacion_id'], reserva['operacion_id']);

      // Con lo guardado ya no alcanza el stock para otras 2
      await expectLater(
        api.crearReserva(sucursalId: 1, varianteId: 1000, cantidad: 2),
        throwsA(isA<ApiException>().having((e) => e.mensaje, 'mensaje', contains('Stock insuficiente'))),
      );
    }, () => _sinRed());

    final enviadas = <Map<String, dynamic>>[];
    await http.runWithClient(() async {
      await sync.probarConexion();
      await sync.sincronizar();
    }, () => _servidor(enviadas: enviadas, stockPolera: 1));

    expect(sync.enLinea, isTrue);
    final enviada = enviadas.single;
    expect(enviada['id'], reserva['operacion_id']);
    expect(enviada['tienda'], 'fashionstore');
    expect(enviada['sucursal_id'], 1);
    expect(enviada['datos']['cliente_id'], isNull); // un cliente reserva para sí
    expect(enviada['datos']['detalles'], [
      {'variante_id': 1000, 'cantidad': 2},
    ]);

    final op = sync.operaciones.single;
    expect(op.estado, 'confirmada');
    expect(op.resultado?['referencia_id'], 900);
    expect(sync.pendientes, 0);
    // Tras confirmar se volvió a bajar el paquete: el stock es el del servidor
    expect(await sync.almacen.stock(1000, 1), 1);
  });

  test('"error" se reintenta, "rechazada" queda final y se avisa el resultado', () async {
    sync.marcarSinConexion();
    final venta = await sync.registrar('venta', 1, {
      'cliente_id': null,
      'detalles': [
        {'variante_id': 1010, 'cantidad': 1, 'precio_unitario': 120.5},
      ],
      'total': 120.5,
      'metodo_pago': 'efectivo',
      'monto_recibido': 150,
    });
    final reserva = await sync.registrar('reserva', 1, {
      'cliente_id': null,
      'detalles': [
        {'variante_id': 1000, 'cantidad': 1},
      ],
    });
    expect(sync.pendientes, 2);

    final aviso = sync.avisos.first;
    final enviadas = <Map<String, dynamic>>[];
    await http.runWithClient(() async {
      sync.enLinea = true;
      await sync.sincronizar();
    }, () => _servidor(enviadas: enviadas, estadoDe: (op) => op['tipo'] == 'venta' ? 'error' : 'rechazada'));

    // Se enviaron en el orden en que se registraron
    expect(enviadas.map((op) => op['id']), [venta.id, reserva.id]);
    final porId = {for (final op in sync.operaciones) op.id: op};
    expect(porId[venta.id]!.estado, 'enviada');
    expect(porId[venta.id]!.intentos, 1);
    expect(porId[reserva.id]!.estado, 'rechazada');
    expect(porId[reserva.id]!.resultado?['mensaje'], 'Respuesta de prueba');
    expect(sync.pendientes, 1);
    expect(await aviso, 'Operaciones sincronizadas: 1 rechazada.');
  });

  test('si el servidor no responde, la operación queda guardada para reintentar', () async {
    sync.marcarSinConexion();
    await sync.registrar('reserva', 1, {
      'cliente_id': null,
      'detalles': [
        {'variante_id': 1000, 'cantidad': 1},
      ],
    });
    await http.runWithClient(() async {
      sync.enLinea = true;
      await sync.sincronizar();
    }, () => _sinRed());

    expect(sync.enLinea, isFalse);
    expect(sync.operaciones.single.estado, 'enviada');
    expect(sync.pendientes, 1);
    expect(sync.ultimoError, 'No hay conexión con el servidor.');
  });

  test('con conexión, "Mis reservas" suma las que todavía no llegaron al servidor', () async {
    sync.marcarSinConexion();
    await sync.registrar('reserva', 2, {
      'cliente_id': null,
      'detalles': [
        {'variante_id': 1001, 'cantidad': 1},
      ],
    });
    sync.enLinea = true;
    await http.runWithClient(() async {
      final reservas = await api.getMisReservas();
      expect(reservas.map((r) => r['sincronizacion']), ['registrada', null]);
      expect(reservas.first['sucursal_nombre'], 'Norte');
      expect(reservas.last['id'], 55);
    }, () => MockClient((req) async {
      if (req.url.path == '/api/v1/reservas') {
        return _json([
          {'id': 55, 'estado': 'confirmada', 'sucursal_nombre': 'Central', 'detalles': []},
        ]);
      }
      return _json({'detail': 'Error'}, 500);
    }));
  });

  test('las operaciones de otro usuario del teléfono no se envían con esta sesión', () async {
    sync.marcarSinConexion();
    await sync.registrar('reserva', 1, {
      'cliente_id': null,
      'detalles': [
        {'variante_id': 1000, 'cantidad': 1},
      ],
    });
    api.setCurrentUser({'id': 8, 'correo': 'otro@example.com', 'roles': ['Cliente']});
    await sync.cargarLocal();
    expect(sync.operaciones, isEmpty);
    expect(sync.tieneDatos, isFalse); // el paquete era del otro usuario

    final enviadas = <Map<String, dynamic>>[];
    await http.runWithClient(() async {
      sync.enLinea = true;
      await sync.sincronizar();
    }, () => _servidor(enviadas: enviadas));
    expect(enviadas, isEmpty);
  });
}
