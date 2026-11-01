// Operación sin conexión en la app: mismos contratos que backend/app/schemas/sincronizacion.py y
// que la PWA (frontend-web/src/app/core/offline/modelos.ts), guardados en SQLite.
import 'dart:convert';

/// registrada: solo en este teléfono. enviada: salió hacia el servidor y todavía no hay respuesta
/// definitiva (se reintenta). confirmada / rechazada: respuesta final. conflicto: el servidor la
/// recibió y espera la decisión del Administrador de Empresa (CU-14).
const estadosLocales = ['registrada', 'enviada', 'confirmada', 'rechazada', 'conflicto'];

/// Lo que se sabe del paquete guardado, sin las tablas.
class InfoPaquete {
  final String generadoEn;
  final int vigenciaHoras;
  final String tienda;
  final int diasParaCambio;
  final int usuarioId;

  const InfoPaquete({
    required this.generadoEn,
    required this.vigenciaHoras,
    required this.tienda,
    required this.diasParaCambio,
    required this.usuarioId,
  });
}

class OperacionLocal {
  final String id; // UUID generado en el teléfono: el mismo en todos los reintentos
  final int orden; // se envían en el orden en que se registraron
  final String tipo; // venta | reserva
  final String tienda;
  final int sucursalId;
  final String registradaEn;
  final String dispositivo;
  final Map<String, dynamic> datos;
  final int usuarioId; // solo la sesión de quien la registró la envía
  final String estado;
  final int intentos;
  final String? ultimoIntento;
  final Map<String, dynamic>? resultado; // respuesta del servidor: codigo, mensaje, referencia, procesada_en
  final String resumen;

  const OperacionLocal({
    required this.id,
    this.orden = 0,
    required this.tipo,
    required this.tienda,
    required this.sucursalId,
    required this.registradaEn,
    required this.dispositivo,
    required this.datos,
    required this.usuarioId,
    this.estado = 'registrada',
    this.intentos = 0,
    this.ultimoIntento,
    this.resultado,
    required this.resumen,
  });

  OperacionLocal copiarCon({
    int? orden,
    String? estado,
    int? intentos,
    String? ultimoIntento,
    Map<String, dynamic>? resultado,
  }) {
    return OperacionLocal(
      id: id,
      orden: orden ?? this.orden,
      tipo: tipo,
      tienda: tienda,
      sucursalId: sucursalId,
      registradaEn: registradaEn,
      dispositivo: dispositivo,
      datos: datos,
      usuarioId: usuarioId,
      estado: estado ?? this.estado,
      intentos: intentos ?? this.intentos,
      ultimoIntento: ultimoIntento ?? this.ultimoIntento,
      resultado: resultado ?? this.resultado,
      resumen: resumen,
    );
  }

  /// Fila de la tabla "operacion" (sin "orden": lo asigna SQLite).
  Map<String, Object?> aFila() => {
        'id': id,
        'tipo': tipo,
        'tienda': tienda,
        'sucursal_id': sucursalId,
        'registrada_en': registradaEn,
        'dispositivo': dispositivo,
        'datos': jsonEncode(datos),
        'usuario_id': usuarioId,
        'estado': estado,
        'intentos': intentos,
        'ultimo_intento': ultimoIntento,
        'resultado': resultado == null ? null : jsonEncode(resultado),
        'resumen': resumen,
      };

  factory OperacionLocal.desdeFila(Map<String, Object?> fila) {
    final resultado = fila['resultado'] as String?;
    return OperacionLocal(
      id: fila['id'] as String,
      orden: fila['orden'] as int,
      tipo: fila['tipo'] as String,
      tienda: fila['tienda'] as String,
      sucursalId: fila['sucursal_id'] as int,
      registradaEn: fila['registrada_en'] as String,
      dispositivo: fila['dispositivo'] as String,
      datos: Map<String, dynamic>.from(jsonDecode(fila['datos'] as String) as Map),
      usuarioId: fila['usuario_id'] as int,
      estado: fila['estado'] as String,
      intentos: fila['intentos'] as int,
      ultimoIntento: fila['ultimo_intento'] as String?,
      resultado: resultado == null ? null : Map<String, dynamic>.from(jsonDecode(resultado) as Map),
      resumen: fila['resumen'] as String,
    );
  }
}
