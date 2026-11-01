import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../core/services/api_service.dart';
import '../../core/services/cart_service.dart';
import '../../core/services/push_notification_service.dart';
import '../../core/theme/logo_empresa.dart';

final _direccionValida = RegExp(r'^[a-z0-9](?:[a-z0-9-]{0,38}[a-z0-9])?$');

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _formKey = GlobalKey<FormState>();
  // Solo en desarrollo: la app que se instala no trae credenciales escritas
  final _loginController = TextEditingController(text: kDebugMode ? 'admin@fashionstore.com' : '');
  final _passwordController = TextEditingController(text: kDebugMode ? 'Admin123*' : '');
  final _apiService = ApiService();
  // SaaS: cada empresa tiene su dirección (slug); la sesión vale solo en esa empresa
  late final _tiendaController = TextEditingController(text: _apiService.tienda);

  bool _isLoading = false;
  bool _verPassword = false;
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
    final tema = Theme.of(context);
    final esquema = tema.colorScheme;
    final esPlataforma = _apiService.tienda == 'fashionstore';
    return Scaffold(
      appBar: AppBar(),
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.fromLTRB(24, 0, 24, 24),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 440),
              child: Form(
                key: _formKey,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    const Center(child: LogoEmpresa(tamano: 88)),
                    const SizedBox(height: 20),
                    Text('Iniciar sesión', textAlign: TextAlign.center, style: tema.textTheme.headlineSmall),
                    const SizedBox(height: 6),
                    Text(
                      esPlataforma ? 'Plataforma Inteligente de Moda' : 'en ${_apiService.tiendaNombre}',
                      textAlign: TextAlign.center,
                      style: tema.textTheme.bodyLarge?.copyWith(color: esquema.onSurfaceVariant),
                    ),
                    const SizedBox(height: 28),
                    if (_errorMessage != null)
                      Container(
                        padding: const EdgeInsets.all(14),
                        margin: const EdgeInsets.only(bottom: 16),
                        decoration: BoxDecoration(
                          color: esquema.errorContainer,
                          borderRadius: BorderRadius.circular(14),
                        ),
                        child: Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Icon(Icons.error_outline, color: esquema.onErrorContainer),
                            const SizedBox(width: 10),
                            Expanded(
                              child: Text(
                                _errorMessage!,
                                style: TextStyle(color: esquema.onErrorContainer, fontSize: 13.5),
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
                        helperMaxLines: 2,
                        prefixIcon: Icon(Icons.storefront_outlined),
                      ),
                      autocorrect: false,
                      textInputAction: TextInputAction.next,
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
                      ),
                      keyboardType: TextInputType.emailAddress,
                      autocorrect: false,
                      textInputAction: TextInputAction.next,
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
                      decoration: InputDecoration(
                        labelText: 'Contraseña',
                        prefixIcon: const Icon(Icons.lock_outline),
                        suffixIcon: IconButton(
                          tooltip: _verPassword ? 'Ocultar contraseña' : 'Mostrar contraseña',
                          icon: Icon(_verPassword ? Icons.visibility_off_outlined : Icons.visibility_outlined),
                          onPressed: () => setState(() => _verPassword = !_verPassword),
                        ),
                      ),
                      obscureText: !_verPassword,
                      textInputAction: TextInputAction.done,
                      onFieldSubmitted: (_) {
                        if (!_isLoading) _handleLogin();
                      },
                      validator: (val) {
                        if (val == null || val.isEmpty) {
                          return 'Ingrese su contraseña';
                        }
                        return null;
                      },
                    ),
                    const SizedBox(height: 28),
                    ElevatedButton(
                      onPressed: _isLoading ? null : _handleLogin,
                      child: _isLoading
                          ? SizedBox(
                              height: 22,
                              width: 22,
                              child: CircularProgressIndicator(strokeWidth: 2.5, color: esquema.onPrimary),
                            )
                          : const Text('Ingresar'),
                    ),
                    const SizedBox(height: 12),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Text('¿No tienes una cuenta?', style: TextStyle(color: esquema.onSurfaceVariant)),
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
        ),
      ),
    );
  }
}
