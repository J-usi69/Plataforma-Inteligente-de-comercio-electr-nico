import 'package:flutter/material.dart';
import '../../core/services/api_service.dart';

class SucursalesScreen extends StatefulWidget {
  const SucursalesScreen({super.key});

  @override
  State<SucursalesScreen> createState() => _SucursalesScreenState();
}

class _SucursalesScreenState extends State<SucursalesScreen> {
  final _apiService = ApiService();
  bool _isLoading = true;
  List<dynamic> _sucursales = [];
  List<dynamic> _ciudades = [];
  int? _selectedCiudadId;

  @override
  void initState() {
    super.initState();
    _cargarDatos();
  }

  Future<void> _cargarDatos() async {
    setState(() => _isLoading = true);
    try {
      final ciudades = await _apiService.getCiudades();
      final sucursales = await _apiService.getSucursales(ciudadId: _selectedCiudadId);
      setState(() {
        _ciudades = ciudades;
        _sucursales = sucursales;
      });
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error: $e'), backgroundColor: Colors.red),
      );
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Nuestras Sucursales'),
        centerTitle: true,
      ),
      body: Column(
        children: [
          // Selector de Ciudad
          if (_ciudades.isNotEmpty)
            SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
              child: Row(
                children: [
                  ChoiceChip(
                    label: const Text('Todas'),
                    selected: _selectedCiudadId == null,
                    onSelected: (selected) {
                      if (selected) {
                        setState(() => _selectedCiudadId = null);
                        _cargarDatos();
                      }
                    },
                  ),
                  const SizedBox(width: 8),
                  ..._ciudades.map((c) {
                    final isSelected = _selectedCiudadId == c['id'];
                    return Padding(
                      padding: const EdgeInsets.only(right: 8),
                      child: ChoiceChip(
                        label: Text(c['nombre']),
                        selected: isSelected,
                        onSelected: (selected) {
                          setState(() {
                            _selectedCiudadId = selected ? c['id'] : null;
                          });
                          _cargarDatos();
                        },
                      ),
                    );
                  }),
                ],
              ),
            ),
          const Divider(height: 1),
          Expanded(
            child: _isLoading
                ? const Center(child: CircularProgressIndicator())
                : _sucursales.isEmpty
                    ? const Center(child: Text('No hay sucursales disponibles en esta ciudad.'))
                    : ListView.builder(
                        padding: const EdgeInsets.all(16),
                        itemCount: _sucursales.length,
                        itemBuilder: (context, index) {
                          final s = _sucursales[index];
                          return Card(
                            margin: const EdgeInsets.only(bottom: 12),
                            elevation: 1,
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(10),
                              side: BorderSide(color: Colors.grey.shade200),
                            ),
                            child: Padding(
                              padding: const EdgeInsets.all(16),
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Row(
                                    children: [
                                      const Icon(Icons.storefront, color: Colors.indigo),
                                      const SizedBox(width: 8),
                                      Expanded(
                                        child: Text(
                                          s['nombre'],
                                          style: const TextStyle(
                                            fontSize: 16,
                                            fontWeight: FontWeight.bold,
                                          ),
                                        ),
                                      ),
                                      Container(
                                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                                        decoration: BoxDecoration(
                                          color: Colors.indigo.shade50,
                                          borderRadius: BorderRadius.circular(12),
                                        ),
                                        child: Text(
                                          s['ciudad_nombre'] ?? 'Sucursal',
                                          style: const TextStyle(
                                            fontSize: 11,
                                            fontWeight: FontWeight.bold,
                                            color: Colors.indigo,
                                          ),
                                        ),
                                      ),
                                    ],
                                  ),
                                  const SizedBox(height: 8),
                                  Row(
                                    children: [
                                      const Icon(Icons.location_on_outlined, size: 16, color: Colors.black54),
                                      const SizedBox(width: 4),
                                      Expanded(
                                        child: Text(
                                          s['direccion'],
                                          style: const TextStyle(fontSize: 13, color: Colors.black87),
                                        ),
                                      ),
                                    ],
                                  ),
                                  const SizedBox(height: 6),
                                  Row(
                                    children: [
                                      const Icon(Icons.access_time, size: 16, color: Colors.black54),
                                      const SizedBox(width: 4),
                                      Text(
                                        'Horario: ${s['hora_inicio'] ?? '09:00'} - ${s['hora_fin'] ?? '21:00'}',
                                        style: const TextStyle(fontSize: 13, color: Colors.black87),
                                      ),
                                      if (s['telefono'] != null) ...[
                                        const SizedBox(width: 16),
                                        const Icon(Icons.phone_outlined, size: 16, color: Colors.black54),
                                        const SizedBox(width: 4),
                                        Text(
                                          s['telefono'],
                                          style: const TextStyle(fontSize: 13, color: Colors.black87),
                                        ),
                                      ],
                                    ],
                                  ),
                                ],
                              ),
                            ),
                          );
                        },
                      ),
          ),
        ],
      ),
    );
  }
}

