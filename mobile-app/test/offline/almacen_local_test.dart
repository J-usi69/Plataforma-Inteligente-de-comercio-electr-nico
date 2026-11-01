import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:path/path.dart' as p;
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

import 'package:fashionstore/core/offline/almacen_local.dart';

import 'datos_de_prueba.dart';

void main() {
  late AlmacenLocal almacen;

  setUp(() => almacen = almacenEnMemoria());
  tearDown(() => almacen.cerrar());

  test('sin paquete no hay info ni catálogo', () async {
    expect(await almacen.leerInfo(), isNull);
    expect(await almacen.prendas(), isEmpty);
  });

  test('guarda el paquete y responde el catálogo con la forma del backend', () async {
    await almacen.guardarPaquete(paqueteDePrueba(generadoEn: '2026-10-31T23:00:00Z'), 7, const []);

    final info = (await almacen.leerInfo())!;
    expect(info.generadoEn, '2026-10-31T23:00:00Z');
    expect(info.vigenciaHoras, 12);
    expect(info.tienda, 'fashionstore');
    expect(info.usuarioId, 7);

    final prendas = await almacen.prendas();
    expect(prendas.map((pr) => pr['nombre']), ['Jean recto', 'Polera básica']);
    expect(prendas.last['categoria_nombre'], 'Poleras');
    expect(prendas.last['precio_base'], 50.0);
    expect(prendas.last['estado'], isTrue);

    expect((await almacen.prendas(categoriaId: 11)).single['id'], 101);
    expect((await almacen.prendas(tallaId: 1)).single['id'], 100);
    expect((await almacen.prendas(colorId: 2)).single['id'], 100);
    expect((await almacen.prendas(buscar: 'POLERA')).single['id'], 100);
    expect(await almacen.prenda(999), isNull);

    final variantes = await almacen.variantes(100);
    expect(variantes.map((v) => '${v['talla_nombre']}/${v['color_nombre']}'), ['S/Negro', 'M/Blanco']);

    final sucursales = await almacen.sucursales();
    expect(sucursales.first, containsPair('ciudad_nombre', 'Santa Cruz'));
  });

  test('disponibilidad solo lista sucursales con stock', () async {
    await almacen.guardarPaquete(paqueteDePrueba(), 7, const []);
    final disponibilidad = await almacen.disponibilidad(1000);
    expect(disponibilidad.single['sucursal_id'], 1);
    expect(disponibilidad.single['stock_disponible'], 3);
  });

  test('la caja busca por nombre o por código de barras con el stock de su sucursal', () async {
    await almacen.guardarPaquete(paqueteDePrueba(), 7, const []);
    final porCodigo = await almacen.buscarVariantes('7790010', 1);
    expect(porCodigo.single['prenda_nombre'], 'Jean recto');
    expect(porCodigo.single['stock'], 2);

    final porNombre = await almacen.buscarVariantes('polera', 2);
    expect(porNombre.map((v) => v['stock']), [0, 5]);
  });

  test('registrar una venta la guarda y descuenta el stock local sin bajar de cero', () async {
    await almacen.guardarPaquete(paqueteDePrueba(stockPolera: 3), 7, const []);

    final op = await almacen.registrar(operacionDePrueba(cantidad: 2));
    expect(op.orden, greaterThan(0));
    expect(await almacen.stock(1000, 1), 1);

    await almacen.registrar(operacionDePrueba(id: 'otra', cantidad: 5));
    expect(await almacen.stock(1000, 1), 0);

    final guardadas = await almacen.operaciones();
    expect(guardadas.map((o) => o.id), ['11111111-2222-4333-8444-555555555555', 'otra']);
    expect(guardadas.first.datos['metodo_pago'], 'efectivo');
  });

  test('un paquete nuevo reemplaza al anterior y vuelve a descontar lo no enviado', () async {
    await almacen.guardarPaquete(paqueteDePrueba(stockPolera: 3), 7, const []);
    final pendiente = await almacen.registrar(operacionDePrueba(cantidad: 1));

    // El servidor todavía no conoce la venta: su stock (10) no la incluye
    await almacen.guardarPaquete(paqueteDePrueba(stockPolera: 10), 7, [pendiente]);
    expect(await almacen.stock(1000, 1), 9);
    expect((await almacen.prendas()).length, 2);
    expect(await almacen.operaciones(), hasLength(1));
  });

  test('actualizar guarda el estado y la respuesta del servidor', () async {
    final op = await almacen.registrar(operacionDePrueba());
    await almacen.actualizar([
      op.copiarCon(
        estado: 'confirmada',
        intentos: 1,
        ultimoIntento: '2026-11-01T00:00:00Z',
        resultado: {'codigo': 'OK', 'referencia_tipo': 'venta', 'referencia_id': 321},
      ),
    ]);
    final guardada = (await almacen.operaciones()).single;
    expect(guardada.estado, 'confirmada');
    expect(guardada.intentos, 1);
    expect(guardada.resultado?['referencia_id'], 321);
  });

  test('cerrar sesión borra el paquete pero no las operaciones', () async {
    await almacen.guardarPaquete(paqueteDePrueba(), 7, const []);
    await almacen.registrar(operacionDePrueba());
    await almacen.borrarPaquete();
    expect(await almacen.leerInfo(), isNull);
    expect(await almacen.prendas(), isEmpty);
    expect(await almacen.operaciones(), hasLength(1));
  });

  test('las operaciones sobreviven al cierre y reapertura de la app', () async {
    sqfliteFfiInit();
    final carpeta = await Directory.systemTemp.createTemp('fs_offline_');
    final ruta = p.join(carpeta.path, 'prueba.db');
    try {
      final primera = AlmacenLocal(fabrica: databaseFactoryFfi, ruta: ruta);
      await primera.guardarPaquete(paqueteDePrueba(), 7, const []);
      await primera.registrar(operacionDePrueba(tipo: 'reserva'));
      await primera.cerrar();

      final segunda = AlmacenLocal(fabrica: databaseFactoryFfi, ruta: ruta);
      expect((await segunda.operaciones()).single.tipo, 'reserva');
      expect(await segunda.stock(1000, 1), 2);
      await segunda.cerrar();
    } finally {
      await carpeta.delete(recursive: true);
    }
  });
}
