import 'dart:async';

import 'package:flutter/material.dart';

import '../../core/offline/reglas.dart';
import '../../core/offline/sincronizacion_service.dart';
import '../../core/router.dart';
import '../../core/theme/tema.dart';

/// Barra al pie de todas las pantallas: sin conexión avisa con qué datos se trabaja y, con o sin
/// red, cuántas operaciones faltan sincronizar. No hay un "modo sin conexión" aparte: las
/// pantallas siguen siendo las mismas. Abajo queda al alcance del pulgar para abrir la cola.
class ConBarraDeConexion extends StatefulWidget {
  final Widget child;
  const ConBarraDeConexion({super.key, required this.child});

  @override
  State<ConBarraDeConexion> createState() => _ConBarraDeConexionState();
}

class _ConBarraDeConexionState extends State<ConBarraDeConexion> {
  final _sync = SincronizacionService();
  StreamSubscription<String>? _avisos;

  @override
  void initState() {
    super.initState();
    // CU-13, paso 5: el resultado de cada sincronización se informa aunque se esté en otra pantalla
    _avisos = _sync.avisos.listen((texto) {
      avisosGlobales.currentState?.showSnackBar(SnackBar(
        content: Text(texto),
        action: SnackBarAction(label: 'Ver', onPressed: abrirPendientes),
      ));
    });
  }

  @override
  void dispose() {
    _avisos?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: _sync,
      builder: (context, _) {
        final visible = !_sync.enLinea || _sync.pendientes > 0 || _sync.enConflicto > 0;
        if (!visible) return widget.child;
        return Column(
          children: [
            // La barra ocupa el borde inferior: la pantalla de arriba ya no lo tiene que esquivar
            Expanded(child: MediaQuery.removePadding(context: context, removeBottom: true, child: widget.child)),
            _Barra(sync: _sync),
          ],
        );
      },
    );
  }
}

class _Barra extends StatelessWidget {
  final SincronizacionService sync;
  const _Barra({required this.sync});

  @override
  Widget build(BuildContext context) {
    final sinConexion = !sync.enLinea;
    final info = sync.info;
    final String texto;
    if (sinConexion) {
      texto = info == null
          ? 'Sin conexión: este teléfono todavía no tiene datos guardados.'
          : 'Sin conexión · datos del ${fechaCorta(info.generadoEn)}'
              '${sync.desactualizado ? ' (pueden estar desactualizados)' : ''}';
    } else if (sync.sincronizando) {
      texto = 'Enviando operaciones…';
    } else if (sync.pendientes > 0) {
      texto = '${sync.pendientes} ${sync.pendientes == 1 ? 'operación' : 'operaciones'} por enviar';
    } else {
      texto = '${sync.enConflicto} en conflicto: las revisa el administrador';
    }
    final fondo = sinConexion ? const Color(0xFF334155) : context.marca;
    final tinta = sinConexion ? Colors.white : context.sobreMarca;

    return Material(
      color: fondo,
      child: SafeArea(
        top: false,
        child: InkWell(
          onTap: abrirPendientes,
          child: ConstrainedBox(
            constraints: const BoxConstraints(minHeight: 48),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              child: Row(
                children: [
                  Icon(sinConexion ? Icons.cloud_off : Icons.sync, color: tinta, size: 20),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(texto, style: TextStyle(color: tinta, fontSize: 13)),
                  ),
                  if (sinConexion && sync.pendientes > 0)
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                      decoration: BoxDecoration(color: Colors.amber.shade600, borderRadius: BorderRadius.circular(10)),
                      child: Text(
                        '${sync.pendientes} por enviar',
                        style: const TextStyle(color: Colors.black87, fontSize: 12, fontWeight: FontWeight.w700),
                      ),
                    ),
                  Icon(Icons.chevron_right, color: tinta.withValues(alpha: 0.7)),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
