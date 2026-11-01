import 'package:sqflite_common_ffi/sqflite_ffi.dart';

import 'package:fashionstore/core/offline/almacen_local.dart';
import 'package:fashionstore/core/offline/modelos.dart';

/// Base en memoria: cada test arranca vacío si cierra el almacén al terminar.
AlmacenLocal almacenEnMemoria() {
  sqfliteFfiInit();
  return AlmacenLocal(fabrica: databaseFactoryFfi, ruta: inMemoryDatabasePath);
}

/// Mismo formato que GET /api/v1/sync/paquete (PaqueteOut), con datos inventados.
Map<String, dynamic> paqueteDePrueba({String? generadoEn, int stockPolera = 3, String tienda = 'fashionstore'}) => {
      'generado_en': generadoEn ?? DateTime.now().toUtc().toIso8601String(),
      'vigencia_horas': 12,
      'tienda': tienda,
      'dias_para_cambio': 7,
      'sucursales': [
        {'id': 1, 'nombre': 'Central', 'direccion': 'Av. Siempre Viva 1', 'ciudad': 'Santa Cruz'},
        {'id': 2, 'nombre': 'Norte', 'direccion': 'Calle 2', 'ciudad': null},
      ],
      'categorias': [
        {'id': 10, 'nombre': 'Poleras'},
        {'id': 11, 'nombre': 'Pantalones'},
      ],
      'tallas': [
        {'id': 1, 'nombre': 'S'},
        {'id': 2, 'nombre': 'M'},
      ],
      'colores': [
        {'id': 1, 'nombre': 'Negro', 'hex': '#000000'},
        {'id': 2, 'nombre': 'Blanco', 'hex': null},
      ],
      'prendas': [
        {'id': 100, 'nombre': 'Polera básica', 'descripcion': null, 'categoria_id': 10, 'precio_base': 50.0, 'imagen_url': null},
        {'id': 101, 'nombre': 'Jean recto', 'descripcion': 'Azul', 'categoria_id': 11, 'precio_base': 120.5, 'imagen_url': null},
      ],
      'variantes': [
        {'id': 1000, 'prenda_id': 100, 'talla_id': 1, 'color_id': 1, 'codigo_barras': '7790001', 'imagen_url': null},
        {'id': 1001, 'prenda_id': 100, 'talla_id': 2, 'color_id': 2, 'codigo_barras': '7790002', 'imagen_url': null},
        {'id': 1010, 'prenda_id': 101, 'talla_id': 2, 'color_id': 1, 'codigo_barras': '7790010', 'imagen_url': null},
      ],
      'inventario': [
        {'variante_id': 1000, 'sucursal_id': 1, 'stock_disponible': stockPolera},
        {'variante_id': 1000, 'sucursal_id': 2, 'stock_disponible': 0},
        {'variante_id': 1001, 'sucursal_id': 2, 'stock_disponible': 5},
        {'variante_id': 1010, 'sucursal_id': 1, 'stock_disponible': 2},
      ],
      'clientes': [
        {'id': 50, 'correo': 'ana@example.com'},
      ],
      'ventas': [],
    };

OperacionLocal operacionDePrueba({
  String id = '11111111-2222-4333-8444-555555555555',
  String tipo = 'venta',
  int sucursalId = 1,
  int varianteId = 1000,
  int cantidad = 1,
  int usuarioId = 7,
  String estado = 'registrada',
}) {
  final datos = tipo == 'venta'
      ? {
          'cliente_id': null,
          'detalles': [
            {'variante_id': varianteId, 'cantidad': cantidad, 'precio_unitario': 50.0},
          ],
          'total': 50.0 * cantidad,
          'metodo_pago': 'efectivo',
        }
      : {
          'cliente_id': null,
          'detalles': [
            {'variante_id': varianteId, 'cantidad': cantidad},
          ],
        };
  return OperacionLocal(
    id: id,
    tipo: tipo,
    tienda: 'fashionstore',
    sucursalId: sucursalId,
    registradaEn: '2026-10-31T23:40:00Z',
    dispositivo: 'movil:android',
    datos: datos,
    usuarioId: usuarioId,
    estado: estado,
    resumen: 'prueba',
  );
}
