import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../core/services/api_service.dart';

class ReservarScreen extends StatefulWidget {
  final Map<String, dynamic> prenda;

  const ReservarScreen({super.key, required this.prenda});

  @override
  State<ReservarScreen> createState() => _ReservarScreenState();
}

class _ReservarScreenState extends State<ReservarScreen> {
  final _apiService = ApiService();

  bool _cargandoVariantes = true;
  List<dynamic> _variantes = [];
  Map<String, dynamic>? _varianteSeleccionada;

  bool _cargandoDisponibilidad = false;
  List<dynamic> _disponibilidad = [];
  Map<String, dynamic>? _sucursalSeleccionada;

  int _cantidad = 1;
  bool _enviando = false;
  String? _error;
  bool _exito = false;

  @override
  void initState() {
    super.initState();
    _cargarVariantes();
  }

  Future<void> _cargarVariantes() async {
    try {
      final variantes = await _apiService.getVariantes(widget.prenda['id'] as int);
      setState(() {
        _variantes = variantes.where((v) => v['estado'] == true).toList();
        _cargandoVariantes = false;
      });
    } catch (e) {
      setState(() {
        _cargandoVariantes = false;
        _error = e.toString().replaceAll('Exception: ', '');
      });
    }
  }

  Future<void> _seleccionarVariante(Map<String, dynamic> variante) async {
    setState(() {
      _varianteSeleccionada = variante;
      _sucursalSeleccionada = null;
      _cargandoDisponibilidad = true;
      _disponibilidad = [];
    });
    try {
      final disponibilidad = await _apiService.getDisponibilidad(variante['id'] as int);
      setState(() {
        _disponibilidad = disponibilidad;
        _cargandoDisponibilidad = false;
      });
    } catch (e) {
      setState(() {
        _cargandoDisponibilidad = false;
        _error = e.toString().replaceAll('Exception: ', '');
      });
    }
  }

  Future<void> _confirmarReserva() async {
    if (_varianteSeleccionada == null || _sucursalSeleccionada == null) return;

    setState(() {
      _enviando = true;
      _error = null;
    });

    try {
      await _apiService.crearReserva(
        sucursalId: _sucursalSeleccionada!['sucursal_id'] as int,
        varianteId: _varianteSeleccionada!['id'] as int,
        cantidad: _cantidad,
      );
      if (!mounted) return;
      setState(() {
        _enviando = false;
        _exito = true;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _enviando = false;
        _error = e.toString().replaceAll('Exception: ', '');
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Reservar prenda')),
      body: _exito ? _buildExito() : _buildFormulario(),
    );
  }

  Widget _buildExito() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.check_circle, size: 96, color: Colors.green),
            const SizedBox(height: 16),
            const Text(
              '¡Reserva creada!',
              style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 8),
            const Text(
              'Preséntate en la sucursal seleccionada para probarte la prenda.',
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 24),
            ElevatedButton(
              onPressed: () => context.push('/reservas'),
              style: ElevatedButton.styleFrom(backgroundColor: Colors.indigo, foregroundColor: Colors.white),
              child: const Text('Ver mis reservas'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildFormulario() {
    if (_cargandoVariantes) {
      return const Center(child: CircularProgressIndicator());
    }

    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            widget.prenda['nombre'] ?? '',
            style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 20),
          if (_error != null)
            Container(
              padding: const EdgeInsets.all(12),
              margin: const EdgeInsets.only(bottom: 16),
              decoration: BoxDecoration(color: Colors.red.shade50, borderRadius: BorderRadius.circular(8)),
              child: Text(_error!, style: const TextStyle(color: Colors.red)),
            ),

          const Text('1. Elige talla y color', style: TextStyle(fontWeight: FontWeight.bold)),
          const SizedBox(height: 8),
          if (_variantes.isEmpty)
            const Text('Esta prenda todavía no tiene variantes registradas.')
          else
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: _variantes.map((v) {
                final seleccionada = _varianteSeleccionada?['id'] == v['id'];
                return ChoiceChip(
                  label: Text('${v['talla_nombre']} · ${v['color_nombre']}'),
                  selected: seleccionada,
                  onSelected: (_) => _seleccionarVariante(v),
                );
              }).toList(),
            ),

          if (_varianteSeleccionada != null) ...[
            const SizedBox(height: 24),
            const Text('2. Elige sucursal (con stock disponible)', style: TextStyle(fontWeight: FontWeight.bold)),
            const SizedBox(height: 8),
            if (_cargandoDisponibilidad)
              const Center(child: CircularProgressIndicator())
            else if (_disponibilidad.isEmpty)
              const Text('No hay stock disponible de esta variante en ninguna sucursal.')
            else
              Column(
                children: _disponibilidad.map((d) {
                  final seleccionada = _sucursalSeleccionada?['sucursal_id'] == d['sucursal_id'];
                  return Card(
                    color: seleccionada ? Colors.indigo.shade50 : null,
                    child: RadioListTile<int>(
                      value: d['sucursal_id'] as int,
                      groupValue: _sucursalSeleccionada?['sucursal_id'] as int?,
                      onChanged: (_) => setState(() {
                        _sucursalSeleccionada = d;
                        _cantidad = 1;
                      }),
                      title: Text('${d['sucursal_nombre']} — ${d['ciudad_nombre']}'),
                      subtitle: Text('${d['direccion']} · Stock: ${d['stock_disponible']}'),
                    ),
                  );
                }).toList(),
              ),
          ],

          if (_sucursalSeleccionada != null) ...[
            const SizedBox(height: 24),
            const Text('3. Cantidad', style: TextStyle(fontWeight: FontWeight.bold)),
            const SizedBox(height: 8),
            Row(
              children: [
                IconButton(
                  onPressed: _cantidad > 1 ? () => setState(() => _cantidad--) : null,
                  icon: const Icon(Icons.remove_circle_outline),
                ),
                Text('$_cantidad', style: const TextStyle(fontSize: 18)),
                IconButton(
                  onPressed: _cantidad < (_sucursalSeleccionada!['stock_disponible'] as int)
                      ? () => setState(() => _cantidad++)
                      : null,
                  icon: const Icon(Icons.add_circle_outline),
                ),
              ],
            ),
            const SizedBox(height: 24),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: _enviando ? null : _confirmarReserva,
                style: ElevatedButton.styleFrom(
                  padding: const EdgeInsets.symmetric(vertical: 14),
                  backgroundColor: Colors.indigo,
                  foregroundColor: Colors.white,
                ),
                child: Text(_enviando ? 'Enviando...' : 'Confirmar reserva'),
              ),
            ),
          ],
        ],
      ),
    );
  }
}
