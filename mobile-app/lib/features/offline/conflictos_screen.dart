import 'dart:async';

import 'package:flutter/material.dart';

import '../../core/offline/reglas.dart';
import '../../core/offline/sincronizacion_service.dart';
import '../../core/services/api_service.dart';
import '../../core/theme/tema.dart';

const _naranja = Color(0xFFC2410C);
const _rojo = Color(0xFFDC2626);
const _verde = Color(0xFF15803D);

/// CU-14: el encargado (de su sucursal) o el administrador (de todas) revisan las operaciones hechas
/// sin conexión que quedaron en conflicto al sincronizar y deciden: aceptar con ajuste de inventario,
/// reasignar a otra sucursal (solo el administrador) o anular. La decisión queda en la bitácora.
class ConflictosScreen extends StatefulWidget {
  /// Operación a abrir apenas cargue la lista (llega desde "Operaciones pendientes").
  final String? abrirId;

  const ConflictosScreen({super.key, this.abrirId});

  @override
  State<ConflictosScreen> createState() => _ConflictosScreenState();
}

class _ConflictosScreenState extends State<ConflictosScreen> {
  final _api = ApiService();
  List<Map<String, dynamic>> _porResolver = [];
  List<Map<String, dynamic>> _resueltas = [];
  bool _cargando = true;
  String? _error;
  bool _verResueltas = false;
  String? _abrirAlCargar;
  String? _abriendo; // operación cuyo detalle se está preparando (evita abrirla dos veces)

  @override
  void initState() {
    super.initState();
    _abrirAlCargar = widget.abrirId;
    _cargar();
  }

  Future<void> _cargar() async {
    setState(() {
      _cargando = true;
      _error = null;
    });
    try {
      final respuestas = await Future.wait([
        _api.getOperacionesSync(estado: 'conflicto', limite: 500),
        _api.getOperacionesSync(limite: 200),
      ]);
      if (!mounted) return;
      setState(() {
        _porResolver = respuestas[0];
        _resueltas = respuestas[1].where((op) => op['resuelta_en'] != null).toList();
        _cargando = false;
      });
      final abrir = _abrirAlCargar;
      _abrirAlCargar = null;
      final op = _porResolver.where((o) => o['id'] == abrir).firstOrNull;
      if (op != null) await _decidir(op);
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = textoDeError(e);
        _cargando = false;
      });
    }
  }

  Future<void> _decidir(Map<String, dynamic> op) async {
    if (_abriendo != null) return;
    setState(() => _abriendo = '${op['id']}');
    final lineas = lineasDe(op);
    final variantes = await _describir(lineas.map((l) => l.varianteId));
    final sucursales = _api.esAdministrador ? await _otrasSucursales(op) : const <Map<String, dynamic>>[];
    if (!mounted) return;
    setState(() => _abriendo = null);
    final mensaje = await showModalBottomSheet<String>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (_) => HojaDecision(
        op: op,
        lineas: lineas,
        variantes: variantes,
        sucursales: sucursales,
        puedeReasignar: _api.esAdministrador,
      ),
    );
    if (mensaje == null || !mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(mensaje)));
    // Si la operación se registró en este teléfono, su estado local se actualiza ya
    unawaited(SincronizacionService().sincronizar().catchError((_) {}));
    await _cargar();
  }

  /// Nombres de las prendas con lo guardado para trabajar sin conexión (sin ellos, el número de variante).
  Future<Map<int, Map<String, dynamic>>> _describir(Iterable<int> ids) async {
    try {
      return await SincronizacionService().almacen.describirVariantes(ids);
    } catch (_) {
      return const {};
    }
  }

  Future<List<Map<String, dynamic>>> _otrasSucursales(Map<String, dynamic> op) async {
    try {
      final todas = await _api.getSucursales();
      return [
        for (final s in todas)
          if (s is Map && s['id'] != op['sucursal_id']) Map<String, dynamic>.from(s),
      ];
    } catch (_) {
      return const [];
    }
  }

  @override
  Widget build(BuildContext context) {
    final lista = _verResueltas ? _resueltas : _porResolver;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Conflictos de sincronización'),
        actions: [
          IconButton(tooltip: 'Actualizar', icon: const Icon(Icons.refresh), onPressed: _cargando ? null : _cargar),
        ],
      ),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 8),
            child: SizedBox(
              width: double.infinity,
              child: SegmentedButton<bool>(
                segments: [
                  ButtonSegment(
                    value: false,
                    icon: const Icon(Icons.warning_amber_rounded),
                    label: Text('Por resolver (${_porResolver.length})'),
                  ),
                  const ButtonSegment(value: true, icon: Icon(Icons.task_alt), label: Text('Resueltas')),
                ],
                selected: {_verResueltas},
                onSelectionChanged: (s) => setState(() => _verResueltas = s.first),
              ),
            ),
          ),
          Expanded(
            child: RefreshIndicator(
              onRefresh: _cargar,
              child: _cargando && lista.isEmpty
                  ? const Center(child: CircularProgressIndicator())
                  : _error != null
                      ? _Aviso(
                          icono: Icons.cloud_off,
                          titulo: 'No se pudieron traer los conflictos',
                          texto: _error!,
                          accion: FilledButton.icon(
                            onPressed: _cargar,
                            icon: const Icon(Icons.refresh),
                            label: const Text('Reintentar'),
                          ),
                        )
                      : lista.isEmpty
                          ? _Aviso(
                              icono: _verResueltas ? Icons.history : Icons.verified_outlined,
                              titulo: _verResueltas ? 'Todavía no se resolvió ningún conflicto' : 'No hay conflictos por resolver',
                              texto: _verResueltas
                                  ? 'Acá vas a ver cada decisión: quién la tomó, cuándo y con qué nota.'
                                  : 'Cuando una venta hecha sin conexión no se pueda registrar tal cual '
                                      '(por ejemplo, porque el stock del sistema no alcanza), aparece acá para que decidas.',
                            )
                          : ListView.separated(
                              padding: const EdgeInsets.fromLTRB(16, 4, 16, 24),
                              itemCount: lista.length,
                              separatorBuilder: (_, _) => const SizedBox(height: 12),
                              itemBuilder: (_, i) => _TarjetaOperacion(
                                op: lista[i],
                                onDecidir: _verResueltas ? null : () => _decidir(lista[i]),
                                abriendo: _abriendo == lista[i]['id'],
                              ),
                            ),
            ),
          ),
        ],
      ),
    );
  }
}

/// Una línea de la operación: qué prenda (variante), cuántas y en qué parte (cambio: devuelve/entrega).
typedef Linea = ({String? parte, int varianteId, int cantidad});

/// Las líneas que subió el dispositivo (los datos de la operación tal como llegaron).
List<Linea> lineasDe(Map<String, dynamic> op) {
  final datos = (op['datos'] as Map?)?['datos'];
  if (datos is! Map) return const [];
  List<Linea> de(String clave, String? parte) => [
        for (final l in (datos[clave] as List? ?? const []))
          if (l is Map && l['variante_id'] is int) (parte: parte, varianteId: l['variante_id'] as int, cantidad: (l['cantidad'] as num?)?.toInt() ?? 0),
      ];
  return op['tipo'] == 'cambio' ? [...de('devuelve', 'Devuelve'), ...de('entrega', 'Entrega')] : de('detalles', null);
}

String tipoDe(Map<String, dynamic> op) => switch (op['tipo']) {
      'venta' => 'Venta de contado',
      'cambio' => 'Cambio de prenda',
      'reserva' => 'Reserva',
      _ => '${op['tipo']}',
    };

IconData _iconoDe(Map<String, dynamic> op) => switch (op['tipo']) {
      'venta' => Icons.point_of_sale,
      'cambio' => Icons.swap_horiz,
      _ => Icons.event_available,
    };

/// Monto que se manejó en la tienda: el total cobrado (venta) o la diferencia (cambio).
String? montoDe(Map<String, dynamic> op) {
  final datos = (op['datos'] as Map?)?['datos'];
  if (datos is! Map) return null;
  final monto = op['tipo'] == 'cambio' ? datos['diferencia'] : datos['total'];
  if (monto is! num) return null;
  return op['tipo'] == 'cambio' ? 'Diferencia ${formatoBs(monto)}' : formatoBs(monto);
}

String _sucursalDe(Map<String, dynamic> op) => '${op['sucursal_nombre'] ?? 'Sucursal #${op['sucursal_id']}'}';

/// Qué se decidió, según cómo quedó la operación.
(String, Color) decisionDe(Map<String, dynamic> op) {
  if (op['estado'] == 'rechazada') return ('Anulada', _rojo);
  final original = (op['datos'] as Map?)?['sucursal_id'];
  return original != null && original != op['sucursal_id'] ? ('Reasignada', _verde) : ('Aceptada con ajuste', _verde);
}

String textoDeError(Object e) => e.toString().replaceFirst('Exception: ', '');

class _TarjetaOperacion extends StatelessWidget {
  final Map<String, dynamic> op;
  final VoidCallback? onDecidir;
  final bool abriendo;

  const _TarjetaOperacion({required this.op, this.onDecidir, this.abriendo = false});

  @override
  Widget build(BuildContext context) {
    final monto = montoDe(op);
    final resuelta = onDecidir == null;
    final (decision, color) = decisionDe(op);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                CircleAvatar(
                  radius: 22,
                  backgroundColor: context.marcaSuave,
                  child: Icon(_iconoDe(op), color: context.marca),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('${tipoDe(op)} · ${_sucursalDe(op)}', style: Theme.of(context).textTheme.titleSmall),
                      const SizedBox(height: 2),
                      Text(
                        '${op['usuario_correo'] ?? 'Usuario eliminado'} · ${fechaCorta('${op['registrada_en']}')}',
                        style: TextStyle(fontSize: 12.5, color: Colors.grey.shade700),
                      ),
                    ],
                  ),
                ),
                if (monto != null)
                  Text(monto, style: TextStyle(fontWeight: FontWeight.w800, color: context.marca)),
              ],
            ),
            const SizedBox(height: 12),
            if (resuelta) ...[
              Row(
                children: [
                  _Etiqueta(decision, color),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      'por ${op['resuelta_por_correo'] ?? '-'} · ${fechaCorta('${op['resuelta_en']}')}',
                      style: TextStyle(fontSize: 12.5, color: Colors.grey.shade700),
                    ),
                  ),
                ],
              ),
              if ((op['nota_resolucion'] ?? '').toString().isNotEmpty) ...[
                const SizedBox(height: 8),
                Text('Nota: ${op['nota_resolucion']}', style: const TextStyle(fontSize: 13)),
              ],
            ] else ...[
              _Motivo('${op['mensaje'] ?? 'La operación no se pudo registrar tal como se hizo en la tienda.'}'),
              const SizedBox(height: 12),
              SizedBox(
                width: double.infinity,
                child: FilledButton.tonalIcon(
                  onPressed: abriendo ? null : onDecidir,
                  icon: abriendo
                      ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))
                      : const Icon(Icons.gavel),
                  label: Text(abriendo ? 'Abriendo…' : 'Revisar y decidir'),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

/// Detalle del conflicto y las decisiones posibles (CU-14, pasos 3 a 6).
class HojaDecision extends StatefulWidget {
  final Map<String, dynamic> op;
  final List<Linea> lineas;
  final Map<int, Map<String, dynamic>> variantes;
  final List<Map<String, dynamic>> sucursales;
  final bool puedeReasignar;

  const HojaDecision({
    super.key,
    required this.op,
    required this.lineas,
    required this.variantes,
    required this.sucursales,
    required this.puedeReasignar,
  });

  @override
  State<HojaDecision> createState() => _HojaDecisionState();
}

class _HojaDecisionState extends State<HojaDecision> {
  final _nota = TextEditingController();
  String _accion = 'aceptar';
  int? _sucursalId;
  bool _enviando = false;
  String? _error;

  @override
  void dispose() {
    _nota.dispose();
    super.dispose();
  }

  String get _nombreSucursal =>
      '${widget.sucursales.where((s) => s['id'] == _sucursalId).firstOrNull?['nombre'] ?? 'la sucursal elegida'}';

  bool get _lista => !_enviando && (_accion != 'reasignar' || _sucursalId != null);

  String get _textoBoton => switch (_accion) {
        'reasignar' => _sucursalId == null ? 'Elegí la sucursal' : 'Reasignar a $_nombreSucursal',
        'anular' => 'Anular la operación',
        _ => 'Aceptar con ajuste',
      };

  Future<void> _aplicar() async {
    setState(() {
      _enviando = true;
      _error = null;
    });
    final nota = _nota.text.trim();
    try {
      await ApiService().resolverConflicto(
        '${widget.op['id']}',
        _accion,
        nota: nota.isEmpty ? null : nota,
        nuevaSucursalId: _accion == 'reasignar' ? _sucursalId : null,
      );
      if (!mounted) return;
      Navigator.of(context).pop(switch (_accion) {
        'reasignar' => 'Operación reasignada a $_nombreSucursal y registrada.',
        'anular' => 'Operación anulada: no se registró.',
        _ => 'Operación aceptada: se registró con ajuste de inventario.',
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _enviando = false;
        _error = textoDeError(e);
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final op = widget.op;
    final monto = montoDe(op);
    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.of(context).viewInsets.bottom),
      child: SafeArea(
        child: ConstrainedBox(
          constraints: BoxConstraints(maxHeight: MediaQuery.of(context).size.height * 0.88),
          child: ListView(
            shrinkWrap: true,
            padding: const EdgeInsets.fromLTRB(20, 0, 20, 20),
            children: [
              Text('Decidir el conflicto', style: Theme.of(context).textTheme.titleLarge),
              const SizedBox(height: 12),
              _Dato('Operación', tipoDe(op)),
              _Dato('Sucursal', _sucursalDe(op)),
              _Dato('Registrada por', '${op['usuario_correo'] ?? 'Usuario eliminado'}'),
              _Dato('Fecha en la tienda', fechaCorta('${op['registrada_en']}')),
              if (op['dispositivo'] != null) _Dato('Dispositivo', '${op['dispositivo']}'),
              const SizedBox(height: 8),
              _Motivo('${op['mensaje'] ?? 'La operación no se pudo registrar tal como se hizo en la tienda.'}'),
              if (widget.lineas.isNotEmpty) ...[
                const SizedBox(height: 12),
                for (final l in widget.lineas)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 4),
                    child: Text('${l.parte == null ? '' : '${l.parte}: '}${_prenda(l.varianteId)} × ${l.cantidad}'),
                  ),
              ],
              if (monto != null) ...[
                const SizedBox(height: 4),
                Text(op['tipo'] == 'venta' ? 'Total cobrado en efectivo: $monto' : monto,
                    style: const TextStyle(fontWeight: FontWeight.w700)),
              ],
              const Divider(height: 28),
              Text('¿Qué hacemos?', style: Theme.of(context).textTheme.titleMedium),
              const SizedBox(height: 8),
              _Opcion(
                icono: Icons.inventory_2_outlined,
                titulo: 'Aceptar con ajuste',
                texto: 'Se registra tal como se hizo en la tienda. Lo que falte de stock queda en el kardex de la sucursal.',
                elegida: _accion == 'aceptar',
                onTap: () => setState(() => _accion = 'aceptar'),
              ),
              if (widget.puedeReasignar) ...[
                _Opcion(
                  icono: Icons.alt_route,
                  titulo: 'Reasignar a otra sucursal',
                  texto: 'Se registra descontando el stock de la sucursal de donde salió la prenda.',
                  elegida: _accion == 'reasignar',
                  onTap: () => setState(() => _accion = 'reasignar'),
                ),
                if (_accion == 'reasignar')
                  Padding(
                    padding: const EdgeInsets.fromLTRB(4, 0, 4, 12),
                    child: widget.sucursales.isEmpty
                        ? const Text('No hay otra sucursal activa (o no se pudieron cargar).')
                        : Wrap(
                            spacing: 8,
                            runSpacing: 8,
                            children: [
                              for (final s in widget.sucursales)
                                ChoiceChip(
                                  label: Text('${s['nombre']}'),
                                  selected: _sucursalId == s['id'],
                                  onSelected: (_) => setState(() => _sucursalId = s['id'] as int),
                                ),
                            ],
                          ),
                  ),
              ],
              _Opcion(
                icono: Icons.block,
                titulo: 'Anular',
                texto: 'No se registra. La tienda devuelve el dinero o recupera la prenda.',
                elegida: _accion == 'anular',
                onTap: () => setState(() => _accion = 'anular'),
                peligrosa: true,
              ),
              const SizedBox(height: 8),
              TextField(
                controller: _nota,
                maxLength: 300,
                maxLines: 2,
                textCapitalization: TextCapitalization.sentences,
                decoration: const InputDecoration(
                  labelText: 'Nota para la bitácora (opcional)',
                  hintText: 'Motivo o quién lo autorizó',
                ),
              ),
              if (_error != null)
                Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: Text(_error!, style: const TextStyle(color: _rojo)),
                ),
              FilledButton(
                onPressed: _lista ? _aplicar : null,
                style: _accion == 'anular' ? FilledButton.styleFrom(backgroundColor: _rojo, foregroundColor: Colors.white) : null,
                child: _enviando
                    ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2))
                    : Text(_textoBoton),
              ),
            ],
          ),
        ),
      ),
    );
  }

  String _prenda(int varianteId) {
    final v = widget.variantes[varianteId];
    if (v == null) return 'Variante #$varianteId';
    return '${v['prenda_nombre']} (${v['talla_nombre'] ?? '-'} / ${v['color_nombre'] ?? '-'})';
  }
}

class _Opcion extends StatelessWidget {
  final IconData icono;
  final String titulo;
  final String texto;
  final bool elegida;
  final VoidCallback onTap;
  final bool peligrosa;

  const _Opcion({
    required this.icono,
    required this.titulo,
    required this.texto,
    required this.elegida,
    required this.onTap,
    this.peligrosa = false,
  });

  @override
  Widget build(BuildContext context) {
    final color = peligrosa ? _rojo : context.marca;
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Material(
        color: elegida ? color.withValues(alpha: 0.08) : Colors.white,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
          side: BorderSide(color: elegida ? color : Colors.grey.shade300, width: elegida ? 2 : 1),
        ),
        child: InkWell(
          borderRadius: BorderRadius.circular(16),
          onTap: onTap,
          child: Padding(
            padding: const EdgeInsets.all(14),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(icono, color: color),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(titulo, style: TextStyle(fontWeight: FontWeight.w700, color: peligrosa ? _rojo : null)),
                      const SizedBox(height: 2),
                      Text(texto, style: TextStyle(fontSize: 12.5, color: Colors.grey.shade700)),
                    ],
                  ),
                ),
                Icon(elegida ? Icons.radio_button_checked : Icons.radio_button_off, color: elegida ? color : Colors.grey),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _Motivo extends StatelessWidget {
  final String texto;

  const _Motivo(this.texto);

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: const Color(0xFFFFF7ED),
        border: Border.all(color: const Color(0xFFFDBA74)),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(Icons.warning_amber_rounded, color: _naranja, size: 20),
          const SizedBox(width: 8),
          Expanded(child: Text(texto, style: const TextStyle(fontSize: 13, color: Color(0xFF9A3412)))),
        ],
      ),
    );
  }
}

class _Etiqueta extends StatelessWidget {
  final String texto;
  final Color color;

  const _Etiqueta(this.texto, this.color);

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(color: color.withValues(alpha: 0.12), borderRadius: BorderRadius.circular(20)),
      child: Text(texto, style: TextStyle(color: color, fontWeight: FontWeight.w700, fontSize: 12)),
    );
  }
}

class _Dato extends StatelessWidget {
  final String etiqueta;
  final String valor;

  const _Dato(this.etiqueta, this.valor);

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 4),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(width: 130, child: Text(etiqueta, style: TextStyle(color: Colors.grey.shade700))),
          Expanded(child: Text(valor, style: const TextStyle(fontWeight: FontWeight.w600))),
        ],
      ),
    );
  }
}

class _Aviso extends StatelessWidget {
  final IconData icono;
  final String titulo;
  final String texto;
  final Widget? accion;

  const _Aviso({required this.icono, required this.titulo, required this.texto, this.accion});

  @override
  Widget build(BuildContext context) {
    // ListView para que también se pueda tirar hacia abajo y actualizar
    return ListView(
      padding: const EdgeInsets.fromLTRB(32, 64, 32, 32),
      children: [
        Icon(icono, size: 56, color: context.marca),
        const SizedBox(height: 16),
        Text(titulo, textAlign: TextAlign.center, style: Theme.of(context).textTheme.titleMedium),
        const SizedBox(height: 8),
        Text(texto, textAlign: TextAlign.center, style: TextStyle(color: Colors.grey.shade700)),
        if (accion != null) ...[const SizedBox(height: 20), Center(child: accion)],
      ],
    );
  }
}
