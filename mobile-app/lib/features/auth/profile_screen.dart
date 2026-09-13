import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../core/services/api_service.dart';

class ProfileScreen extends StatefulWidget {
  const ProfileScreen({super.key});

  @override
  State<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends State<ProfileScreen> {
  final _apiService = ApiService();
  bool _isLoading = true;
  Map<String, dynamic>? _user;

  @override
  void initState() {
    super.initState();
    _loadProfile();
  }

  Future<void> _loadProfile() async {
    setState(() => _isLoading = true);
    try {
      final data = await _apiService.getProfile();
      setState(() => _user = data);
    } catch (_) {
      setState(() => _user = _apiService.currentUser);
    } finally {
      setState(() => _isLoading = false);
    }
  }

  Future<void> _handleLogout() async {
    await _apiService.logout();
    if (!mounted) return;
    context.go('/login');
  }

  @override
  Widget build(BuildContext context) {
    final user = _user ?? _apiService.currentUser;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Mi Perfil'),
        actions: [
          IconButton(
            icon: const Icon(Icons.logout),
            onPressed: _handleLogout,
            tooltip: 'Cerrar Sesión',
          ),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : user == null
              ? Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      const Text('No has iniciado sesión.'),
                      const SizedBox(height: 12),
                      ElevatedButton(
                        onPressed: () => context.go('/login'),
                        child: const Text('Iniciar Sesión'),
                      ),
                    ],
                  ),
                )
              : ListView(
                  padding: const EdgeInsets.all(20),
                  children: [
                    Center(
                      child: CircleAvatar(
                        radius: 44,
                        backgroundColor: Colors.indigo.shade100,
                        child: const Icon(Icons.person, size: 48, color: Colors.indigo),
                      ),
                    ),
                    const SizedBox(height: 16),
                    Text(
                      user['correo'] ?? 'Usuario',
                      textAlign: TextAlign.center,
                      style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      'Roles: ${(user['roles'] as List?)?.join(', ') ?? 'Cliente'}',
                      textAlign: TextAlign.center,
                      style: const TextStyle(color: Colors.indigo, fontWeight: FontWeight.w600),
                    ),
                    const SizedBox(height: 24),
                    const Divider(),
                    ListTile(
                      leading: const Icon(Icons.email_outlined),
                      title: const Text('Correo Electrónico'),
                      subtitle: Text(user['correo'] ?? '-'),
                    ),
                    ListTile(
                      leading: const Icon(Icons.phone_outlined),
                      title: const Text('Celular'),
                      subtitle: Text(user['celular'] ?? 'No especificado'),
                    ),
                    ListTile(
                      leading: const Icon(Icons.verified_user_outlined),
                      title: const Text('Estado de Cuenta'),
                      subtitle: Text(user['estado'] == true ? 'Activo' : 'Inactivo'),
                      trailing: const Icon(Icons.check_circle, color: Colors.green),
                    ),
                    const Divider(height: 32),
                    ListTile(
                      leading: const Icon(Icons.receipt_long_outlined, color: Color(0xFF4F46E5)),
                      title: const Text('Mis Compras Realizadas', style: TextStyle(fontWeight: FontWeight.w600)),
                      subtitle: const Text('Ver comprobantes, tickets y facturas digitales'),
                      trailing: const Icon(Icons.chevron_right),
                      onTap: () => context.push('/mis-compras'),
                    ),
                    ListTile(
                      leading: const Icon(Icons.event_note_outlined, color: Color(0xFF4F46E5)),
                      title: const Text('Mis Reservas en Tienda', style: TextStyle(fontWeight: FontWeight.w600)),
                      subtitle: const Text('Consultar prendas apartadas en sucursales'),
                      trailing: const Icon(Icons.chevron_right),
                      onTap: () => context.push('/reservas'),
                    ),
                    ListTile(
                      leading: const Icon(Icons.shopping_bag_outlined, color: Color(0xFF4F46E5)),
                      title: const Text('Bolsa de Compras', style: TextStyle(fontWeight: FontWeight.w600)),
                      subtitle: const Text('Ver artículos pendientes de compra'),
                      trailing: const Icon(Icons.chevron_right),
                      onTap: () => context.push('/carrito'),
                    ),
                    const SizedBox(height: 24),
                    ElevatedButton.icon(
                      onPressed: _handleLogout,
                      icon: const Icon(Icons.logout),
                      label: const Text('CERRAR SESIÓN'),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: Colors.red.shade600,
                        foregroundColor: Colors.white,
                        padding: const EdgeInsets.symmetric(vertical: 12),
                      ),
                    ),
                  ],
                ),
    );
  }
}

