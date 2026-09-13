import 'package:flutter/material.dart';
import 'package:flutter_stripe/flutter_stripe.dart' hide Card;
import 'package:go_router/go_router.dart';
import '../../core/services/api_service.dart';
import '../../core/services/cart_service.dart';

class CarritoScreen extends StatefulWidget {
  const CarritoScreen({super.key});

  @override
  State<CarritoScreen> createState() => _CarritoScreenState();
}

class _CarritoScreenState extends State<CarritoScreen> {
  final _apiService = ApiService();
  final _cartService = CartService();

  List<dynamic> _sucursales = [];
  int _selectedSucursalId = 1;
  String _tipoEntrega = 'DOMICILIO';
  final _direccionController = TextEditingController(text: 'Av. San Martín #450, Equipetrol');
  bool _isLoadingSucursales = false;
  bool _isProcessingSale = false;

  @override
  void initState() {
    super.initState();
    _cartService.addListener(_onCartChanged);
    _cargarSucursales();
  }

  @override
  void dispose() {
    _cartService.removeListener(_onCartChanged);
    _direccionController.dispose();
    super.dispose();
  }

  void _onCartChanged() {
    if (mounted) setState(() {});
  }

  Future<void> _cargarSucursales() async {
    setState(() => _isLoadingSucursales = true);
    try {
      final data = await _apiService.getSucursales();
      if (mounted) {
        setState(() {
          _sucursales = data;
          if (data.isNotEmpty && !_sucursales.any((s) => s['id'] == _selectedSucursalId)) {
            _selectedSucursalId = data.first['id'];
          }
        });
      }
    } catch (_) {
      // Ignorar fallback
    } finally {
      if (mounted) setState(() => _isLoadingSucursales = false);
    }
  }

  void _iniciarCheckout() async {
    if (!_apiService.isLoggedIn) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: const Text('Debes iniciar sesión para completar tu compra.'),
          action: SnackBarAction(
            label: 'Ingresar',
            onPressed: () => context.push('/login'),
          ),
        ),
      );
      return;
    }

    if (_cartService.items.isEmpty) return;

    setState(() => _isProcessingSale = true);
    try {
      final detalles = _cartService.items.map((i) => {
        'variante_id': i.varianteId,
        'cantidad': i.cantidad,
      }).toList();

      final venta = await _apiService.crearVentaDigital(
        sucursalId: _selectedSucursalId,
        tipoEntrega: _tipoEntrega,
        direccionEnvio: _tipoEntrega == 'DOMICILIO' ? _direccionController.text.trim() : null,
        detalles: detalles,
      );

      final ventaId = venta['id'] as int;
      final total = (venta['total'] as num).toDouble();

      if (!mounted) return;
      _mostrarModalPago(ventaId, total);
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Error al preparar orden: $e'),
          backgroundColor: Colors.red.shade700,
        ),
      );
    } finally {
      if (mounted) setState(() => _isProcessingSale = false);
    }
  }

  void _mostrarModalPago(int ventaId, double total) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (ctx) => _ModalPagoDigital(
        ventaId: ventaId,
        total: total,
        onPagoCompletado: (comprobante) {
          Navigator.of(ctx).pop();
          _cartService.clear();
          _mostrarModalComprobante(comprobante);
        },
      ),
    );
  }

  void _mostrarModalComprobante(Map<String, dynamic> comprobante) {
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (ctx) => Dialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                width: 64,
                height: 64,
                decoration: const BoxDecoration(
                  color: Color(0xFFECFDF5),
                  shape: BoxShape.circle,
                ),
                child: const Icon(Icons.check_circle, color: Color(0xFF059669), size: 42),
              ),
              const SizedBox(height: 16),
              const Text(
                '¡Pago Procesado con Éxito!',
                style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: Color(0xFF0F172A)),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 6),
              Text(
                'Comprobante N° ${comprobante['numero_comprobante']}',
                style: const TextStyle(fontWeight: FontWeight.w700, color: Color(0xFF4F46E5), fontSize: 15),
              ),
              const SizedBox(height: 16),
              Container(
                padding: const EdgeInsets.all(14),
                decoration: BoxDecoration(
                  color: const Color(0xFFF8FAFC),
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: const Color(0xFFE2E8F0)),
                ),
                child: Column(
                  children: [
                    _resumenFila('Cliente', comprobante['cliente_nombre'] ?? 'Cliente'),
                    _resumenFila('Sucursal', comprobante['sucursal_nombre'] ?? 'Central'),
                    _resumenFila('Tipo de Venta', comprobante['tipo_origen'] ?? 'DIGITAL'),
                    _resumenFila('Método de Pago', comprobante['metodo_pago'] ?? 'ELECTRÓNICO'),
                    const Divider(height: 16),
                    _resumenFila('Total Cancelado', 'Bs. ${(comprobante['total'] as num).toStringAsFixed(2)}', bold: true),
                  ],
                ),
              ),
              const SizedBox(height: 16),
              Text(
                'Código de Autorización: ${comprobante['transaccion_id'] ?? comprobante['numero_comprobante']}',
                style: const TextStyle(fontSize: 11, color: Color(0xFF94A3B8), fontFamily: 'monospace'),
              ),
              const SizedBox(height: 24),
              Row(
                children: [
                  Expanded(
                    child: OutlinedButton(
                      onPressed: () {
                        Navigator.of(ctx).pop();
                        context.go('/catalogo');
                      },
                      child: const Text('Catálogo'),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: ElevatedButton(
                      onPressed: () {
                        Navigator.of(ctx).pop();
                        context.push('/mis-compras');
                      },
                      style: ElevatedButton.styleFrom(
                        backgroundColor: const Color(0xFF4F46E5),
                        foregroundColor: Colors.white,
                      ),
                      child: const Text('Mis Compras'),
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _resumenFila(String etiqueta, String valor, {bool bold = false}) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 3),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(
            etiqueta,
            style: TextStyle(
              fontSize: 13,
              color: bold ? const Color(0xFF0F172A) : const Color(0xFF64748B),
              fontWeight: bold ? FontWeight.bold : FontWeight.normal,
            ),
          ),
          Text(
            valor,
            style: TextStyle(
              fontSize: 13,
              fontWeight: bold ? FontWeight.bold : FontWeight.w600,
              color: bold ? const Color(0xFF0F172A) : const Color(0xFF1E293B),
            ),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final items = _cartService.items;

    return Scaffold(
      backgroundColor: const Color(0xFFF8FAFC),
      appBar: AppBar(
        title: const Text('Bolsa de Compras'),
        backgroundColor: Colors.white,
        elevation: 0,
        actions: [
          if (items.isNotEmpty)
            IconButton(
              icon: const Icon(Icons.delete_sweep_outlined, color: Colors.red),
              tooltip: 'Vaciar bolsa',
              onPressed: () => _cartService.clear(),
            ),
        ],
      ),
      body: items.isEmpty
          ? Center(
              child: Padding(
                padding: const EdgeInsets.all(32),
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Icon(Icons.shopping_bag_outlined, size: 80, color: Colors.grey.shade400),
                    const SizedBox(height: 16),
                    const Text(
                      'Tu bolsa de compras está vacía',
                      style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: Color(0xFF334155)),
                    ),
                    const SizedBox(height: 8),
                    const Text(
                      'Explora nuestras colecciones exclusivas y añade tus prendas favoritas.',
                      textAlign: TextAlign.center,
                      style: TextStyle(color: Color(0xFF64748B)),
                    ),
                    const SizedBox(height: 24),
                    ElevatedButton.icon(
                      onPressed: () => context.go('/catalogo'),
                      icon: const Icon(Icons.arrow_back),
                      label: const Text('Explorar Catálogo'),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: const Color(0xFF4F46E5),
                        foregroundColor: Colors.white,
                        padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
                      ),
                    ),
                  ],
                ),
              ),
            )
          : ListView(
              padding: const EdgeInsets.all(16),
              children: [
                // Lista de Items
                ...items.map((item) => Card(
                  elevation: 0,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(14),
                    side: const BorderSide(color: Color(0xFFE2E8F0)),
                  ),
                  margin: const EdgeInsets.only(bottom: 12),
                  child: Padding(
                    padding: const EdgeInsets.all(12),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.center,
                      children: [
                        ClipRRect(
                          borderRadius: BorderRadius.circular(10),
                          child: Container(
                            width: 68,
                            height: 68,
                            color: const Color(0xFFEEF2FF),
                            child: item.imagenUrl != null && item.imagenUrl!.isNotEmpty
                                ? Image.network(
                                    item.imagenUrl!,
                                    fit: BoxFit.cover,
                                    errorBuilder: (_, __, ___) => const Icon(Icons.checkroom, color: Color(0xFF4F46E5)),
                                  )
                                : const Icon(Icons.checkroom, color: Color(0xFF4F46E5), size: 32),
                          ),
                        ),
                        const SizedBox(width: 14),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                item.nombre,
                                style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15),
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                              ),
                              const SizedBox(height: 2),
                              Text(
                                'Talla: ${item.talla}  ·  Color: ${item.color}',
                                style: const TextStyle(fontSize: 12, color: Color(0xFF64748B)),
                              ),
                              const SizedBox(height: 6),
                              Text(
                                'Bs. ${(item.precio * item.cantidad).toStringAsFixed(2)}',
                                style: const TextStyle(
                                  fontWeight: FontWeight.w800,
                                  color: Color(0xFF4F46E5),
                                  fontSize: 14,
                                ),
                              ),
                            ],
                          ),
                        ),
                        // Controles de cantidad
                        Row(
                          children: [
                            IconButton(
                              icon: const Icon(Icons.remove_circle_outline, size: 20),
                              onPressed: () => _cartService.updateQuantity(item.varianteId, item.cantidad - 1),
                              color: const Color(0xFF64748B),
                            ),
                            Text(
                              '${item.cantidad}',
                              style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14),
                            ),
                            IconButton(
                              icon: const Icon(Icons.add_circle_outline, size: 20),
                              onPressed: () => _cartService.updateQuantity(item.varianteId, item.cantidad + 1),
                              color: const Color(0xFF4F46E5),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                )),

                const SizedBox(height: 12),

                // Opciones de Entrega y Sucursal
                Card(
                  elevation: 0,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(14),
                    side: const BorderSide(color: Color(0xFFE2E8F0)),
                  ),
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          'Detalles de Entrega',
                          style: TextStyle(fontWeight: FontWeight.bold, fontSize: 15, color: Color(0xFF0F172A)),
                        ),
                        const SizedBox(height: 12),
                        Row(
                          children: [
                            Expanded(
                              child: ChoiceChip(
                                label: const Text('Envío a Domicilio'),
                                selected: _tipoEntrega == 'DOMICILIO',
                                onSelected: (sel) {
                                  if (sel) setState(() => _tipoEntrega = 'DOMICILIO');
                                },
                              ),
                            ),
                            const SizedBox(width: 8),
                            Expanded(
                              child: ChoiceChip(
                                label: const Text('Retiro en Tienda'),
                                selected: _tipoEntrega == 'SUCURSAL',
                                onSelected: (sel) {
                                  if (sel) setState(() => _tipoEntrega = 'SUCURSAL');
                                },
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 14),
                        // Sucursal
                        const Text('Sucursal para preparación de pedido:', style: TextStyle(fontSize: 12, color: Color(0xFF64748B))),
                        const SizedBox(height: 6),
                        if (_isLoadingSucursales)
                          const LinearProgressIndicator()
                        else
                          DropdownButtonFormField<int>(
                            value: _selectedSucursalId,
                            decoration: InputDecoration(
                              contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                              border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                            ),
                            items: _sucursales.map<DropdownMenuItem<int>>((s) {
                              return DropdownMenuItem<int>(
                                value: s['id'] as int,
                                child: Text('${s['nombre']} (${s['ciudad_nombre'] ?? 'Bolivia'})'),
                              );
                            }).toList(),
                            onChanged: (val) {
                              if (val != null) setState(() => _selectedSucursalId = val);
                            },
                          ),

                        if (_tipoEntrega == 'DOMICILIO') ...[
                          const SizedBox(height: 14),
                          const Text('Dirección de Envío:', style: TextStyle(fontSize: 12, color: Color(0xFF64748B))),
                          const SizedBox(height: 6),
                          TextField(
                            controller: _direccionController,
                            decoration: InputDecoration(
                              prefixIcon: const Icon(Icons.location_on_outlined),
                              hintText: 'Ej. Calle Las Palmas #123, Santa Cruz',
                              contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                              border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                            ),
                          ),
                        ],
                      ],
                    ),
                  ),
                ),

                const SizedBox(height: 12),

                // Resumen Financiero
                Card(
                  elevation: 0,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(14),
                    side: const BorderSide(color: Color(0xFFE2E8F0)),
                  ),
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      children: [
                        _resumenFila('Subtotal (${_cartService.totalCount} prendas)', 'Bs. ${_cartService.totalAmount.toStringAsFixed(2)}'),
                        _resumenFila('Costo de envío', 'Gratis', bold: false),
                        const Divider(height: 16),
                        _resumenFila('Total a Pagar', 'Bs. ${_cartService.totalAmount.toStringAsFixed(2)}', bold: true),
                      ],
                    ),
                  ),
                ),

                const SizedBox(height: 20),

                // Botón de Pago
                ElevatedButton(
                  onPressed: _isProcessingSale ? null : _iniciarCheckout,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFF4F46E5),
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(vertical: 16),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                    elevation: 2,
                  ),
                  child: _isProcessingSale
                      ? const SizedBox(
                          height: 20,
                          width: 20,
                          child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2),
                        )
                      : Text(
                          'CONTINUAR AL PAGO DIGITAL (Bs. ${_cartService.totalAmount.toStringAsFixed(2)})',
                          style: const TextStyle(fontSize: 15, fontWeight: FontWeight.bold),
                        ),
                ),
                const SizedBox(height: 32),
              ],
            ),
    );
  }
}

class _ModalPagoDigital extends StatefulWidget {
  final int ventaId;
  final double total;
  final Function(Map<String, dynamic> comprobante) onPagoCompletado;

  const _ModalPagoDigital({
    required this.ventaId,
    required this.total,
    required this.onPagoCompletado,
  });

  @override
  State<_ModalPagoDigital> createState() => _ModalPagoDigitalState();
}

class _ModalPagoDigitalState extends State<_ModalPagoDigital> with SingleTickerProviderStateMixin {
  late TabController _tabController;
  final _apiService = ApiService();
  bool _isPaying = false;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  // Pago QR/Libélula: Stripe no maneja QR interoperable boliviano, se mantiene simulado.
  Future<void> _procesarPagoQr() async {
    setState(() => _isPaying = true);
    try {
      await _apiService.pagarVentaDigital(
        ventaId: widget.ventaId,
        metodoPago: 'qr',
        pasarela: 'Libélula QR Interoperable',
      );
      await _finalizarPago();
    } catch (e) {
      _mostrarError('Error al procesar pago: $e');
    } finally {
      if (mounted) setState(() => _isPaying = false);
    }
  }

  // Pago con tarjeta: crea el PaymentIntent en el backend, lo confirma con Stripe
  // usando los datos que el usuario cargó en el CardField (nunca pasan por nuestro
  // servidor), y solo si Stripe confirma se le notifica al backend.
  Future<void> _procesarPagoTarjeta() async {
    setState(() => _isPaying = true);
    try {
      final clientSecret = await _apiService.crearIntentoPagoStripe(widget.ventaId);

      final paymentIntent = await Stripe.instance.confirmPayment(
        paymentIntentClientSecret: clientSecret,
        data: const PaymentMethodParams.card(paymentMethodData: PaymentMethodData()),
      );

      if (paymentIntent.status != PaymentIntentsStatus.Succeeded) {
        _mostrarError('El pago no se pudo completar (estado: ${paymentIntent.status}).');
        return;
      }

      await _apiService.pagarVentaDigital(
        ventaId: widget.ventaId,
        metodoPago: 'tarjeta',
        stripePaymentIntentId: paymentIntent.id,
      );
      await _finalizarPago();
    } on StripeException catch (e) {
      _mostrarError(e.error.localizedMessage ?? 'La tarjeta fue rechazada.');
    } catch (e) {
      _mostrarError('Error al procesar pago: $e');
    } finally {
      if (mounted) setState(() => _isPaying = false);
    }
  }

  Future<void> _finalizarPago() async {
    final comprobante = await _apiService.getComprobanteVenta(widget.ventaId);
    widget.onPagoCompletado(comprobante);
  }

  void _mostrarError(String mensaje) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(mensaje), backgroundColor: Colors.red.shade700),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: const BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      padding: EdgeInsets.only(
        top: 20,
        left: 20,
        right: 20,
        bottom: MediaQuery.of(context).viewInsets.bottom + 24,
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 40,
            height: 4,
            decoration: BoxDecoration(
              color: Colors.grey.shade300,
              borderRadius: BorderRadius.circular(2),
            ),
          ),
          const SizedBox(height: 16),
          const Text(
            'Pasarela de Pago Electrónico',
            style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: Color(0xFF0F172A)),
          ),
          const SizedBox(height: 4),
          Text(
            'Total a cancelar: Bs. ${widget.total.toStringAsFixed(2)}',
            style: const TextStyle(color: Color(0xFF4F46E5), fontWeight: FontWeight.w700, fontSize: 16),
          ),
          const SizedBox(height: 16),
          TabBar(
            controller: _tabController,
            labelColor: const Color(0xFF4F46E5),
            unselectedLabelColor: const Color(0xFF64748B),
            indicatorColor: const Color(0xFF4F46E5),
            tabs: const [
              Tab(icon: Icon(Icons.qr_code_2), text: 'Pago QR Libélula'),
              Tab(icon: Icon(Icons.credit_card), text: 'Tarjeta Débito/Crédito'),
            ],
          ),
          const SizedBox(height: 16),
          SizedBox(
            height: 320,
            child: TabBarView(
              controller: _tabController,
              children: [
                // Vista QR
                Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Container(
                      padding: const EdgeInsets.all(16),
                      decoration: BoxDecoration(
                        color: Colors.white,
                        borderRadius: BorderRadius.circular(16),
                        border: Border.all(color: const Color(0xFFE2E8F0)),
                        boxShadow: [
                          BoxShadow(
                            color: Colors.black.withOpacity(0.05),
                            blurRadius: 10,
                            offset: const Offset(0, 4),
                          ),
                        ],
                      ),
                      child: Column(
                        children: [
                          Container(
                            width: 160,
                            height: 160,
                            decoration: BoxDecoration(
                              color: const Color(0xFF0F172A),
                              borderRadius: BorderRadius.circular(12),
                            ),
                            child: const Center(
                              child: Icon(Icons.qr_code_scanner, color: Colors.white, size: 100),
                            ),
                          ),
                          const SizedBox(height: 8),
                          const Text(
                            'QR Simple & Libélula Pay',
                            style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: Color(0xFF4F46E5)),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 16),
                    const Text(
                      'Escanea desde cualquier app bancaria de Bolivia.',
                      style: TextStyle(fontSize: 12, color: Color(0xFF64748B)),
                    ),
                    const SizedBox(height: 16),
                    SizedBox(
                      width: double.infinity,
                      child: ElevatedButton.icon(
                        onPressed: _isPaying ? null : _procesarPagoQr,
                        icon: const Icon(Icons.check),
                        label: _isPaying
                            ? const SizedBox(
                                height: 18,
                                width: 18,
                                child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2),
                              )
                            : const Text('CONFIRMAR PAGO QR'),
                        style: ElevatedButton.styleFrom(
                          backgroundColor: const Color(0xFF059669),
                          foregroundColor: Colors.white,
                          padding: const EdgeInsets.symmetric(vertical: 14),
                        ),
                      ),
                    ),
                  ],
                ),

                // Vista Tarjeta: CardField de Stripe, procesa el número en un
                // componente nativo aislado que nunca pasa por nuestro código.
                SingleChildScrollView(
                  child: Column(
                    children: [
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8),
                        decoration: BoxDecoration(
                          border: Border.all(color: const Color(0xFFCBD5E1)),
                          borderRadius: BorderRadius.circular(10),
                        ),
                        child: CardField(
                          onCardChanged: (_) {},
                        ),
                      ),
                      const SizedBox(height: 8),
                      const Text(
                        'Procesado de forma segura por Stripe.',
                        style: TextStyle(fontSize: 11, color: Color(0xFF94A3B8)),
                      ),
                      const SizedBox(height: 18),
                      SizedBox(
                        width: double.infinity,
                        child: ElevatedButton(
                          onPressed: _isPaying ? null : _procesarPagoTarjeta,
                          style: ElevatedButton.styleFrom(
                            backgroundColor: const Color(0xFF4F46E5),
                            foregroundColor: Colors.white,
                            padding: const EdgeInsets.symmetric(vertical: 14),
                          ),
                          child: _isPaying
                              ? const SizedBox(
                                  height: 18,
                                  width: 18,
                                  child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2),
                                )
                              : Text('PAGAR BS. ${widget.total.toStringAsFixed(2)}'),
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
