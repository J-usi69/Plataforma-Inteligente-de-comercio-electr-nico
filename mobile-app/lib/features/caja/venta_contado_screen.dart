import 'dart:async';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../core/offline/reglas.dart';
import '../../core/offline/sincronizacion_service.dart';
import '../../core/services/api_service.dart';

class _Linea {
  final int varianteId;
  final String descripcion;
  final double precio;
  int cantidad;
  int stock;

  _Linea({required this.varianteId, required this.descripcion, required this.precio, required this.stock}) : cantidad = 1;

  Map<String, dynamic> get comoDetalle => {'variante_id': varianteId, 'cantidad': cantidad, 'precio_unitario': precio};
}

/// CU-11: el Cajero registra una venta de contado con o sin conexión. Precios y existencias salen
/// de los datos guardados en el teléfono; la venta entra a la cola y el servidor la confirma al
/// sincronizar (o la deja en conflicto si ya no hay stock). Sin conexión solo se cobra en efectivo.
class VentaContadoScreen extends StatefulWidget {
  const VentaContadoScreen({super.key});

  @override
  State<VentaContadoScreen> createState() => _VentaContadoScreenState();
}

class _VentaContadoScreenState extends State<VentaContadoScreen> {
  final _sync = SincronizacionService();
  final _busqueda = TextEditingController();
  final _recibido = TextEditingController();
  final List<_Linea> _lineas = [];
  List<Map<String, dynamic>> _sucursales = [];
  List<Map<String, dynamic>> _clientes = [];
  List<Map<String, dynamic>> _resultados = [];
  int? _sucursalId;
  int? _clienteId;
  bool _registrando = false;
  Timer? _demora;

  @override
  void initState() {
    super.initState();
    _sync.addListener(_alCambiarDatos);
    _cargar();
  }

  @override
  void dispose() {
    _sync.removeListener(_alCambiarDatos);
    _demora?.cancel();
    _busqueda.dispose();
    _recibido.dispose();
    super.dispose();
  }

  // El paquete puede llegar después de abrir la pantalla (p. ej. recién iniciada la sesión)
  void _alCambiarDatos() {
    if (_sync.tieneDatos && _sucursales.isEmpty) _cargar();
  }

  Future<void> _cargar() async {
    if (!_sync.tieneDatos) return;
    final sucursales = await _sync.almacen.sucursales();
    final clientes = await _sync.almacen.clientes();
    if (!mounted) return;
    setState(() {
      _sucursales = sucursales;
      _clientes = clientes;
      _sucursalId ??= sucursales.isEmpty ? null : sucursales.first['id'] as int;
    });
  }

  double get _total => totalDe(_lineas.map((l) => l.comoDetalle).toList());
  double? get _montoRecibido => double.tryParse(_recibido.text.replaceAll(',', '.'));

  void _alEscribir(String texto) {
    _demora?.cancel();
    _demora = Timer(const Duration(milliseconds: 250), () => _buscar(texto));
  }

  Future<void> _buscar(String texto) async {
    final sucursalId = _sucursalId;
    if (sucursalId == null || texto.trim().length < 2) {
      setState(() => _resultados = []);
      return;
    }
    final resultados = await _sync.almacen.buscarVariantes(texto, sucursalId);
    if (mounted) setState(() => _resultados = resultados);
  }

  void _agregar(Map<String, dynamic> r) {
    setState(() {
      final existente = _lineas.where((l) => l.varianteId == r['variante_id']).firstOrNull;
      if (existente != null) {
        existente.cantidad++;
      } else {
        _lineas.add(_Linea(
          varianteId: r['variante_id'] as int,
          descripcion: '${r['prenda_nombre']} (${r['talla_nombre'] ?? '-'} / ${r['color_nombre'] ?? '-'})',
          precio: (r['precio_base'] as num).toDouble(),
          stock: r['stock'] as int,
        ));
      }
      _busqueda.clear();
      _resultados = [];
    });
  }

  void _elegirPagoElectronico() {
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
      content: Text(_sync.enLinea
          ? 'En la app la caja cobra solo en efectivo: tarjeta y QR se cobran desde la caja web.'
          : 'Sin conexión solo se cobra en efectivo: tarjeta y QR necesitan Internet.'),
    ));
  }

  Future<void> _confirmar() async {
    final sucursalId = _sucursalId;
    if (_lineas.isEmpty || sucursalId == null) return;
    final messenger = ScaffoldMessenger.of(context);
    final recibido = _montoRecibido;
    if (recibido != null && recibido < _total) {
      messenger.showSnackBar(const SnackBar(content: Text('El monto recibido no alcanza para el total.')));
      return;
    }
    // Existencia conocida al momento de cobrar (ya descuenta lo vendido en este teléfono)
    for (final l in _lineas) {
      l.stock = await _sync.almacen.stock(l.varianteId, sucursalId);
    }
    final excedidas = _lineas.where((l) => l.cantidad > l.stock).toList();
    if (excedidas.isNotEmpty && mounted) {
      final seguir = await showDialog<bool>(
        context: context,
        builder: (context) => AlertDialog(
          title: const Text('Existencia insuficiente'),
          content: Text(
            'Según los datos guardados no alcanza el stock de:\n'
            '${excedidas.map((l) => '• ${l.descripcion}: hay ${l.stock}, vendés ${l.cantidad}').join('\n')}\n\n'
            'Podés quitar las prendas o registrar igual: al sincronizar, si el servidor confirma que no '
            'alcanza, la venta queda en conflicto para el administrador.',
          ),
          actions: [
            TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Revisar')),
            FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Registrar igual')),
          ],
        ),
      );
      if (seguir != true) {
        setState(() {});
        return;
      }
    }

    setState(() => _registrando = true);
    final total = _total;
    try {
      final op = await _sync.registrar('venta', sucursalId, {
        'cliente_id': _clienteId,
        'detalles': _lineas.map((l) => l.comoDetalle).toList(),
        'total': total,
        'metodo_pago': 'efectivo',
        'monto_recibido': recibido,
      });
      if (!mounted) return;
      setState(() {
        _lineas.clear();
        _recibido.clear();
        _clienteId = null;
        _registrando = false;
      });
      await _mostrarRegistrada(codigoProvisional(op.id), total, recibido);
    } catch (e) {
      if (!mounted) return;
      setState(() => _registrando = false);
      messenger.showSnackBar(SnackBar(
        content: Text(e.toString().replaceAll('Exception: ', '')),
        backgroundColor: Colors.red.shade700,
      ));
    }
  }

  Future<void> _mostrarRegistrada(String codigo, double total, double? recibido) {
    final enLinea = _sync.enLinea;
    return showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        icon: const Icon(Icons.check_circle, color: Colors.green, size: 48),
        title: const Text('Venta registrada'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text('Comprobante provisional $codigo', style: const TextStyle(fontWeight: FontWeight.w700)),
            const SizedBox(height: 6),
            Text('Total cobrado: ${formatoBs(total)}'),
            if (recibido != null) Text('Cambio: ${formatoBs(recibido - total)}'),
            const SizedBox(height: 10),
            Text(
              enLinea
                  ? 'Se está enviando al servidor para confirmarla.'
                  : 'Quedó guardada en el teléfono y se enviará sola cuando vuelva la conexión.',
              textAlign: TextAlign.center,
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () {
              Navigator.pop(context);
              context.push('/pendientes');
            },
            child: const Text('Ver operaciones'),
          ),
          FilledButton(onPressed: () => Navigator.pop(context), child: const Text('Nueva venta')),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    if (!ApiService().puedeCobrarEnCaja) {
      return Scaffold(
        appBar: AppBar(title: const Text('Venta de contado')),
        body: const Center(
          child: Padding(
            padding: EdgeInsets.all(24),
            child: Text('Solo el Cajero o el Administrador registran ventas de contado.', textAlign: TextAlign.center),
          ),
        ),
      );
    }
    return ListenableBuilder(
      listenable: _sync,
      builder: (context, _) => Scaffold(
        appBar: AppBar(title: const Text('Venta de contado')),
        body: _sync.tieneDatos ? _caja() : _sinDatos(),
      ),
    );
  }

  Widget _sinDatos() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.download_for_offline_outlined, size: 56, color: Color(0xFF4F46E5)),
            const SizedBox(height: 12),
            const Text(
              'La caja usa el catálogo guardado en el teléfono, y todavía no está descargado.',
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 16),
            FilledButton.icon(
              onPressed: _sync.enLinea && !_sync.descargando ? () => _sync.descargarPaquete() : null,
              icon: const Icon(Icons.download),
              label: Text(_sync.descargando ? 'Descargando…' : 'Descargar datos'),
              style: FilledButton.styleFrom(minimumSize: const Size(200, 48)),
            ),
            if (!_sync.enLinea)
              const Padding(
                padding: EdgeInsets.only(top: 8),
                child: Text('Necesitás conexión una vez para descargarlo.'),
              ),
          ],
        ),
      ),
    );
  }

  Widget _caja() {
    final recibido = _montoRecibido;
    return Column(
      children: [
        Expanded(
          child: ListView(
            padding: const EdgeInsets.all(16),
            children: [
              if (_sucursales.length > 1)
                DropdownButtonFormField<int>(
                  initialValue: _sucursalId,
                  decoration: const InputDecoration(labelText: 'Sucursal', border: OutlineInputBorder()),
                  items: [
                    for (final s in _sucursales)
                      DropdownMenuItem(value: s['id'] as int, child: Text('${s['nombre']}')),
                  ],
                  onChanged: _lineas.isEmpty ? (v) => setState(() => _sucursalId = v) : null,
                )
              else if (_sucursales.isNotEmpty)
                Text('Sucursal: ${_sucursales.first['nombre']}', style: const TextStyle(fontWeight: FontWeight.w600)),
              const SizedBox(height: 14),
              TextField(
                controller: _busqueda,
                onChanged: _alEscribir,
                textInputAction: TextInputAction.search,
                decoration: const InputDecoration(
                  labelText: 'Buscar prenda o código de barras',
                  prefixIcon: Icon(Icons.search),
                  border: OutlineInputBorder(),
                ),
              ),
              if (_resultados.isNotEmpty)
                Card(
                  margin: const EdgeInsets.only(top: 6),
                  child: Column(
                    children: [
                      for (final r in _resultados.take(8))
                        ListTile(
                          title: Text('${r['prenda_nombre']}'),
                          subtitle: Text(
                            '${r['talla_nombre'] ?? '-'} · ${r['color_nombre'] ?? '-'} · stock ${r['stock']} · ${formatoBs(r['precio_base'] as num)}',
                          ),
                          trailing: const Icon(Icons.add_circle, color: Color(0xFF4F46E5)),
                          onTap: () => _agregar(r),
                        ),
                    ],
                  ),
                )
              else if (_busqueda.text.trim().length >= 2)
                const Padding(
                  padding: EdgeInsets.only(top: 8),
                  child: Text('No hay prendas guardadas con ese nombre o código.'),
                ),
              const SizedBox(height: 16),
              if (_lineas.isEmpty)
                const Padding(
                  padding: EdgeInsets.symmetric(vertical: 20),
                  child: Text('Agregá prendas buscándolas por nombre o código.', textAlign: TextAlign.center),
                )
              else
                for (final l in _lineas) _linea(l),
              const SizedBox(height: 12),
              DropdownButtonFormField<int?>(
                initialValue: _clienteId,
                isExpanded: true,
                decoration: const InputDecoration(labelText: 'Cliente', border: OutlineInputBorder()),
                items: [
                  const DropdownMenuItem<int?>(value: null, child: Text('Cliente ocasional')),
                  for (final c in _clientes)
                    DropdownMenuItem<int?>(value: c['id'] as int, child: Text('${c['correo']}', overflow: TextOverflow.ellipsis)),
                ],
                onChanged: (v) => setState(() => _clienteId = v),
              ),
              const SizedBox(height: 14),
              const Text('Forma de pago', style: TextStyle(fontWeight: FontWeight.w600)),
              const SizedBox(height: 6),
              Wrap(
                spacing: 8,
                children: [
                  const ChoiceChip(label: Text('Efectivo'), selected: true),
                  ChoiceChip(label: const Text('Tarjeta'), selected: false, onSelected: (_) => _elegirPagoElectronico()),
                  ChoiceChip(label: const Text('QR'), selected: false, onSelected: (_) => _elegirPagoElectronico()),
                ],
              ),
              const SizedBox(height: 14),
              TextField(
                controller: _recibido,
                onChanged: (_) => setState(() {}),
                keyboardType: const TextInputType.numberWithOptions(decimal: true),
                decoration: InputDecoration(
                  labelText: 'Monto recibido (opcional)',
                  prefixText: 'Bs. ',
                  border: const OutlineInputBorder(),
                  helperText: recibido != null && recibido >= _total && _lineas.isNotEmpty
                      ? 'Cambio: ${formatoBs(recibido - _total)}'
                      : null,
                ),
              ),
            ],
          ),
        ),
        _barraTotal(),
      ],
    );
  }

  Widget _linea(_Linea l) {
    final excede = l.cantidad > l.stock;
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: Padding(
        padding: const EdgeInsets.fromLTRB(14, 8, 4, 8),
        child: Row(
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(l.descripcion, style: const TextStyle(fontWeight: FontWeight.w600)),
                  Text('${formatoBs(l.precio)} c/u · ${formatoBs(redondear(l.precio * l.cantidad))}'),
                  if (excede)
                    Text('Stock guardado: ${l.stock}', style: TextStyle(color: Colors.orange.shade800, fontSize: 12.5)),
                ],
              ),
            ),
            IconButton(
              tooltip: 'Quitar una',
              icon: const Icon(Icons.remove_circle_outline),
              onPressed: () => setState(() => l.cantidad > 1 ? l.cantidad-- : _lineas.remove(l)),
            ),
            Text('${l.cantidad}', style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
            IconButton(
              tooltip: 'Agregar una',
              icon: const Icon(Icons.add_circle_outline),
              onPressed: () => setState(() => l.cantidad++),
            ),
          ],
        ),
      ),
    );
  }

  Widget _barraTotal() {
    return Material(
      elevation: 8,
      child: SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 10, 16, 12),
          child: Row(
            children: [
              Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('Total', style: TextStyle(color: Colors.black54)),
                  Text(formatoBs(_total), style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w800)),
                ],
              ),
              const SizedBox(width: 16),
              Expanded(
                child: FilledButton(
                  onPressed: _lineas.isEmpty || _registrando ? null : _confirmar,
                  style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(52)),
                  child: Text(_registrando ? 'Registrando…' : 'Confirmar recepción del efectivo', textAlign: TextAlign.center),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
