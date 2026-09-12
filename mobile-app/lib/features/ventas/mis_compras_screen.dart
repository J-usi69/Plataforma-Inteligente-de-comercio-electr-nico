import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../core/services/api_service.dart';

class MisComprasScreen extends StatefulWidget {
  const MisComprasScreen({super.key});

  @override
  State<MisComprasScreen> createState() => _MisComprasScreenState();
}

class _MisComprasScreenState extends State<MisComprasScreen> {
  final _apiService = ApiService();
  bool _isLoading = true;
  List<dynamic> _compras = [];

  @override
  void initState() {
    super.initState();
    _cargarCompras();
  }

  Future<void> _cargarCompras() async {
    setState(() => _isLoading = true);
    try {
      final data = await _apiService.getMisCompras();
      if (mounted) {
        setState(() => _compras = data);
      }
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Error al cargar historial de compras: $e'),
          backgroundColor: Colors.red.shade700,
        ),
      );
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  void _verComprobante(int ventaId) async {
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (ctx) => const Center(child: CircularProgressIndicator()),
    );

    try {
      final comprobante = await _apiService.getComprobanteVenta(ventaId);
      if (!mounted) return;
      Navigator.of(context).pop(); // Cierra loading

      showDialog(
        context: context,
        builder: (ctx) => Dialog(
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    const Text(
                      'COMPROBANTE OFICIAL',
                      style: TextStyle(
                        fontWeight: FontWeight.w800,
                        fontSize: 14,
                        letterSpacing: 0.5,
                        color: Color(0xFF4F46E5),
                      ),
                    ),
                    IconButton(
                      icon: const Icon(Icons.close, size: 20),
                      onPressed: () => Navigator.of(ctx).pop(),
                      padding: EdgeInsets.zero,
                      constraints: const BoxConstraints(),
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                Text(
                  comprobante['numero_comprobante'] ?? 'FAC-0000',
                  style: const TextStyle(
                    fontSize: 20,
                    fontWeight: FontWeight.bold,
                    color: Color(0xFF0F172A),
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  'Fecha: ${comprobante['fecha_emision'] ?? '-'}',
                  style: const TextStyle(fontSize: 12, color: Color(0xFF64748B)),
                ),
                const Divider(height: 24),

                // Datos cliente y sucursal
                _infoFila('Cliente', comprobante['cliente_nombre'] ?? 'Cliente'),
                _infoFila('Sucursal', comprobante['sucursal_nombre'] ?? 'Central'),
                _infoFila('Tipo Venta', comprobante['tipo_venta'] ?? 'DIGITAL'),
                _infoFila('Método Pago', comprobante['metodo_pago'] ?? 'ELECTRÓNICO'),

                const Divider(height: 24),
                const Text(
                  'DETALLE DE PRODUCTOS',
                  style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: Color(0xFF475569)),
                ),
                const SizedBox(height: 8),
                ...((comprobante['items'] as List?) ?? []).map((item) => Padding(
                  padding: const EdgeInsets.symmetric(vertical: 4),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Expanded(
                        child: Text(
                          '${item['cantidad']}x ${item['prenda_nombre']} (${item['talla']}/${item['color']})',
                          style: const TextStyle(fontSize: 13, color: Color(0xFF1E293B)),
                        ),
                      ),
                      Text(
                        'Bs. ${(item['subtotal'] as num).toStringAsFixed(2)}',
                        style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
                      ),
                    ],
                  ),
                )),

                const Divider(height: 24),
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    const Text('TOTAL CANCELADO', style: TextStyle(fontWeight: FontWeight.w800, fontSize: 16)),
                    Text(
                      'Bs. ${(comprobante['total'] as num).toStringAsFixed(2)}',
                      style: const TextStyle(
                        fontWeight: FontWeight.w800,
                        fontSize: 18,
                        color: Color(0xFF4F46E5),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 16),
                Container(
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: const Color(0xFFF1F5F9),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Text(
                    'Cód. Control: ${comprobante['codigo_control']}',
                    style: const TextStyle(fontSize: 10, fontFamily: 'monospace', color: Color(0xFF64748B)),
                    textAlign: TextAlign.center,
                  ),
                ),
                const SizedBox(height: 20),
                ElevatedButton(
                  onPressed: () => Navigator.of(ctx).pop(),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFF4F46E5),
                    foregroundColor: Colors.white,
                  ),
                  child: const Text('Cerrar'),
                ),
              ],
            ),
          ),
        ),
      );
    } catch (e) {
      if (!mounted) return;
      Navigator.of(context).pop(); // Cierra loading
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Error al cargar comprobante: $e'),
          backgroundColor: Colors.red.shade700,
        ),
      );
    }
  }

  Widget _infoFila(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 2),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: const TextStyle(fontSize: 12, color: Color(0xFF64748B))),
          Text(value, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: Color(0xFF0F172A))),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF8FAFC),
      appBar: AppBar(
        title: const Text('Historial de Compras'),
        backgroundColor: Colors.white,
        elevation: 0,
      ),
      body: RefreshIndicator(
        onRefresh: _cargarCompras,
        child: _isLoading
            ? const Center(child: CircularProgressIndicator())
            : _compras.isEmpty
                ? Center(
                    child: Padding(
                      padding: const EdgeInsets.all(32),
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Icon(Icons.receipt_long_outlined, size: 72, color: Colors.grey.shade400),
                          const SizedBox(height: 16),
                          const Text(
                            'Aún no tienes compras registradas',
                            style: TextStyle(fontSize: 17, fontWeight: FontWeight.bold, color: Color(0xFF334155)),
                          ),
                          const SizedBox(height: 8),
                          const Text(
                            'Tus compras online o presenciales en nuestras sucursales aparecerán aquí.',
                            textAlign: TextAlign.center,
                            style: TextStyle(color: Color(0xFF64748B), fontSize: 13),
                          ),
                          const SizedBox(height: 24),
                          ElevatedButton.icon(
                            onPressed: () => context.go('/catalogo'),
                            icon: const Icon(Icons.shopping_bag_outlined),
                            label: const Text('Explorar Tienda'),
                            style: ElevatedButton.styleFrom(
                              backgroundColor: const Color(0xFF4F46E5),
                              foregroundColor: Colors.white,
                            ),
                          ),
                        ],
                      ),
                    ),
                  )
                : ListView.builder(
                    padding: const EdgeInsets.all(16),
                    itemCount: _compras.length,
                    itemBuilder: (context, index) {
                      final compra = _compras[index];
                      final estado = (compra['estado'] ?? '').toString().toUpperCase();
                      final tipo = (compra['tipo_venta'] ?? '').toString().toUpperCase();
                      final total = (compra['total'] as num?)?.toDouble() ?? 0.0;
                      final detalles = (compra['detalles'] as List?) ?? [];

                      return Card(
                        elevation: 0,
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(16),
                          side: const BorderSide(color: Color(0xFFE2E8F0)),
                        ),
                        margin: const EdgeInsets.only(bottom: 14),
                        child: Padding(
                          padding: const EdgeInsets.all(16),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Row(
                                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                children: [
                                  Text(
                                    'Orden #${compra['id']}',
                                    style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16, color: Color(0xFF0F172A)),
                                  ),
                                  // Badges
                                  Row(
                                    children: [
                                      Container(
                                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                                        decoration: BoxDecoration(
                                          color: tipo == 'DIGITAL' ? const Color(0xFFEFF6FF) : const Color(0xFFFAF5FF),
                                          borderRadius: BorderRadius.circular(6),
                                        ),
                                        child: Text(
                                          tipo,
                                          style: TextStyle(
                                            fontSize: 10,
                                            fontWeight: FontWeight.bold,
                                            color: tipo == 'DIGITAL' ? const Color(0xFF2563EB) : const Color(0xFF7C3AED),
                                          ),
                                        ),
                                      ),
                                      const SizedBox(width: 6),
                                      Container(
                                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                                        decoration: BoxDecoration(
                                          color: estado == 'PAGADO' ? const Color(0xFFECFDF5) : const Color(0xFFFFFBEB),
                                          borderRadius: BorderRadius.circular(6),
                                        ),
                                        child: Text(
                                          estado,
                                          style: TextStyle(
                                            fontSize: 10,
                                            fontWeight: FontWeight.bold,
                                            color: estado == 'PAGADO' ? const Color(0xFF059669) : const Color(0xFFD97706),
                                          ),
                                        ),
                                      ),
                                    ],
                                  ),
                                ],
                              ),
                              const SizedBox(height: 8),
                              Text(
                                'Fecha: ${compra['fecha'] != null ? compra['fecha'].toString().substring(0, 16).replaceAll('T', ' ') : '-'}',
                                style: const TextStyle(fontSize: 12, color: Color(0xFF64748B)),
                              ),
                              Text(
                                'Sucursal: ${compra['sucursal_nombre'] ?? 'Sucursal'}',
                                style: const TextStyle(fontSize: 12, color: Color(0xFF64748B)),
                              ),
                              const Divider(height: 18),

                              // Items
                              ...detalles.map((d) => Padding(
                                padding: const EdgeInsets.symmetric(vertical: 2),
                                child: Row(
                                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                  children: [
                                    Expanded(
                                      child: Text(
                                        '${d['cantidad']}x ${d['prenda_nombre'] ?? 'Prenda'} (${d['talla_nombre'] ?? '-'}/${d['color_nombre'] ?? '-'})',
                                        style: const TextStyle(fontSize: 13, color: Color(0xFF334155)),
                                      ),
                                    ),
                                    Text(
                                      'Bs. ${((d['subtotal'] ?? 0) as num).toStringAsFixed(2)}',
                                      style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
                                    ),
                                  ],
                                ),
                              )),

                              const Divider(height: 18),
                              Row(
                                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                children: [
                                  Column(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    children: [
                                      const Text('Total Pagado', style: TextStyle(fontSize: 11, color: Color(0xFF64748B))),
                                      Text(
                                        'Bs. ${total.toStringAsFixed(2)}',
                                        style: const TextStyle(
                                          fontWeight: FontWeight.w800,
                                          fontSize: 18,
                                          color: Color(0xFF4F46E5),
                                        ),
                                      ),
                                    ],
                                  ),
                                  if (estado == 'PAGADO')
                                    ElevatedButton.icon(
                                      onPressed: () => _verComprobante(compra['id']),
                                      icon: const Icon(Icons.receipt, size: 16),
                                      label: const Text('Comprobante'),
                                      style: ElevatedButton.styleFrom(
                                        backgroundColor: const Color(0xFF0F172A),
                                        foregroundColor: Colors.white,
                                        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                                      ),
                                    ),
                                ],
                              ),
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

