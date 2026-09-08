import 'dart:async';

import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import '../../core/services/api_service.dart';

class VestidorArScreen extends StatefulWidget {
  final Map<String, dynamic>? prenda;

  const VestidorArScreen({super.key, this.prenda});

  @override
  State<VestidorArScreen> createState() => _VestidorArScreenState();
}

enum _EstadoVestidor { inicial, generando, listo, error }

class _VestidorArScreenState extends State<VestidorArScreen> {
  final _apiService = ApiService();
  final _picker = ImagePicker();

  _EstadoVestidor _estado = _EstadoVestidor.inicial;
  String? _resultUrl;
  String? _mensajeError;
  Timer? _pollTimer;

  @override
  void dispose() {
    _pollTimer?.cancel();
    super.dispose();
  }

  bool get _prendaTieneImagen =>
      widget.prenda != null &&
      widget.prenda!['imagen_url'] != null &&
      widget.prenda!['imagen_url'].toString().isNotEmpty;

  Future<void> _tomarFotoYGenerar() async {
    if (widget.prenda == null) {
      setState(() {
        _estado = _EstadoVestidor.error;
        _mensajeError = 'No se seleccionó ninguna prenda del catálogo.';
      });
      return;
    }
    if (!_prendaTieneImagen) {
      setState(() {
        _estado = _EstadoVestidor.error;
        _mensajeError = 'Esta prenda todavía no tiene una foto de referencia configurada por el administrador.';
      });
      return;
    }

    final XFile? foto = await _picker.pickImage(source: ImageSource.camera, imageQuality: 90);
    if (foto == null) return;

    setState(() {
      _estado = _EstadoVestidor.generando;
      _mensajeError = null;
      _resultUrl = null;
    });

    try {
      final bytes = await foto.readAsBytes();
      final job = await _apiService.createTryOnJob(
        prendaId: widget.prenda!['id'] as int,
        personaBytes: bytes,
        personaFilename: foto.name,
      );
      _iniciarPolling(job['job_id'] as String);
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _estado = _EstadoVestidor.error;
        _mensajeError = e.toString().replaceAll('Exception: ', '');
      });
    }
  }

  void _iniciarPolling(String jobId) {
    _pollTimer?.cancel();
    _pollTimer = Timer.periodic(const Duration(seconds: 2), (timer) async {
      try {
        final job = await _apiService.getTryOnJob(jobId);
        final status = job['status'] as String?;

        if (status == 'SUCCEEDED') {
          timer.cancel();
          if (!mounted) return;
          setState(() {
            _estado = _EstadoVestidor.listo;
            _resultUrl = job['result_url'] as String?;
          });
        } else if (status == 'FAILED' || status == 'CANCELLED') {
          timer.cancel();
          if (!mounted) return;
          setState(() {
            _estado = _EstadoVestidor.error;
            _mensajeError = job['error'] as String? ?? 'La generación falló.';
          });
        }
        // QUEUED / PROCESSING: seguimos esperando
      } catch (e) {
        timer.cancel();
        if (!mounted) return;
        setState(() {
          _estado = _EstadoVestidor.error;
          _mensajeError = e.toString().replaceAll('Exception: ', '');
        });
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final nombrePrenda = widget.prenda?['nombre'] as String?;

    return Scaffold(
      appBar: AppBar(title: const Text('Vestidor virtual (CU-14)')),
      body: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            if (nombrePrenda != null)
              Text(
                'Probando: $nombrePrenda',
                style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                textAlign: TextAlign.center,
              ),
            const SizedBox(height: 20),
            Expanded(child: Center(child: _buildContenido())),
            const SizedBox(height: 16),
            if (_estado != _EstadoVestidor.generando)
              ElevatedButton.icon(
                onPressed: _tomarFotoYGenerar,
                icon: const Icon(Icons.camera_alt),
                label: Text(_estado == _EstadoVestidor.listo ? 'Probar otra foto' : 'Tomar foto y probar'),
                style: ElevatedButton.styleFrom(
                  padding: const EdgeInsets.symmetric(vertical: 14),
                  backgroundColor: Colors.indigo,
                  foregroundColor: Colors.white,
                ),
              ),
          ],
        ),
      ),
    );
  }

  Widget _buildContenido() {
    switch (_estado) {
      case _EstadoVestidor.inicial:
        return const Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.view_in_ar, size: 96, color: Colors.indigo),
            SizedBox(height: 12),
            Text(
              'Tómate una foto para ver cómo te queda esta prenda, generada con inteligencia artificial.',
              textAlign: TextAlign.center,
            ),
          ],
        );
      case _EstadoVestidor.generando:
        return const Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            CircularProgressIndicator(),
            SizedBox(height: 16),
            Text('Generando tu imagen con IA, puede tardar unos segundos...'),
          ],
        );
      case _EstadoVestidor.listo:
        return _resultUrl != null
            ? ClipRRect(
                borderRadius: BorderRadius.circular(12),
                child: Image.network(_resultUrl!, fit: BoxFit.contain),
              )
            : const Text('No se recibió una imagen de resultado.');
      case _EstadoVestidor.error:
        return Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.error_outline, size: 64, color: Colors.red),
            const SizedBox(height: 12),
            Text(
              _mensajeError ?? 'Ocurrió un error inesperado.',
              textAlign: TextAlign.center,
              style: const TextStyle(color: Colors.red),
            ),
          ],
        );
    }
  }
}
