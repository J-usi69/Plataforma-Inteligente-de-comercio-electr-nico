import 'package:flutter/material.dart';

import '../services/api_service.dart';
import 'tema.dart';

/// Logo de la empresa con la que trabaja la app: el que cargó en la plataforma; FashionStore,
/// el de la plataforma; otra empresa sin logo, sus iniciales con su color.
class LogoEmpresa extends StatelessWidget {
  final double tamano;

  const LogoEmpresa({super.key, this.tamano = 40});

  static const _logoPlataforma = 'assets/marca/logo.png';

  @override
  Widget build(BuildContext context) {
    final api = ApiService();
    return ValueListenableBuilder<Map<String, dynamic>?>(
      valueListenable: api.marca,
      builder: (context, marca, _) {
        final url = marca?['logo_url'] as String?;
        final Widget logo;
        if (url != null && url.isNotEmpty) {
          logo = Image.network(
            url,
            width: tamano,
            height: tamano,
            fit: BoxFit.cover,
            // Sin conexión el logo de la empresa no se descarga: quedan sus iniciales
            errorBuilder: (context, _, _) => _Iniciales(nombre: api.tiendaNombre, tamano: tamano),
          );
        } else if (api.tienda == 'fashionstore') {
          logo = Image.asset(_logoPlataforma, width: tamano, height: tamano);
        } else {
          logo = _Iniciales(nombre: api.tiendaNombre, tamano: tamano);
        }
        return Semantics(
          label: 'Logo de ${api.tiendaNombre}',
          image: true,
          child: ClipRRect(borderRadius: BorderRadius.circular(tamano * 0.24), child: logo),
        );
      },
    );
  }
}

class _Iniciales extends StatelessWidget {
  final String nombre;
  final double tamano;

  const _Iniciales({required this.nombre, required this.tamano});

  @override
  Widget build(BuildContext context) {
    final palabras = nombre.trim().split(RegExp(r'\s+')).where((p) => p.isNotEmpty);
    final iniciales = palabras.take(2).map((p) => p[0].toUpperCase()).join();
    final marca = context.marca;
    return Container(
      width: tamano,
      height: tamano,
      alignment: Alignment.center,
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [marca, Color.lerp(marca, Colors.black, 0.25)!],
        ),
      ),
      child: Text(
        iniciales.isEmpty ? '?' : iniciales,
        style: TextStyle(
          color: context.sobreMarca,
          fontSize: tamano * 0.38,
          fontWeight: FontWeight.w800,
          letterSpacing: -0.5,
        ),
      ),
    );
  }
}
