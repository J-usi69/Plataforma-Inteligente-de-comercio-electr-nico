import 'package:flutter/material.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:webview_flutter/webview_flutter.dart';
import 'package:webview_flutter_android/webview_flutter_android.dart';

import '../../core/config/env.dart';

// Vestidor AR en vivo con MediaPipe. MediaPipe no tiene soporte oficial para Flutter, así que se
// abre el mismo probador AR de la web (/probador-ar) dentro de un WebView: detección de pose y
// superposición de la prenda corren en el navegador embebido, igual que en la web.
class ProbadorArWebView extends StatefulWidget {
  final int prendaId;
  final int? varianteId;

  const ProbadorArWebView({super.key, required this.prendaId, this.varianteId});

  @override
  State<ProbadorArWebView> createState() => _ProbadorArWebViewState();
}

enum _EstadoPermiso { pidiendo, concedido, denegado }

class _ProbadorArWebViewState extends State<ProbadorArWebView> {
  WebViewController? _controller;
  _EstadoPermiso _permiso = _EstadoPermiso.pidiendo;
  int _progreso = 0;

  @override
  void initState() {
    super.initState();
    _iniciar();
  }

  Future<void> _iniciar() async {
    setState(() => _permiso = _EstadoPermiso.pidiendo);

    final estado = await Permission.camera.request();
    if (!mounted) return;
    if (!estado.isGranted) {
      setState(() => _permiso = _EstadoPermiso.denegado);
      return;
    }

    final url = Uri.parse('${Env.webUrl}/probador-ar').replace(queryParameters: {
      'prenda': '${widget.prendaId}',
      if (widget.varianteId != null) 'variante': '${widget.varianteId}',
      'embed': '1',
    });

    final controller = WebViewController(
      // La página pide la cámara con getUserMedia; se concede porque la app ya tiene el permiso.
      onPermissionRequest: (request) => request.grant(),
    )
      ..setJavaScriptMode(JavaScriptMode.unrestricted)
      ..setBackgroundColor(Colors.white)
      ..setNavigationDelegate(NavigationDelegate(
        onProgress: (progreso) {
          if (mounted) setState(() => _progreso = progreso);
        },
      ));

    final plataforma = controller.platform;
    if (plataforma is AndroidWebViewController) {
      // Sin esto Android bloquea el autoplay y el video de la cámara no arranca solo.
      await plataforma.setMediaPlaybackRequiresUserGesture(false);
    }

    await controller.loadRequest(url);
    if (!mounted) return;
    setState(() {
      _controller = controller;
      _permiso = _EstadoPermiso.concedido;
    });
  }

  @override
  Widget build(BuildContext context) {
    switch (_permiso) {
      case _EstadoPermiso.pidiendo:
        return const Center(child: CircularProgressIndicator());
      case _EstadoPermiso.denegado:
        return Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.no_photography_outlined, size: 64, color: Colors.redAccent),
              const SizedBox(height: 12),
              const Text(
                'El vestidor AR en vivo necesita permiso para usar la cámara.',
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 16),
              ElevatedButton(onPressed: openAppSettings, child: const Text('Abrir ajustes')),
              TextButton(onPressed: _iniciar, child: const Text('Reintentar')),
            ],
          ),
        );
      case _EstadoPermiso.concedido:
        return Column(
          children: [
            if (_progreso < 100) LinearProgressIndicator(value: _progreso / 100),
            Expanded(child: WebViewWidget(controller: _controller!)),
          ],
        );
    }
  }
}
