import 'package:flutter/material.dart';

import '../../core/offline/reglas.dart';
import '../../core/services/api_service.dart';
import '../../core/theme/tema.dart';

/// Pantalla móvil de Reportes Inteligentes y Analítica con Machine Learning (CU-16, CU-17, CU-18)
class ReportesIaScreen extends StatefulWidget {
  const ReportesIaScreen({super.key});

  @override
  State<ReportesIaScreen> createState() => _ReportesIaScreenState();
}

class _ReportesIaScreenState extends State<ReportesIaScreen> with SingleTickerProviderStateMixin {
  late TabController _tabController;
  final TextEditingController _promptController = TextEditingController();

  bool _cargandoReporte = false;
  String? _errorReporte;
  Map<String, dynamic>? _resultadoReporte;

  bool _cargandoMl = false;
  String? _errorMl;
  Map<String, dynamic>? _dashboardMl;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
    _cargarAnaliticaMl();
  }

  @override
  void dispose() {
    _tabController.dispose();
    _promptController.dispose();
    super.dispose();
  }

  Future<void> _generarReporte([String? promptTexto]) async {
    final prompt = (promptTexto ?? _promptController.text).trim();
    if (prompt.isEmpty) return;

    setState(() {
      _cargandoReporte = true;
      _errorReporte = null;
    });

    try {
      final res = await ApiService().generarReporteIA(prompt);
      if (mounted) {
        setState(() {
          _resultadoReporte = res;
          _cargandoReporte = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _errorReporte = 'No se pudo generar el reporte: $e';
          _cargandoReporte = false;
        });
      }
    }
  }

  Future<void> _cargarAnaliticaMl() async {
    setState(() {
      _cargandoMl = true;
      _errorMl = null;
    });

    try {
      final res = await ApiService().getDashboardAnaliticaML();
      if (mounted) {
        setState(() {
          _dashboardMl = res;
          _cargandoMl = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _errorMl = 'Plan Básico o sin acceso: $e';
          _cargandoMl = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Inteligencia de Negocio'),
        bottom: TabBar(
          controller: _tabController,
          tabs: const [
            Tab(icon: Icon(Icons.auto_awesome), text: 'Reportes IA'),
            Tab(icon: Icon(Icons.analytics_outlined), text: 'Analítica ML'),
          ],
        ),
      ),
      body: TabBarView(
        controller: _tabController,
        children: [
          _vistaReportesIa(),
          _vistaAnaliticaMl(),
        ],
      ),
    );
  }

  Widget _vistaReportesIa() {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Card(
          elevation: 0,
          color: const Color(0xFFF8FAFC),
          shape: RoundedRectangleBorder(
            side: const BorderSide(color: Color(0xFFE2E8F0)),
            borderRadius: BorderRadius.circular(12),
          ),
          child: Padding(
            padding: const EdgeInsets.all(14),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Consultá en lenguaje natural',
                  style: TextStyle(fontWeight: FontWeight.bold, fontSize: 15),
                ),
                const SizedBox(height: 4),
                const Text(
                  'Escribí tu consulta ejecutiva (ventas, quiebres, prendas más vendidas o por categoría):',
                  style: TextStyle(fontSize: 12, color: Colors.black54),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: _promptController,
                  decoration: InputDecoration(
                    hintText: 'ej. ventas por sucursal de este mes',
                    hintStyle: const TextStyle(fontSize: 13),
                    isDense: true,
                    border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
                    suffixIcon: IconButton(
                      icon: const Icon(Icons.send_rounded),
                      onPressed: _cargandoReporte ? null : () => _generarReporte(),
                    ),
                  ),
                  onSubmitted: (_) => _generarReporte(),
                ),
                const SizedBox(height: 10),
                Wrap(
                  spacing: 6,
                  runSpacing: 6,
                  children: [
                    _chipSugerencia('Ventas por Sucursal', 'ventas por sucursal de este mes'),
                    _chipSugerencia('Top Prendas', 'ranking de prendas más vendidas'),
                    _chipSugerencia('Por Categoría', 'rendimiento de ventas por categoría textil'),
                    _chipSugerencia('Quiebres Stock', 'quiebres de stock críticos'),
                  ],
                ),
              ],
            ),
          ),
        ),
        if (_cargandoReporte)
          const Padding(
            padding: EdgeInsets.symmetric(vertical: 32),
            child: Center(child: CircularProgressIndicator()),
          ),
        if (_errorReporte != null)
          Container(
            margin: const EdgeInsets.only(top: 16),
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: const Color(0xFFFEF2F2),
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: const Color(0xFFFCA5A5)),
            ),
            child: Text(_errorReporte!, style: const TextStyle(color: Color(0xFF991B1B), fontSize: 13)),
          ),
        if (_resultadoReporte != null && !_cargandoReporte) ...[
          const SizedBox(height: 16),
          if (_resultadoReporte!['narrativa_ia'] != null)
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: const Color(0xFFEFF6FF),
                borderRadius: BorderRadius.circular(10),
                border: const Border(left: BorderSide(color: Color(0xFF3B82F6), width: 4)),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Row(
                    children: [
                      Icon(Icons.bolt_rounded, color: Color(0xFF1E40AF), size: 18),
                      SizedBox(width: 6),
                      Text('Análisis Ejecutivo (IA)', style: TextStyle(fontWeight: FontWeight.bold, color: Color(0xFF1E40AF))),
                    ],
                  ),
                  const SizedBox(height: 6),
                  Text(
                    _resultadoReporte!['narrativa_ia'] as String,
                    style: const TextStyle(fontSize: 13, color: Color(0xFF1E3A8A), height: 1.3),
                  ),
                ],
              ),
            ),
          const SizedBox(height: 14),
          Text(
            'Resultados: ${_resultadoReporte!['tipo']?.toString().toUpperCase()}',
            style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14),
          ),
          const SizedBox(height: 8),
          _renderizarDatosReporte(_resultadoReporte!),
        ],
      ],
    );
  }

  Widget _chipSugerencia(String label, String prompt) {
    return ActionChip(
      label: Text(label, style: const TextStyle(fontSize: 11)),
      onPressed: () {
        _promptController.text = prompt;
        _generarReporte(prompt);
      },
    );
  }

  Widget _renderizarDatosReporte(Map<String, dynamic> res) {
    final datos = res['datos'] as List<dynamic>? ?? [];
    if (datos.isEmpty) {
      return const Padding(
        padding: EdgeInsets.all(16),
        child: Center(child: Text('Sin datos en el periodo consultado.')),
      );
    }

    final tipo = res['tipo'] as String;
    return ListView.separated(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      itemCount: datos.length,
      separatorBuilder: (_, __) => const Divider(height: 1),
      itemBuilder: (context, index) {
        final item = datos[index] as Map<String, dynamic>;
        if (tipo == 'ventas') {
          return ListTile(
            dense: true,
            title: Text(item['sucursal_nombre'] ?? 'Sucursal', style: const TextStyle(fontWeight: FontWeight.bold)),
            subtitle: Text('${item['cantidad_ventas']} ventas registradas'),
            trailing: Text(formatoBs(item['total_ventas'] ?? 0), style: const TextStyle(fontWeight: FontWeight.bold, color: Color(0xFF15803D))),
          );
        } else if (tipo == 'prendas_vendidas') {
          return ListTile(
            dense: true,
            leading: CircleAvatar(
              radius: 14,
              backgroundColor: const Color(0xFFEEF2FF),
              child: Text('${index + 1}', style: const TextStyle(fontSize: 11, fontWeight: FontWeight.bold, color: Color(0xFF4338CA))),
            ),
            title: Text(item['prenda_nombre'] ?? 'Prenda', style: const TextStyle(fontWeight: FontWeight.bold)),
            subtitle: Text('${item['cantidad_vendida']} unidades comercializadas'),
            trailing: Text(formatoBs(item['total_vendido'] ?? 0), style: const TextStyle(fontWeight: FontWeight.w600)),
          );
        } else if (tipo == 'rendimiento_categorias') {
          return ListTile(
            dense: true,
            title: Text(item['categoria_nombre'] ?? 'Categoría', style: const TextStyle(fontWeight: FontWeight.bold)),
            subtitle: Text('${item['cantidad_prendas_vendidas']} prendas (${item['porcentaje_ventas']}%)'),
            trailing: Text(formatoBs(item['total_ingresos'] ?? 0), style: const TextStyle(fontWeight: FontWeight.bold, color: Color(0xFF15803D))),
          );
        } else {
          return ListTile(
            dense: true,
            title: Text(item['prenda_nombre'] ?? 'Prenda', style: const TextStyle(fontWeight: FontWeight.bold)),
            subtitle: Text('Sucursal: ${item['sucursal_nombre']}'),
            trailing: Text(
              'Disp: ${item['stock_disponible']} / Min: ${item['stock_minimo']}',
              style: const TextStyle(color: Color(0xFFDC2626), fontWeight: FontWeight.bold),
            ),
          );
        }
      },
    );
  }

  Widget _vistaAnaliticaMl() {
    if (_cargandoMl) {
      return const Center(child: CircularProgressIndicator());
    }

    if (_errorMl != null) {
      return Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.lock_outline_rounded, size: 48, color: Colors.black45),
            const SizedBox(height: 12),
            const Text(
              'Analítica con Machine Learning',
              style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
            ),
            const SizedBox(height: 6),
            const Text(
              'Esta función requiere el Plan Profesional. Actualizá tu plan desde el panel administrativo para acceder a proyección supervisada de demanda y clustering.',
              textAlign: TextAlign.center,
              style: TextStyle(fontSize: 13, color: Colors.black54),
            ),
            const SizedBox(height: 16),
            ElevatedButton(
              onPressed: _cargarAnaliticaMl,
              child: const Text('Reintentar conexión'),
            ),
          ],
        ),
      );
    }

    final ml = _dashboardMl!;
    final metricas = ml['metricas'] as Map<String, dynamic>;
    final predicciones = ml['predicciones_demanda'] as List<dynamic>? ?? [];
    final clusters = ml['segmentacion_clientes'] as List<dynamic>? ?? [];

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        // Resumen
        Container(
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: const Color(0xFFF8FAFC),
            border: const Border(left: BorderSide(color: Color(0xFF6366F1), width: 4)),
            borderRadius: BorderRadius.circular(8),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('INSIGHT EJECUTIVO ML', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 11, color: Color(0xFF4338CA))),
              const SizedBox(height: 4),
              Text(ml['resumen_ejecutivo'] as String? ?? '', style: const TextStyle(fontSize: 12, height: 1.3)),
            ],
          ),
        ),
        const SizedBox(height: 16),

        // Métricas formales
        Row(
          children: [
            Expanded(child: _tarjetaMetrica('R² Score', '${metricas['r2_score']}', 'Bondad de ajuste')),
            const SizedBox(width: 8),
            Expanded(child: _tarjetaMetrica('MAE', formatoBs(metricas['mae'] ?? 0), 'Error absoluto')),
            const SizedBox(width: 8),
            Expanded(child: _tarjetaMetrica('Silueta', '${metricas['silhouette_score']}', 'Clustering RFM')),
          ],
        ),
        const SizedBox(height: 20),

        // Predicción supervisada
        const Text('Proyección de Demanda (4 Semanas)', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 14)),
        const SizedBox(height: 8),
        Card(
          elevation: 0,
          shape: RoundedRectangleBorder(
            side: const BorderSide(color: Color(0xFFE2E8F0)),
            borderRadius: BorderRadius.circular(10),
          ),
          child: Column(
            children: predicciones.map((p) {
              return ListTile(
                dense: true,
                title: Text('${p['periodo']} • ${p['fecha']}', style: const TextStyle(fontWeight: FontWeight.bold)),
                subtitle: Text('Estimadas: ${p['unidades_estimadas']} prendas (rango: ${p['limite_inferior']} - ${p['limite_superior']} Bs.)'),
                trailing: Text(
                  formatoBs(p['ventas_proyectadas'] ?? 0),
                  style: const TextStyle(fontWeight: FontWeight.bold, color: Color(0xFF15803D)),
                ),
              );
            }).toList(),
          ),
        ),
        const SizedBox(height: 20),

        // Segmentación no supervisada
        const Text('Segmentación de Clientes (K-Means)', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 14)),
        const SizedBox(height: 8),
        ...clusters.map((c) {
          return Card(
            margin: const EdgeInsets.only(bottom: 10),
            elevation: 0,
            shape: RoundedRectangleBorder(
              side: const BorderSide(color: Color(0xFFE2E8F0)),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text(c['nombre_segmento'] ?? '', style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14)),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                        decoration: BoxDecoration(color: const Color(0xFFEEF2FF), borderRadius: BorderRadius.circular(6)),
                        child: Text('${c['porcentaje']}%', style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 11, color: Color(0xFF4338CA))),
                      ),
                    ],
                  ),
                  const SizedBox(height: 4),
                  Text(c['descripcion'] ?? '', style: const TextStyle(fontSize: 12, color: Colors.black54)),
                  const SizedBox(height: 8),
                  Text('Estrategia: ${c['estrategia_recomendada']}', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: context.marca)),
                ],
              ),
            ),
          );
        }),
      ],
    );
  }

  Widget _tarjetaMetrica(String label, String valor, String sub) {
    return Container(
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: const Color(0xFFE2E8F0)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: const TextStyle(fontSize: 11, color: Colors.black54)),
          const SizedBox(height: 2),
          Text(valor, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13, color: Color(0xFF0F172A))),
          const SizedBox(height: 2),
          Text(sub, style: const TextStyle(fontSize: 9, color: Colors.black45)),
        ],
      ),
    );
  }
}
