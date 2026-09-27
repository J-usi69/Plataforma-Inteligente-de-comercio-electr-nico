import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:webview_flutter/webview_flutter.dart';

import '../../core/services/api_service.dart';

// Pago con QR a través de Libélula: genera el QR de la venta, lo muestra y consulta cada pocos
// segundos si ya se pagó (el backend además recibe el aviso de Libélula).
class PagoQrLibelula extends StatefulWidget {
  final int ventaId;
  final Future<void> Function() onPagado;

  const PagoQrLibelula({super.key, required this.ventaId, required this.onPagado});

  @override
  State<PagoQrLibelula> createState() => _PagoQrLibelulaState();
}

class _PagoQrLibelulaState extends State<PagoQrLibelula> {
  static const _intervaloConsulta = Duration(seconds: 4);

  final _apiService = ApiService();
  Map<String, dynamic>? _qr;
  String? _error;
  bool _cargando = true;
  bool _simulando = false;
  bool _consultando = false;
  bool _terminado = false;
  Timer? _consultaTimer;

  @override
  void initState() {
    super.initState();
    _generar();
  }

  @override
  void dispose() {
    _consultaTimer?.cancel();
    super.dispose();
  }

  Future<void> _generar() async {
    _consultaTimer?.cancel();
    setState(() {
      _cargando = true;
      _error = null;
      _qr = null;
    });
    try {
      final qr = await _apiService.generarQrLibelula(widget.ventaId);
      if (!mounted) return;
      setState(() {
        _qr = qr;
        _cargando = false;
      });
      _consultaTimer = Timer.periodic(_intervaloConsulta, (_) => _consultarEstado());
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _cargando = false;
        _error = e.toString().replaceAll('Exception: ', '');
      });
    }
  }

  Future<void> _consultarEstado() async {
    if (_consultando || _terminado) return;
    _consultando = true;
    try {
      if (await _apiService.qrLibelulaPagado(widget.ventaId)) await _confirmarPagado();
    } catch (_) {
      // Un fallo puntual de red no corta la espera: se vuelve a consultar en el próximo intervalo
    } finally {
      _consultando = false;
    }
  }

  Future<void> _simularPago() async {
    setState(() => _simulando = true);
    try {
      await _apiService.simularPagoQrLibelula(widget.ventaId);
      await _confirmarPagado();
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _simulando = false;
        _error = e.toString().replaceAll('Exception: ', '');
      });
    }
  }

  Future<void> _confirmarPagado() async {
    if (_terminado) return;
    _terminado = true;
    _consultaTimer?.cancel();
    await widget.onPagado();
  }

  Widget _imagenQr(String url) {
    // En modo de prueba (o si el comercio no tiene QR Simple) el backend manda un data URI
    if (url.startsWith('data:')) {
      return Image.memory(base64Decode(url.split(',').last), width: 220, height: 220, fit: BoxFit.contain);
    }
    return Image.network(url, width: 220, height: 220, fit: BoxFit.contain);
  }

  @override
  Widget build(BuildContext context) {
    if (_cargando) {
      return const Padding(
        padding: EdgeInsets.all(24),
        child: Column(
          children: [
            CircularProgressIndicator(),
            SizedBox(height: 12),
            Text('Generando el QR de pago...'),
          ],
        ),
      );
    }
    if (_error != null) {
      return Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          children: [
            Text(_error!, style: TextStyle(color: Colors.red.shade700), textAlign: TextAlign.center),
            TextButton(onPressed: _generar, child: const Text('Reintentar')),
          ],
        ),
      );
    }

    final qr = _qr!;
    final modoPrueba = qr['modo_prueba'] == true;
    final urlPasarela = qr['url_pasarela'] as String?;
    return Column(
      children: [
        if (modoPrueba)
          Container(
            width: double.infinity,
            margin: const EdgeInsets.only(bottom: 12),
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            decoration: BoxDecoration(
              color: const Color(0xFFFEF3C7),
              border: Border.all(color: const Color(0xFFFCD34D)),
              borderRadius: BorderRadius.circular(8),
            ),
            child: const Text(
              'MODO DE PRUEBA · Libélula todavía no está configurada: el QR es de demostración.',
              textAlign: TextAlign.center,
              style: TextStyle(fontSize: 11.5, fontWeight: FontWeight.w700, color: Color(0xFF92400E)),
            ),
          ),
        Container(
          padding: const EdgeInsets.all(8),
          decoration: BoxDecoration(
            color: Colors.white,
            border: Border.all(color: const Color(0xFFE2E8F0)),
            borderRadius: BorderRadius.circular(12),
          ),
          child: _imagenQr(qr['qr_url'] as String),
        ),
        const SizedBox(height: 10),
        Text(
          'Escanea el QR con la app de tu banco y paga Bs. ${(qr['monto'] as num).toStringAsFixed(2)}. '
          'Si pagas desde este mismo celular, toma una captura y súbela en la app de tu banco.',
          textAlign: TextAlign.center,
          style: const TextStyle(fontSize: 12.5, color: Color(0xFF475569)),
        ),
        const SizedBox(height: 10),
        const Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            SizedBox(width: 14, height: 14, child: CircularProgressIndicator(strokeWidth: 2)),
            SizedBox(width: 8),
            Text(
              'Esperando la confirmación del pago...',
              style: TextStyle(fontSize: 12.5, color: Color(0xFF4F46E5), fontWeight: FontWeight.w600),
            ),
          ],
        ),
        if (urlPasarela != null)
          TextButton.icon(
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute(builder: (_) => _PasarelaLibelula(url: urlPasarela)),
            ),
            icon: const Icon(Icons.open_in_new, size: 18),
            label: const Text('Pagar en la pasarela de Libélula'),
          ),
        if (modoPrueba) ...[
          const SizedBox(height: 12),
          SizedBox(
            width: double.infinity,
            child: ElevatedButton.icon(
              onPressed: _simulando ? null : _simularPago,
              icon: const Icon(Icons.check),
              label: Text(_simulando ? 'Confirmando...' : 'Simular pago (modo de prueba)'),
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFF4F46E5),
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(vertical: 14),
              ),
            ),
          ),
        ],
      ],
    );
  }
}

// La pasarela de Libélula (tarjeta, Tigo Money, QR...) dentro de la app. Al terminar, Libélula
// avisa el pago al backend y la pantalla del QR lo detecta sola al volver.
class _PasarelaLibelula extends StatefulWidget {
  final String url;

  const _PasarelaLibelula({required this.url});

  @override
  State<_PasarelaLibelula> createState() => _PasarelaLibelulaState();
}

class _PasarelaLibelulaState extends State<_PasarelaLibelula> {
  late final WebViewController _controller = WebViewController()
    ..setJavaScriptMode(JavaScriptMode.unrestricted)
    ..loadRequest(Uri.parse(widget.url));

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Pasarela Libélula')),
      body: SafeArea(child: WebViewWidget(controller: _controller)),
    );
  }
}
