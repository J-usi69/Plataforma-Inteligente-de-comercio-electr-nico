// Reglas de negocio de la operación sin conexión, sin Flutter ni SQLite: qué le hace cada
// operación al stock local, montos y cómo queda una operación según la respuesta del servidor.
// Las mismas que la PWA (reglas.ts) y que valida el backend: acá sirven para avisar antes; la
// decisión final es siempre del servidor.
import 'dart:math';

import 'modelos.dart';

double redondear(num monto) => (monto * 100).roundToDouble() / 100;

/// Total de líneas con precio ({variante_id, cantidad, precio_unitario}).
double totalDe(List<Map<String, dynamic>> lineas) => redondear(
      lineas.fold<double>(0, (suma, l) => suma + redondear((l['precio_unitario'] as num) * (l['cantidad'] as num))),
    );

/// Cuánto saca (negativo) cada operación del stock de su sucursal, por variante. Así lo que se ve
/// sin conexión ya descuenta lo vendido y reservado en este teléfono.
Map<int, int> efectoEnStock(String tipo, Map<String, dynamic> datos) {
  final efecto = <int, int>{};
  void sumar(List<dynamic> lineas, int signo) {
    for (final l in lineas) {
      final varianteId = l['variante_id'] as int;
      efecto[varianteId] = (efecto[varianteId] ?? 0) + signo * (l['cantidad'] as int);
    }
  }

  if (tipo == 'cambio') {
    sumar(datos['devuelve'] as List, 1);
    sumar(datos['entrega'] as List, -1);
  } else {
    sumar(datos['detalles'] as List, -1);
  }
  return efecto;
}

/// Sigue pendiente de envío: todavía no hay una respuesta definitiva del servidor.
bool pendienteDeEnvio(String estado) => estado == 'registrada' || estado == 'enviada';

/// "error" no es una respuesta definitiva (falla momentánea del servidor): se vuelve a enviar.
String estadoTrasResultado(String estadoServidor) => estadoServidor == 'error' ? 'enviada' : estadoServidor;

bool paqueteDesactualizado(String generadoEn, int vigenciaHoras, {DateTime? ahora}) {
  final generado = DateTime.parse(generadoEn);
  return (ahora ?? DateTime.now()).difference(generado) > Duration(hours: vigenciaHoras);
}

/// Lo que viaja al servidor (sin los datos que solo usa el teléfono).
Map<String, dynamic> sobreParaEnviar(OperacionLocal op) => {
      'id': op.id,
      'tipo': op.tipo,
      'tienda': op.tienda,
      'sucursal_id': op.sucursalId,
      'registrada_en': op.registradaEn,
      'dispositivo': op.dispositivo,
      'datos': op.datos,
    };

String formatoBs(num monto) => 'Bs. ${monto.toStringAsFixed(2)}';

String _prendas(List<dynamic> lineas) {
  final unidades = lineas.fold<int>(0, (suma, l) => suma + (l['cantidad'] as int));
  return '$unidades ${unidades == 1 ? 'prenda' : 'prendas'}';
}

String resumenDe(String tipo, Map<String, dynamic> datos) {
  if (tipo == 'venta') {
    return 'Venta de contado · ${_prendas(datos['detalles'] as List)} · ${formatoBs(datos['total'] as num)}';
  }
  return 'Reserva · ${_prendas(datos['detalles'] as List)}';
}

final _azar = Random.secure();

/// UUID v4 para identificar la operación.
String nuevoId() {
  final b = List<int>.generate(16, (_) => _azar.nextInt(256));
  b[6] = (b[6] & 0x0f) | 0x40;
  b[8] = (b[8] & 0x3f) | 0x80;
  final h = b.map((x) => x.toRadixString(16).padLeft(2, '0')).join();
  return '${h.substring(0, 8)}-${h.substring(8, 12)}-${h.substring(12, 16)}-${h.substring(16, 20)}-${h.substring(20)}';
}

/// "31/10 19:40" en la hora del teléfono.
String fechaCorta(String iso) {
  final f = DateTime.parse(iso).toLocal();
  String dos(int n) => n.toString().padLeft(2, '0');
  return '${dos(f.day)}/${dos(f.month)} ${dos(f.hour)}:${dos(f.minute)}';
}

/// Código provisional para el comprobante de una operación todavía no confirmada.
String codigoProvisional(String id) => 'PEND-${id.substring(0, 8).toUpperCase()}';
