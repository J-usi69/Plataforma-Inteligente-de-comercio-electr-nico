import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'package:fashionstore/features/ventas/mis_compras_screen.dart';

// PNG de 1x1: el QR de prueba que manda el backend es un data URI como este
const _pngBase64 =
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==';

Map<String, dynamic> _compra(int id, String estado, String tipoOrigen) => {
      'id': id,
      'estado': estado,
      'tipo_origen': tipoOrigen,
      'total': 89.9,
      'fecha_venta': '2026-09-27T12:00:00Z',
      'sucursal_nombre': 'Sucursal Central',
      'detalles': [
        {'cantidad': 1, 'prenda_nombre': 'Polera Basica', 'talla_nombre': 'S', 'color_nombre': 'Blanco', 'subtotal': 89.9},
      ],
    };

// Responde como el backend (estados y campos tal cual los manda la API)
class _BackendFalso {
  final compras = [
    _compra(10, 'pagada', 'movil'),
    _compra(11, 'pendiente', 'movil'),
    _compra(12, 'pendiente', 'presencial'),
    _compra(13, 'anulada', 'web'),
  ];
  final pedidos = <String>[];

  Future<http.Response> responder(http.Request req) async {
    final ruta = '${req.method} ${req.url.path}';
    pedidos.add(ruta);
    Object? cuerpo;
    switch (ruta) {
      case 'GET /api/v1/ventas/mis-compras':
        cuerpo = compras;
      case 'POST /api/v1/ventas/11/qr-libelula':
        cuerpo = {
          'pago_id': 1,
          'transaccion_id': 'PRUEBA-abc',
          'qr_url': 'data:image/png;base64,$_pngBase64',
          'url_pasarela': null,
          'monto': 89.9,
          'modo_prueba': true,
        };
      case 'GET /api/v1/ventas/11/qr-libelula/estado':
        cuerpo = {'pagado': compras[1]['estado'] == 'pagada', 'estado_venta': compras[1]['estado'], 'modo_prueba': true};
      case 'POST /api/v1/ventas/11/qr-libelula/simular-pago':
        compras[1]['estado'] = 'pagada';
        cuerpo = compras[1];
      case 'GET /api/v1/ventas/comprobante/11':
        cuerpo = {
          'numero_comprobante': 'FS-2026-000011',
          'venta_id': 11,
          'fecha_emision': '2026-09-27T12:05:00Z',
          'tipo_origen': 'movil',
          'sucursal_nombre': 'Sucursal Central',
          'sucursal_direccion': 'Av. San Martín',
          'cliente_nombre': 'cliente@fashionstore.com',
          'metodo_pago': 'QR',
          'transaccion_id': 'PRUEBA-abc',
          'estado_venta': 'pagada',
          'subtotal': 89.9,
          'total': 89.9,
          'items': [
            {'descripcion': 'Polera Basica', 'talla': 'S', 'color': 'Blanco', 'cantidad': 1, 'precio_unitario': 89.9, 'subtotal': 89.9},
          ],
        };
      default:
        return http.Response('{"detail": "no esperado: $ruta"}', 404);
    }
    return http.Response(jsonEncode(cuerpo), 200, headers: {'content-type': 'application/json; charset=utf-8'});
  }
}

void main() {
  testWidgets('Mis compras: estados del backend, pago con QR de una pendiente y su comprobante', (tester) async {
    final backend = _BackendFalso();
    // Pantalla alta para que la lista construya las cuatro compras sin tener que desplazarla
    tester.view.physicalSize = const Size(800, 2400);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.reset);

    await http.runWithClient(() async {
      await tester.pumpWidget(const MaterialApp(home: MisComprasScreen()));
      await tester.pumpAndSettle();

      // El backend manda "pagada" (antes la pantalla esperaba "PAGADO" y ninguna figuraba pagada)
      expect(find.text('PAGADA'), findsOneWidget);
      expect(find.text('PENDIENTE'), findsNWidgets(2));
      expect(find.text('ANULADA'), findsOneWidget);
      expect(find.text('MOVIL'), findsNWidgets(2));
      expect(find.text('PRESENCIAL'), findsOneWidget);
      expect(find.text('Fecha: -'), findsNothing);
      expect(find.textContaining('Fecha: 27/09/2026'), findsNWidgets(4));
      // Comprobante solo en la pagada; "Pagar con QR" solo en la pendiente en línea (la de caja no)
      expect(find.text('Comprobante'), findsOneWidget);
      expect(find.text('Pagar con QR'), findsOneWidget);

      // La hoja del QR tiene un indicador de "Esperando la confirmación" que no se detiene: no
      // hay pumpAndSettle posible mientras está abierta
      await tester.tap(find.text('Pagar con QR'));
      await tester.pump();
      await tester.pump(const Duration(seconds: 1));
      expect(find.text('Pagar Orden #11'), findsOneWidget);
      expect(find.text('Simular pago (modo de prueba)'), findsOneWidget);
      expect(backend.pedidos, contains('POST /api/v1/ventas/11/qr-libelula'));

      // La hoja consulta sola si ya se pagó
      await tester.pump(const Duration(seconds: 5));
      expect(backend.pedidos, contains('GET /api/v1/ventas/11/qr-libelula/estado'));

      await tester.ensureVisible(find.text('Simular pago (modo de prueba)'));
      await tester.tap(find.text('Simular pago (modo de prueba)'));
      await tester.pumpAndSettle();

      // Pagada: se cierra la hoja, se muestra el comprobante y la lista se recarga
      expect(find.text('Pagar Orden #11'), findsNothing);
      expect(find.text('COMPROBANTE OFICIAL'), findsOneWidget);
      expect(find.text('FS-2026-000011'), findsOneWidget);
      final enComprobante = find.descendant(of: find.byType(Dialog), matching: find.text('1x Polera Basica (S/Blanco)'));
      expect(enComprobante, findsOneWidget);
      expect(find.text('Transacción: PRUEBA-abc'), findsOneWidget);
      expect(find.textContaining('null'), findsNothing);

      await tester.tap(find.text('Cerrar'));
      await tester.pumpAndSettle();
      expect(find.text('PAGADA'), findsNWidgets(2));
      expect(find.text('Pagar con QR'), findsNothing);
    }, () => MockClient(backend.responder));
  });
}
