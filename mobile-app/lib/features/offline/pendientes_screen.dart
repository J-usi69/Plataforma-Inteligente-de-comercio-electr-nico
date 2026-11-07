import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../core/offline/modelos.dart';
import '../../core/offline/reglas.dart';
import '../../core/offline/sincronizacion_service.dart';
import '../../core/services/api_service.dart';
import '../../core/theme/tema.dart';

const _etiquetas = {
  'registrada': 'Registrada (por enviar)',
  'enviada': 'Enviada (esperando respuesta)',
  'confirmada': 'Confirmada',
  'rechazada': 'Rechazada',
  'conflicto': 'En conflicto',
};

const _colores = {
  'registrada': Color(0xFFB45309),
  'enviada': Color(0xFF2563EB),
  'confirmada': Color(0xFF15803D),
  'rechazada': Color(0xFFDC2626),
  'conflicto': Color(0xFFC2410C),
};

/// CU-12: las reservas y ventas registradas en este teléfono con su estado de sincronización y la
/// respuesta del servidor. CU-13: "Sincronizar ahora" (además de la sincronización automática).
class PendientesScreen extends StatefulWidget {
  const PendientesScreen({super.key});

  @override
  State<PendientesScreen> createState() => _PendientesScreenState();
}

class _PendientesScreenState extends State<PendientesScreen> {
  final _sync = SincronizacionService();
  String? _tipo;
  String? _estado;
  Map<int, String> _sucursales = {};

  @override
  void initState() {
    super.initState();
    _cargarSucursales();
  }

  Future<void> _cargarSucursales() async {
    final sucursales = await _sync.almacen.sucursales();
    if (!mounted) return;
    setState(() => _sucursales = {for (final s in sucursales) s['id'] as int: s['nombre'] as String});
  }

  Future<void> _sincronizarAhora() async {
    final messenger = ScaffoldMessenger.of(context);
    if (!_sync.enLinea) await _sync.probarConexion();
    if (!_sync.enLinea) {
      messenger.showSnackBar(const SnackBar(
        content: Text('Sigue sin conexión: las operaciones se enviarán solas cuando vuelva.'),
      ));
      return;
    }
    await _sync.sincronizar();
    if (_sync.ultimoError != null) {
      messenger.showSnackBar(SnackBar(content: Text(_sync.ultimoError!), backgroundColor: Colors.red.shade700));
    } else if (_sync.pendientes == 0) {
      messenger.showSnackBar(const SnackBar(content: Text('No quedan operaciones por enviar.')));
    }
  }

  Future<void> _actualizarDatos() async {
    final messenger = ScaffoldMessenger.of(context);
    final ok = await _sync.descargarPaquete();
    await _cargarSucursales();
    messenger.showSnackBar(SnackBar(
      content: Text(ok
          ? 'Datos para trabajar sin conexión actualizados.'
          : (_sync.ultimoError ?? 'No se pudieron actualizar los datos.')),
    ));
  }

  String _sucursal(int id) => _sucursales[id] ?? 'Sucursal #$id';

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: _sync,
      builder: (context, _) {
        final todas = _sync.operaciones.reversed.toList(); // las más nuevas arriba
        final visibles = todas.where((op) => (_tipo == null || op.tipo == _tipo) && (_estado == null || op.estado == _estado)).toList();
        return Scaffold(
          appBar: AppBar(
            title: const Text('Operaciones pendientes'),
            actions: [
              IconButton(
                tooltip: 'Actualizar los datos guardados para trabajar sin conexión',
                icon: _sync.descargando
                    ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2))
                    : const Icon(Icons.download_for_offline_outlined),
                onPressed: _sync.descargando || !_sync.enLinea ? null : _actualizarDatos,
              ),
            ],
          ),
          body: Column(
            children: [
              _resumenDatos(),
              _filtros(),
              const Divider(height: 1),
              Expanded(
                child: RefreshIndicator(
                  onRefresh: _sincronizarAhora,
                  child: todas.isEmpty
                      ? _vacio('No hay operaciones registradas en este teléfono.')
                      : visibles.isEmpty
                          ? _vacio('Ninguna operación coincide con el filtro.')
                          : ListView.builder(
                              padding: const EdgeInsets.fromLTRB(12, 8, 12, 12),
                              itemCount: visibles.length,
                              itemBuilder: (context, i) => _tarjeta(visibles[i]),
                            ),
                ),
              ),
              _botonSincronizar(),
            ],
          ),
        );
      },
    );
  }

  Widget _resumenDatos() {
    final info = _sync.info;
    return Container(
      width: double.infinity,
      color: const Color(0xFFF1F5F9),
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
      child: Text(
        info == null
            ? 'Este teléfono todavía no tiene datos guardados para trabajar sin conexión.'
            : 'Datos guardados del ${fechaCorta(info.generadoEn)}'
                '${_sync.desactualizado ? ' · pueden estar desactualizados' : ''}'
                ' · ${_sync.enLinea ? 'con conexión' : 'sin conexión'}',
        style: const TextStyle(fontSize: 12.5, color: Color(0xFF334155)),
      ),
    );
  }

  Widget _filtros() {
    Widget chip(String texto, bool seleccionado, VoidCallback alElegir) => Padding(
          padding: const EdgeInsets.only(right: 8),
          child: ChoiceChip(label: Text(texto), selected: seleccionado, onSelected: (_) => alElegir()),
        );
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Column(
        children: [
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.symmetric(horizontal: 12),
            child: Row(children: [
              chip('Todas', _tipo == null, () => setState(() => _tipo = null)),
              chip('Reservas', _tipo == 'reserva', () => setState(() => _tipo = 'reserva')),
              chip('Ventas', _tipo == 'venta', () => setState(() => _tipo = 'venta')),
            ]),
          ),
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.symmetric(horizontal: 12),
            child: Row(children: [
              chip('Cualquier estado', _estado == null, () => setState(() => _estado = null)),
              for (final estado in estadosLocales)
                chip(_etiquetas[estado]!.split(' (').first, _estado == estado, () => setState(() => _estado = estado)),
            ]),
          ),
        ],
      ),
    );
  }

  Widget _vacio(String texto) => ListView(
        children: [
          const SizedBox(height: 80),
          const Icon(Icons.inbox_outlined, size: 56, color: Colors.black26),
          const SizedBox(height: 12),
          Center(child: Text(texto, textAlign: TextAlign.center)),
        ],
      );

  Widget _tarjeta(OperacionLocal op) {
    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      child: ListTile(
        contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
        leading: Icon(op.tipo == 'venta' ? Icons.point_of_sale : Icons.event_available, color: context.marca),
        title: Text(op.resumen, style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 14)),
        subtitle: Text('${fechaCorta(op.registradaEn)} · ${_sucursal(op.sucursalId)}\n${codigoProvisional(op.id)}'),
        isThreeLine: true,
        trailing: _EtiquetaEstado(op.estado),
        onTap: () => _detalle(op),
      ),
    );
  }

  Widget _botonSincronizar() {
    return SafeArea(
      top: false,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(16, 8, 16, 12),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (_sync.ultimoError != null && _sync.pendientes > 0)
              Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Text(_sync.ultimoError!, style: TextStyle(color: Colors.red.shade700, fontSize: 12.5)),
              ),
            SizedBox(
              width: double.infinity,
              child: FilledButton.icon(
                onPressed: _sync.sincronizando ? null : _sincronizarAhora,
                icon: _sync.sincronizando
                    ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))
                    : const Icon(Icons.sync),
                label: Text(_sync.sincronizando ? 'Enviando…' : 'Sincronizar ahora'),
                style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(48)),
              ),
            ),
          ],
        ),
      ),
    );
  }

  /// CU-12, paso 4: detalle y respuesta del servidor.
  Future<void> _detalle(OperacionLocal op) async {
    final lineas = (op.datos['detalles'] as List).map((l) => Map<String, dynamic>.from(l as Map)).toList();
    final variantes = await _sync.almacen.describirVariantes(lineas.map((l) => l['variante_id'] as int));
    if (!mounted) return;
    final resultado = op.resultado;
    final total = op.tipo == 'venta'
        ? (op.datos['total'] as num).toDouble()
        : totalDe(lineas.map((l) => {...l, 'precio_unitario': variantes[l['variante_id']]?['precio_base'] ?? 0}).toList());
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (context) => SafeArea(
        child: ConstrainedBox(
          constraints: BoxConstraints(maxHeight: MediaQuery.of(context).size.height * 0.8),
          child: ListView(
            shrinkWrap: true,
            padding: const EdgeInsets.fromLTRB(20, 0, 20, 20),
            children: [
              Row(children: [
                Expanded(
                  child: Text(op.tipo == 'venta' ? 'Venta de contado' : 'Reserva',
                      style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
                ),
                _EtiquetaEstado(op.estado),
              ]),
              const SizedBox(height: 12),
              _dato('Identificador', op.id),
              _dato('Registrada', fechaCorta(op.registradaEn)),
              _dato('Sucursal', _sucursal(op.sucursalId)),
              if (op.intentos > 0) _dato('Envíos', '${op.intentos}'),
              const Divider(height: 24),
              for (final l in lineas)
                Padding(
                  padding: const EdgeInsets.only(bottom: 4),
                  child: Text(
                    '${variantes[l['variante_id']]?['prenda_nombre'] ?? 'Variante #${l['variante_id']}'}'
                    ' (${variantes[l['variante_id']]?['talla_nombre'] ?? '-'} / ${variantes[l['variante_id']]?['color_nombre'] ?? '-'})'
                    ' × ${l['cantidad']}',
                  ),
                ),
              const SizedBox(height: 6),
              Text('${op.tipo == 'venta' ? 'Total cobrado en efectivo' : 'Total estimado'}: ${formatoBs(total)}',
                  style: const TextStyle(fontWeight: FontWeight.w700)),
              const Divider(height: 24),
              const Text('Respuesta del servidor', style: TextStyle(fontWeight: FontWeight.bold)),
              const SizedBox(height: 6),
              if (resultado == null)
                Text(op.estado == 'registrada'
                    ? 'Todavía no se envió: se enviará sola cuando haya conexión.'
                    : 'Enviada: esperando la respuesta del servidor (se reintenta sola).')
              else ...[
                if (resultado['mensaje'] != null) Text('${resultado['mensaje']}'),
                if (resultado['referencia_id'] != null)
                  _dato('Registro', '${resultado['referencia_tipo'] ?? op.tipo} #${resultado['referencia_id']}'),
                if (resultado['procesada_en'] != null) _dato('Procesada', fechaCorta('${resultado['procesada_en']}')),
              ],
              if (op.estado == 'rechazada')
                Container(
                  margin: const EdgeInsets.only(top: 12),
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(color: const Color(0xFFFEF2F2), borderRadius: BorderRadius.circular(10)),
                  child: const Text('Operación rechazada definitivamente por reglas del servidor.', style: TextStyle(color: Color(0xFF991B1B))),
                ),
              if (op.estado == 'conflicto')
                Container(
                  margin: const EdgeInsets.only(top: 12),
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: const Color(0xFFFFF7ED),
                    border: Border.all(color: const Color(0xFFFDBA74)),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Row(
                        children: [
                          Icon(Icons.warning_amber_rounded, color: Color(0xFFC2410C), size: 18),
                          SizedBox(width: 6),
                          Text('Conflicto: stock central insuficiente', style: TextStyle(fontWeight: FontWeight.bold, color: Color(0xFFC2410C))),
                        ],
                      ),
                      const SizedBox(height: 6),
                      // Solo el encargado o el administrador deciden (el servidor se lo niega al resto)
                      if (!ApiService().puedeResolverConflictos)
                        const Text(
                          'Un encargado o el administrador decide si se acepta con ajuste de inventario o se anula.',
                          style: TextStyle(fontSize: 12, color: Color(0xFF9A3412)),
                        )
                      else ...[
                        const Text(
                          'Revisá el detalle y decidí qué hacer: aceptar con ajuste de inventario, reasignar o anular.',
                          style: TextStyle(fontSize: 12, color: Color(0xFF9A3412)),
                        ),
                        const SizedBox(height: 10),
                        SizedBox(
                          width: double.infinity,
                          child: FilledButton.icon(
                            // CU-14: la misma decisión que en el panel, con nota para la bitácora
                            onPressed: () {
                              Navigator.of(context).pop();
                              this.context.push('/conflictos', extra: op.id);
                            },
                            icon: const Icon(Icons.gavel),
                            label: const Text('Revisar y decidir'),
                          ),
                        ),
                      ],
                    ],
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _dato(String etiqueta, String valor) => Padding(
        padding: const EdgeInsets.only(bottom: 4),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            SizedBox(width: 104, child: Text(etiqueta, style: const TextStyle(color: Colors.black54))),
            Expanded(child: SelectableText(valor)),
          ],
        ),
      );
}

class _EtiquetaEstado extends StatelessWidget {
  final String estado;
  const _EtiquetaEstado(this.estado);

  @override
  Widget build(BuildContext context) {
    final color = _colores[estado] ?? Colors.grey;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(color: color.withValues(alpha: 0.12), borderRadius: BorderRadius.circular(10)),
      child: Text(
        (_etiquetas[estado] ?? estado).split(' (').first,
        style: TextStyle(color: color, fontSize: 12, fontWeight: FontWeight.w700),
      ),
    );
  }
}
