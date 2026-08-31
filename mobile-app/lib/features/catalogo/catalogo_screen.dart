import 'package:flutter/material.dart';

class CatalogoScreen extends StatelessWidget {
  const CatalogoScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Catalogo')),
      body: const Center(
        child: Text('CU-12 Consultar catalogo de prendas (pendiente)'),
      ),
    );
  }
}
