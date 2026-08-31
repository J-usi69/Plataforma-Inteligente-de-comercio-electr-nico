import 'package:flutter/material.dart';

class ReservasScreen extends StatelessWidget {
  const ReservasScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Mis reservas')),
      body: const Center(
        child: Text('CU-15/16 Reservar y consultar reservas (pendiente)'),
      ),
    );
  }
}
