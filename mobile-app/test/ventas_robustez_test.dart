import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'package:fashionstore/core/services/cart_service.dart';
import 'package:fashionstore/features/ventas/carrito_screen.dart';
import 'package:fashionstore/features/ventas/mis_compras_screen.dart';
import 'package:fashionstore/features/ventas/pago_qr_libelula.dart';

// Lo que pasa cuando el usuario cierra algo a mitad de camino o la red falla: nada de eso debe
// cerrar otra pantalla, dejar la app trabada ni romper el carrito.

const _pngBase64 =
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==';

http.Response _json(Object cuerpo, [int estado = 200]) =>
    http.Response(jsonEncode(cuerpo), estado, headers: {'content-type': 'application/json; charset=utf-8'});

final _compraPagada = {
  'id': 10,
  'estado': 'pagada',
  'tipo_origen': 'movil',
  'total': 89.9,
  'fecha_venta': '2026-09-27T12:00:00Z',
  'sucursal_nombre': 'Sucursal Central',
  'detalles': [],
};

Future<void> _abrirMisCompras(WidgetTester tester) async {
  // Sobre otra pantalla, para notar si un pop() de más la cierra
  await tester.pumpWidget(const MaterialApp(home: Scaffold(body: Text('Inicio'))));
  tester.state<NavigatorState>(find.byType(Navigator)).push(
        MaterialPageRoute<void>(builder: (_) => const MisComprasScreen()),
      );
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('Mis compras: cerrar con "atrás" el cargando del comprobante no cierra la pantalla', (tester) async {
    final comprobante = Completer<http.Response>();

    await http.runWithClient(() async {
      await _abrirMisCompras(tester);
      await tester.tap(find.text('Comprobante'));
      await tester.pump();
      expect(find.byType(CircularProgressIndicator), findsOneWidget);

      await tester.binding.handlePopRoute(); // botón "atrás" de Android
      await tester.pumpAndSettle();
      comprobante.complete(_json({'detail': 'Error'}, 500));
      await tester.pumpAndSettle();

      expect(find.byType(MisComprasScreen), findsOneWidget);
      expect(find.byType(CircularProgressIndicator), findsNothing);
    }, () => MockClient((req) async {
      if (req.url.path == '/api/v1/ventas/mis-compras') return _json([_compraPagada]);
      return comprobante.future;
    }));
  });

  testWidgets('Mis compras: si el comprobante falla, se cierra el cargando y se avisa', (tester) async {
    await http.runWithClient(() async {
      await _abrirMisCompras(tester);
      await tester.tap(find.text('Comprobante'));
      await tester.pumpAndSettle();

      expect(find.byType(CircularProgressIndicator), findsNothing);
      expect(find.textContaining('Error al cargar comprobante'), findsOneWidget);
      expect(find.byType(MisComprasScreen), findsOneWidget);
    }, () => MockClient((req) async {
      if (req.url.path == '/api/v1/ventas/mis-compras') return _json([_compraPagada]);
      return _json({'detail': 'Error'}, 500);
    }));
  });

  testWidgets('QR: si se cierra mientras consulta el estado y llega "pagado", no avisa a nadie', (tester) async {
    final estado = Completer<http.Response>();
    var avisos = 0;
    var mostrar = true;
    late StateSetter cambiar;

    await http.runWithClient(() async {
      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: StatefulBuilder(builder: (context, setState) {
            cambiar = setState;
            return mostrar
                ? PagoQrLibelula(ventaId: 11, onPagado: () async => avisos++)
                : const Text('Cerrado');
          }),
        ),
      ));
      await tester.pump(); // genera el QR
      await tester.pump(const Duration(seconds: 5)); // primera consulta: queda esperando respuesta

      cambiar(() => mostrar = false); // el usuario cierra la hoja
      await tester.pump();
      estado.complete(_json({'pagado': true, 'estado_venta': 'pagada', 'modo_prueba': true}));
      await tester.pump();

      expect(avisos, 0);
    }, () => MockClient((req) async {
      if (req.url.path.endsWith('/estado')) return estado.future;
      return _json({
        'pago_id': 1,
        'transaccion_id': 'PRUEBA-abc',
        'qr_url': 'data:image/png;base64,$_pngBase64',
        'url_pasarela': null,
        'monto': 89.9,
        'modo_prueba': true,
      });
    }));
  });

  testWidgets('Carrito: si las sucursales no cargan, ofrece reintentar y no deja pagar', (tester) async {
    tester.view.physicalSize = const Size(800, 2400);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.reset);
    CartService().addItem(CartItem(
      varianteId: 3, prendaId: 1, nombre: 'Polera Basica', talla: 'S', color: 'Blanco', precio: 89.9,
    ));
    addTearDown(CartService().clear);
    var caido = true;
    final botonPagar = find.widgetWithText(ElevatedButton, 'CONTINUAR AL PAGO DIGITAL (Bs. 89.90)');

    await http.runWithClient(() async {
      await tester.pumpWidget(const MaterialApp(home: CarritoScreen()));
      await tester.pumpAndSettle();

      expect(tester.takeException(), isNull);
      expect(find.text('No se pudieron cargar las sucursales.'), findsOneWidget);
      expect(tester.widget<ElevatedButton>(botonPagar).onPressed, isNull);

      caido = false;
      await tester.tap(find.text('Reintentar'));
      await tester.pumpAndSettle();

      expect(find.text('Sucursal Norte (Santa Cruz)'), findsOneWidget);
      expect(tester.widget<ElevatedButton>(botonPagar).onPressed, isNotNull);
    }, () => MockClient((req) async {
      if (caido) return _json({'detail': 'Servicio no disponible'}, 503);
      return _json([
        {'id': 4, 'nombre': 'Sucursal Norte', 'ciudad_nombre': 'Santa Cruz'},
      ]);
    }));
  });
}
