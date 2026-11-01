import 'dart:async';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../core/services/api_service.dart';
import '../../core/services/cart_service.dart';
import '../../core/services/push_notification_service.dart';

final _direccionValida = RegExp(r'^[a-z0-9](?:[a-z0-9-]{0,38}[a-z0-9])?$');

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _formKey = GlobalKey<FormState>();
  final _loginController = TextEditingController(text: 'admin@fashionstore.com');
  final _passwordController = TextEditingController(text: 'Admin123*');
  final _apiService = ApiService();
  // SaaS: cada empresa tiene su dirección (slug); la sesión vale solo en esa empresa
  late final _tiendaController = TextEditingController(text: _apiService.tienda);

  bool _isLoading = false;
  String? _errorMessage;

  @override
  void dispose() {
    _loginController.dispose();
    _passwordController.dispose();
    _tiendaController.dispose();
    super.dispose();
  }

  String _mensajeDeError(Object e, String empresa) {
    if (sinConexion(e) || e is SinConexion) {
      return 'Sin conexión: para iniciar sesión necesitás Internet. Si ya habías entrado en este teléfono, '
          'la app recuerda la sesión y funciona con los datos guardados.';
    }
    if (e is ApiException && e.status == 404) return 'No existe una empresa con la dirección "$empresa".';
    return e.toString().replaceAll('Exception: ', '');
  }

  Future<void> _handleLogin() async {
    if (!_formKey.currentState!.validate()) return;

    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    final empresa = _tiendaController.text.trim().toLowerCase();
    try {
      final cambioDeEmpresa = empresa != _apiService.tienda;
      if (cambioDeEmpresa) await _apiService.cambiarTienda(empresa);
      final res = await _apiService.login(
        login: _loginController.text.trim(),
        password: _passwordController.text,
      );
      unawaited(PushNotificationService().registrarTokenSiCorresponde());
      if (cambioDeEmpresa) {
        // La bolsa y el catálogo eran de la otra empresa
        CartService().clear();
        if (!mounted) return;
        context.go('/catalogo');
        return;
      }

      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Bienvenido ${res['usuario']['correo']}'),
          backgroundColor: Colors.green,
        ),
      );
      // Si el login se abrió empujado desde otra pantalla (ej. el carrito
      // pidiendo iniciar sesión antes de pagar), volvemos a ella con "true"
      // para que esa pantalla pueda continuar su flujo automáticamente.
      if (context.canPop()) {
        context.pop(true);
      } else {
        context.go('/catalogo');
      }
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _errorMessage = _mensajeDeError(e, empresa);
      });
    } finally {
      if (mounted) {
        setState(() {
          _isLoading = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Iniciar Sesión'),
        centerTitle: true,
      ),
      body: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.symmetric(horizontal: 24.0, vertical: 16.0),
          child: Form(
            key: _formKey,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const Icon(
                  Icons.shopping_bag_outlined,
                  size: 72,
                  color: Colors.indigo,
                ),
                const SizedBox(height: 12),
                Text(
                  _apiService.tiendaNombre,
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    fontSize: 26,
                    fontWeight: FontWeight.bold,
                    color: Colors.indigo,
                  ),
                ),
                const Text(
                  'Plataforma Inteligente de Moda',
                  textAlign: TextAlign.center,
                  style: TextStyle(fontSize: 14, color: Colors.black54),
                ),
                const SizedBox(height: 32),
                if (_errorMessage != null)
                  Container(
                    padding: const EdgeInsets.all(12),
                    margin: const EdgeInsets.only(bottom: 16),
                    decoration: BoxDecoration(
                      color: Colors.red.shade50,
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: Colors.red.shade200),
                    ),
                    child: Row(
                      children: [
                        const Icon(Icons.error_outline, color: Colors.red),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            _errorMessage!,
                            style: const TextStyle(color: Colors.red, fontSize: 13),
                          ),
                        ),
                      ],
                    ),
                  ),
                TextFormField(
                  controller: _tiendaController,
                  decoration: const InputDecoration(
                    labelText: 'Empresa',
                    helperText: 'Dirección de la empresa en FashionStore, p. ej. moda-andina',
                    prefixIcon: Icon(Icons.storefront_outlined),
                    border: OutlineInputBorder(),
                  ),
                  autocorrect: false,
                  validator: (val) {
                    final valor = (val ?? '').trim().toLowerCase();
                    if (!_direccionValida.hasMatch(valor)) {
                      return 'Solo minúsculas, números y guiones (p. ej. moda-andina)';
                    }
                    return null;
                  },
                ),
                const SizedBox(height: 16),
                TextFormField(
                  controller: _loginController,
                  decoration: const InputDecoration(
                    labelText: 'Correo electrónico o celular',
                    prefixIcon: Icon(Icons.person_outline),
                    border: OutlineInputBorder(),
                  ),
                  keyboardType: TextInputType.emailAddress,
                  validator: (val) {
                    if (val == null || val.trim().isEmpty) {
                      return 'Ingrese su correo o celular';
                    }
                    return null;
                  },
                ),
                const SizedBox(height: 16),
                TextFormField(
                  controller: _passwordController,
                  decoration: const InputDecoration(
                    labelText: 'Contraseña',
                    prefixIcon: Icon(Icons.lock_outline),
                    border: OutlineInputBorder(),
                  ),
                  obscureText: true,
                  validator: (val) {
                    if (val == null || val.isEmpty) {
                      return 'Ingrese su contraseña';
                    }
                    return null;
                  },
                ),
                const SizedBox(height: 24),
                ElevatedButton(
                  onPressed: _isLoading ? null : _handleLogin,
                  style: ElevatedButton.styleFrom(
                    padding: const EdgeInsets.symmetric(vertical: 14),
                    backgroundColor: Colors.indigo,
                    foregroundColor: Colors.white,
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(8),
                    ),
                  ),
                  child: _isLoading
                      ? const SizedBox(
                          height: 20,
                          width: 20,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            color: Colors.white,
                          ),
                        )
                      : const Text(
                          'INGRESAR',
                          style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                        ),
                ),
                const SizedBox(height: 16),
                Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    const Text('¿No tienes una cuenta?'),
                    TextButton(
                      onPressed: () => context.push('/register'),
                      child: const Text('Regístrate aquí'),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
