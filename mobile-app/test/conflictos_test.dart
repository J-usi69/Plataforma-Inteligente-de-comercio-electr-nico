import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'package:fashionstore/core/offline/almacen_local.dart';
import 'package:fashionstore/core/offline/modelos.dart';
import 'package:fashionstore/core/offline/sincronizacion_service.dart';
import 'package:fashionstore/core/services/api_service.dart';
import 'package:fashionstore/features/offline/conflictos_screen.dart';

// CU-14 en la app: el encargado o el administrador ven los conflictos que llegaron al servidor y
// mandan la decisión (aceptar con ajuste, reasignar —solo el administrador— o anular) con su nota.

const _id = '11111111-1111-4111-8111-111111111111';

http.Response _json(Object cuerpo, [int estado = 200]) =>
    http.Response(jsonEncode(cuerpo), estado, headers: {'content-type': 'application/json; charset=utf-8'});

Map<String, dynamic> _conflicto() => {
      'id': _id,
      'tipo': 'venta',
      'estado': 'conflicto',
      'codigo': 'sin_stock',
      'mensaje': 'La venta se hizo en la tienda pero el inventario del sistema no alcanza: Polera básica (M / Negro)',
      'duplicada': false,
      'sucursal_id': 1,
      'sucursal_nombre': 'Centro',
      'usuario_correo': 'cajero@moda.com',
      'dispositivo': 'SM-A245M',
      'registrada_en': '2026-11-07T11:50:00Z',
      'recibida_en': '2026-11-07T12:00:00Z',
      'intentos': 1,
      'datos': {
        'id': _id,
        'tipo': 'venta',
        'tienda': 'fashionstore',
        'sucursal_id': 1,
        'registrada_en': '2026-11-07T11:50:00Z',
        'datos': {
          'detalles': [
            {'variante_id': 101, 'cantidad': 3, 'precio_unitario': 100.0},
          ],
          'total': 300.0,
        },
      },
    };

/// Lo guardado en el teléfono para trabajar sin conexión, sin abrir SQLite.
class _AlmacenDePrueba extends AlmacenLocal {
  @override
  Future<Map<int, Map<String, dynamic>>> describirVariantes(Iterable<int> ids) async => {
        101: {'prenda_nombre': 'Polera básica', 'talla_nombre': 'M', 'color_nombre': 'Negro'},
      };

  @override
  Future<List<OperacionLocal>> operaciones() async => const [];
}

/// El backend: un conflicto por resolver hasta que llega la decisión.
class _Servidor {
  final decisiones = <Map<String, dynamic>>[];
  List<Map<String, dynamic>> conflictos = [_conflicto()];
  http.Response? respuestaAlResolver;

  MockClient cliente() => MockClient((req) async {
        final ruta = req.url.path;
        if (ruta == '/api/v1/sync/operaciones') {
          return _json(req.url.queryParameters['estado'] == 'conflicto' ? conflictos : <Object>[]);
        }
        if (ruta == '/api/v1/sucursales') {
          return _json([
            {'id': 1, 'nombre': 'Centro'},
            {'id': 2, 'nombre': 'Norte'},
          ]);
        }
        if (ruta == '/api/v1/sync/operaciones/$_id/resolver') {
          decisiones.add(Map<String, dynamic>.from(jsonDecode(req.body) as Map));
          if (respuestaAlResolver != null) return respuestaAlResolver!;
          conflictos = [];
          return _json({..._conflicto(), 'estado': 'confirmada'});
        }
        return _json(<Object>[]); // la sincronización en segundo plano no importa acá
      });
}

/// Todo el test corre con el servidor simulado (también los pedidos que salen de los toques).
Future<void> _conServidor(WidgetTester tester, _Servidor servidor, List<String> roles, Future<void> Function() pasos) async {
  tester.view.physicalSize = const Size(1080, 2600);
  tester.view.devicePixelRatio = 2.5;
  addTearDown(tester.view.reset);
  SincronizacionService().almacen = _AlmacenDePrueba();
  ApiService()
    ..setToken('token-de-prueba')
    ..setCurrentUser({'id': 1, 'correo': 'jefe@moda.com', 'roles': roles});
  addTearDown(() => ApiService()
    ..setToken(null)
    ..setCurrentUser(null));
  await http.runWithClient(() async {
    await tester.pumpWidget(const MaterialApp(home: ConflictosScreen()));
    await tester.pumpAndSettle();
    await pasos();
  }, servidor.cliente);
}

Future<void> _tocar(WidgetTester tester, Finder f) async {
  await tester.ensureVisible(f);
  await tester.pumpAndSettle();
  await tester.tap(f);
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('el administrador reasigna el conflicto a otra sucursal con una nota', (tester) async {
    final servidor = _Servidor();
    await _conServidor(tester, servidor, ['Administrador'], () async {
      expect(find.text('Por resolver (1)'), findsOneWidget);
      expect(find.textContaining('no alcanza'), findsOneWidget);
      expect(find.text('Bs. 300.00'), findsOneWidget);

      await _tocar(tester, find.text('Revisar y decidir'));
      expect(find.text('Polera básica (M / Negro) × 3'), findsOneWidget);
      await _tocar(tester, find.text('Reasignar a otra sucursal'));
      // La sucursal donde se registró no se ofrece como destino
      expect(find.widgetWithText(ChoiceChip, 'Centro'), findsNothing);
      final sinElegir = tester.widget<FilledButton>(find.widgetWithText(FilledButton, 'Elegí la sucursal'));
      expect(sinElegir.onPressed, isNull);

      await _tocar(tester, find.widgetWithText(ChoiceChip, 'Norte'));
      await tester.enterText(find.byType(TextField), 'La prenda salió del Norte');
      await _tocar(tester, find.widgetWithText(FilledButton, 'Reasignar a Norte'));

      expect(servidor.decisiones.single, {
        'accion': 'reasignar',
        'nota': 'La prenda salió del Norte',
        'nueva_sucursal_id': 2,
      });
      expect(find.text('No hay conflictos por resolver'), findsOneWidget);
    });
  });

  testWidgets('el encargado no puede reasignar: acepta con ajuste', (tester) async {
    final servidor = _Servidor();
    await _conServidor(tester, servidor, ['Encargado'], () async {
      await _tocar(tester, find.text('Revisar y decidir'));
      expect(find.text('Reasignar a otra sucursal'), findsNothing);
      expect(find.text('Anular'), findsOneWidget);

      await _tocar(tester, find.widgetWithText(FilledButton, 'Aceptar con ajuste'));
      expect(servidor.decisiones.single, {'accion': 'aceptar'});
    });
  });

  testWidgets('si el servidor no acepta la decisión, se muestra el motivo y no se cierra', (tester) async {
    final servidor = _Servidor()
      ..respuestaAlResolver = _json({'detail': 'La operación ya está confirmada: solo se resuelven las que están en conflicto'}, 409);
    await _conServidor(tester, servidor, ['Administrador'], () async {
      await _tocar(tester, find.text('Revisar y decidir'));
      await _tocar(tester, find.text('Anular'));
      await _tocar(tester, find.widgetWithText(FilledButton, 'Anular la operación'));

      expect(servidor.decisiones.single['accion'], 'anular');
      expect(find.textContaining('ya está confirmada'), findsOneWidget);
      expect(find.byType(HojaDecision), findsOneWidget); // sigue abierta para elegir otra cosa
    });
  });

  test('las líneas de un cambio distinguen lo que devuelve y lo que entrega', () {
    final cambio = {
      'tipo': 'cambio',
      'datos': {
        'datos': {
          'devuelve': [
            {'variante_id': 1, 'cantidad': 1},
          ],
          'entrega': [
            {'variante_id': 2, 'cantidad': 1, 'precio_unitario': 120},
          ],
          'diferencia': 20,
        },
      },
    };
    expect(lineasDe(cambio), [
      (parte: 'Devuelve', varianteId: 1, cantidad: 1),
      (parte: 'Entrega', varianteId: 2, cantidad: 1),
    ]);
    expect(montoDe(cambio), 'Diferencia Bs. 20.00');
    expect(decisionDe({'estado': 'confirmada', 'sucursal_id': 2, 'datos': {'sucursal_id': 1}}).$1, 'Reasignada');
    expect(decisionDe({'estado': 'rechazada'}).$1, 'Anulada');
  });
}
