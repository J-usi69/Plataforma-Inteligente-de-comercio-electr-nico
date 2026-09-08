import 'package:flutter/material.dart';
import '../../core/services/api_service.dart';

class ReservasScreen extends StatefulWidget {
  const ReservasScreen({super.key});

  @override
  State<ReservasScreen> createState() => _ReservasScreenState();
}

class _ReservasScreenState extends State<ReservasScreen> {
  final _apiService = ApiService();
  bool _isLoading = true;
  List<dynamic> _reservas = [];
  int? _cancelandoId;

  @override
  void initState() {
    super.initState();
    _cargarReservas();
  }

  Future<void> _cargarReservas() async {
    setState(() => _isLoading = true);
    try {
      final reservas = await _apiService.getMisReservas();
      setState(() => _reservas = reservas);
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error al cargar reservas: $e'), backgroundColor: Colors.red),
      );
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  Future<void> _cancelar(Map<String, dynamic> reserva) async {
    final confirmar = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Cancelar reserva'),
        content: const Text('¿Seguro que quieres cancelar esta reserva?'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('No')),
          TextButton(onPressed: () => Navigator.pop(context, true), child: const Text('Sí, cancelar')),
        ],
      ),
    );
    if (confirmar != true) return;

    setState(() => _cancelandoId = reserva['id'] as int);
    try {
      await _apiService.cancelarReserva(reserva['id'] as int);
      await _cargarReservas();
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(e.toString().replaceAll('Exception: ', '')), backgroundColor: Colors.red),
      );
    } finally {
      if (mounted) setState(() => _cancelandoId = null);
    }
  }

  Color _colorEstado(String estado) {
    switch (estado) {
      case 'pendiente':
        return Colors.orange;
      case 'confirmada':
        return Colors.blue;
      case 'atendida':
        return Colors.green;
      default:
        return Colors.red;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Mis reservas')),
      body: RefreshIndicator(
        onRefresh: _cargarReservas,
        child: _isLoading
            ? const Center(child: CircularProgressIndicator())
            : _reservas.isEmpty
                ? ListView(
                    children: const [
                      SizedBox(height: 100),
                      Center(child: Text('Todavía no tienes reservas.')),
                    ],
                  )
                : ListView.builder(
                    padding: const EdgeInsets.all(16),
                    itemCount: _reservas.length,
                    itemBuilder: (context, index) {
                      final r = _reservas[index];
                      final estado = r['estado'] as String;
                      final detalles = (r['detalles'] as List<dynamic>? ?? []);

                      return Card(
                        margin: const EdgeInsets.only(bottom: 14),
                        child: Padding(
                          padding: const EdgeInsets.all(14),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Row(
                                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                children: [
                                  Text('Reserva #${r['id']}', style: const TextStyle(fontWeight: FontWeight.bold)),
                                  Chip(
                                    label: Text(estado, style: const TextStyle(color: Colors.white, fontSize: 12)),
                                    backgroundColor: _colorEstado(estado),
                                    padding: EdgeInsets.zero,
                                  ),
                                ],
                              ),
                              const SizedBox(height: 6),
                              Text(r['sucursal_nombre'] ?? '', style: const TextStyle(fontWeight: FontWeight.w600)),
                              if (r['horario_atencion'] != null) Text('Horario: ${r['horario_atencion']}'),
                              const Divider(),
                              ...detalles.map(
                                (d) => Text(
                                  '${d['prenda_nombre']} (${d['talla_nombre']} / ${d['color_nombre']}) × ${d['cantidad']}',
                                  style: const TextStyle(fontSize: 13),
                                ),
                              ),
                              if (estado == 'pendiente') ...[
                                const SizedBox(height: 10),
                                Align(
                                  alignment: Alignment.centerRight,
                                  child: OutlinedButton(
                                    onPressed: _cancelandoId == r['id'] ? null : () => _cancelar(r),
                                    style: OutlinedButton.styleFrom(foregroundColor: Colors.red),
                                    child: Text(_cancelandoId == r['id'] ? 'Cancelando...' : 'Cancelar reserva'),
                                  ),
                                ),
                              ],
                            ],
                          ),
                        ),
                      );
                    },
                  ),
      ),
    );
  }
}
