import 'package:flutter_test/flutter_test.dart';

import 'package:fashionstore/core/offline/modelos.dart';
import 'package:fashionstore/core/offline/reglas.dart';

void main() {
  test('totalDe redondea cada línea y el total a centavos', () {
    expect(
      totalDe([
        {'variante_id': 1, 'cantidad': 3, 'precio_unitario': 33.333},
        {'variante_id': 2, 'cantidad': 1, 'precio_unitario': 0.1},
      ]),
      100.1,
    );
  });

  test('una venta o reserva descuenta stock; un cambio devuelve y entrega', () {
    expect(
      efectoEnStock('venta', {
        'detalles': [
          {'variante_id': 1, 'cantidad': 2},
          {'variante_id': 1, 'cantidad': 1},
          {'variante_id': 2, 'cantidad': 4},
        ],
      }),
      {1: -3, 2: -4},
    );
    expect(
      efectoEnStock('cambio', {
        'devuelve': [
          {'variante_id': 1, 'cantidad': 1},
        ],
        'entrega': [
          {'variante_id': 2, 'cantidad': 1},
        ],
      }),
      {1: 1, 2: -1},
    );
  });

  test('"error" del servidor se reintenta; las demás respuestas son finales', () {
    expect(estadoTrasResultado('error'), 'enviada');
    expect(estadoTrasResultado('confirmada'), 'confirmada');
    expect(estadoTrasResultado('rechazada'), 'rechazada');
    expect(estadoTrasResultado('conflicto'), 'conflicto');
    expect(estadosLocales.where(pendienteDeEnvio), ['registrada', 'enviada']);
  });

  test('el paquete queda desactualizado pasada su vigencia', () {
    final ahora = DateTime.utc(2026, 11, 1, 12);
    expect(paqueteDesactualizado('2026-11-01T01:00:00Z', 12, ahora: ahora), isFalse);
    expect(paqueteDesactualizado('2026-10-31T23:59:00Z', 12, ahora: ahora), isTrue);
  });

  test('resumen y código provisional legibles para el cajero', () {
    expect(
      resumenDe('venta', {
        'detalles': [
          {'variante_id': 1, 'cantidad': 2},
        ],
        'total': 100,
      }),
      'Venta de contado · 2 prendas · Bs. 100.00',
    );
    expect(
      resumenDe('reserva', {
        'detalles': [
          {'variante_id': 1, 'cantidad': 1},
        ],
      }),
      'Reserva · 1 prenda',
    );
    expect(codigoProvisional('ab12cd34-0000-4000-8000-000000000000'), 'PEND-AB12CD34');
  });

  test('nuevoId genera UUID v4 distintos', () {
    final ids = List.generate(200, (_) => nuevoId());
    final uuidV4 = RegExp(r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$');
    expect(ids.every(uuidV4.hasMatch), isTrue);
    expect(ids.toSet().length, ids.length);
  });

  test('al servidor viaja solo el sobre de la operación, sin los datos locales', () {
    const op = OperacionLocal(
      id: 'id-1',
      orden: 4,
      tipo: 'reserva',
      tienda: 'moda-andina',
      sucursalId: 3,
      registradaEn: '2026-10-31T23:40:00Z',
      dispositivo: 'movil:android',
      datos: {'detalles': []},
      usuarioId: 7,
      estado: 'enviada',
      intentos: 2,
      resumen: 'Reserva · 0 prendas',
    );
    expect(sobreParaEnviar(op), {
      'id': 'id-1',
      'tipo': 'reserva',
      'tienda': 'moda-andina',
      'sucursal_id': 3,
      'registrada_en': '2026-10-31T23:40:00Z',
      'dispositivo': 'movil:android',
      'datos': {'detalles': []},
    });
  });
}
