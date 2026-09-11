import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../core/services/api_service.dart';

class CatalogoScreen extends StatefulWidget {
  const CatalogoScreen({super.key});

  @override
  State<CatalogoScreen> createState() => _CatalogoScreenState();
}

class _CatalogoScreenState extends State<CatalogoScreen> {
  final _apiService = ApiService();
  bool _isLoading = true;
  List<dynamic> _prendas = [];
  List<dynamic> _categorias = [];
  int? _selectedCategoriaId;

  @override
  void initState() {
    super.initState();
    _cargarDatos();
  }

  Future<void> _cargarDatos() async {
    setState(() => _isLoading = true);
    try {
      final cats = await _apiService.getCategorias();
      final prendas = await _apiService.getPrendas(categoriaId: _selectedCategoriaId);
      setState(() {
        _categorias = cats;
        _prendas = prendas;
      });
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error al cargar catálogo: $e'), backgroundColor: Colors.red),
      );
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Catálogo FashionStore'),
        centerTitle: false,
        actions: [
          if (_apiService.isLoggedIn)
            IconButton(
              icon: const Icon(Icons.shopping_cart_outlined),
              tooltip: 'Carrito',
              onPressed: () => context.push('/carrito'),
            ),
          PopupMenuButton<String>(
            icon: const Icon(Icons.menu),
            tooltip: 'Menú',
            onSelected: (value) {
              switch (value) {
                case 'sucursales':
                  context.push('/sucursales');
                case 'reservas':
                  context.push('/reservas');
                case 'perfil':
                  context.push('/perfil');
                case 'login':
                  context.push('/login');
              }
            },
            itemBuilder: (context) => [
              const PopupMenuItem(
                value: 'sucursales',
                child: ListTile(
                  leading: Icon(Icons.storefront_outlined),
                  title: Text('Ver Sucursales'),
                ),
              ),
              if (_apiService.isLoggedIn)
                const PopupMenuItem(
                  value: 'reservas',
                  child: ListTile(
                    leading: Icon(Icons.event_note_outlined),
                    title: Text('Mis Reservas'),
                  ),
                ),
              if (_apiService.isLoggedIn)
                const PopupMenuItem(
                  value: 'perfil',
                  child: ListTile(
                    leading: Icon(Icons.account_circle),
                    title: Text('Mi Perfil'),
                  ),
                )
              else
                const PopupMenuItem(
                  value: 'login',
                  child: ListTile(
                    leading: Icon(Icons.login),
                    title: Text('Iniciar Sesión'),
                  ),
                ),
            ],
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _cargarDatos,
        child: Column(
          children: [
            // Categorías Chips
            if (_categorias.isNotEmpty)
              SingleChildScrollView(
                scrollDirection: Axis.horizontal,
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                child: Row(
                  children: [
                    ChoiceChip(
                      label: const Text('Todas'),
                      selected: _selectedCategoriaId == null,
                      onSelected: (selected) {
                        if (selected) {
                          setState(() => _selectedCategoriaId = null);
                          _cargarDatos();
                        }
                      },
                    ),
                    const SizedBox(width: 8),
                    ..._categorias.map((cat) {
                      final isSelected = _selectedCategoriaId == cat['id'];
                      return Padding(
                        padding: const EdgeInsets.only(right: 8),
                        child: ChoiceChip(
                          label: Text(cat['nombre']),
                          selected: isSelected,
                          onSelected: (selected) {
                            setState(() {
                              _selectedCategoriaId = selected ? cat['id'] : null;
                            });
                            _cargarDatos();
                          },
                        ),
                      );
                    }),
                  ],
                ),
              ),
            const Divider(height: 1),
            Expanded(
              child: _isLoading
                  ? const Center(child: CircularProgressIndicator())
                  : _prendas.isEmpty
                      ? const Center(child: Text('No hay prendas registradas en este momento.'))
                      : ListView.builder(
                          padding: const EdgeInsets.all(16),
                          itemCount: _prendas.length,
                          itemBuilder: (context, index) {
                            final p = _prendas[index];
                            final has3D = p['modelo_3d_url'] != null && p['modelo_3d_url'].toString().isNotEmpty;

                            return Card(
                              margin: const EdgeInsets.only(bottom: 16),
                              elevation: 2,
                              shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(12),
                              ),
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  // Placeholder imagen
                                  Container(
                                    height: 150,
                                    width: double.infinity,
                                    decoration: BoxDecoration(
                                      color: Colors.indigo.shade50,
                                      borderRadius: const BorderRadius.vertical(top: Radius.circular(12)),
                                    ),
                                    child: Stack(
                                      children: [
                                        const Center(
                                          child: Icon(Icons.checkroom, size: 64, color: Colors.indigo),
                                        ),
                                        if (has3D)
                                          Positioned(
                                            top: 10,
                                            right: 10,
                                            child: Container(
                                              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                                              decoration: BoxDecoration(
                                                color: Colors.green.shade700,
                                                borderRadius: BorderRadius.circular(8),
                                              ),
                                              child: const Row(
                                                mainAxisSize: MainAxisSize.min,
                                                children: [
                                                  Icon(Icons.view_in_ar, size: 14, color: Colors.white),
                                                  SizedBox(width: 4),
                                                  Text(
                                                    '3D RA',
                                                    style: TextStyle(
                                                      color: Colors.white,
                                                      fontSize: 11,
                                                      fontWeight: FontWeight.bold,
                                                    ),
                                                  ),
                                                ],
                                              ),
                                            ),
                                          ),
                                      ],
                                    ),
                                  ),
                                  Padding(
                                    padding: const EdgeInsets.all(14.0),
                                    child: Column(
                                      crossAxisAlignment: CrossAxisAlignment.start,
                                      children: [
                                        Text(
                                          p['categoria_nombre'] ?? 'Prenda',
                                          style: TextStyle(
                                            fontSize: 12,
                                            color: Colors.indigo.shade600,
                                            fontWeight: FontWeight.bold,
                                          ),
                                        ),
                                        const SizedBox(height: 4),
                                        Text(
                                          p['nombre'],
                                          style: const TextStyle(
                                            fontSize: 17,
                                            fontWeight: FontWeight.bold,
                                          ),
                                        ),
                                        if (p['descripcion'] != null) ...[
                                          const SizedBox(height: 4),
                                          Text(
                                            p['descripcion'],
                                            maxLines: 2,
                                            overflow: TextOverflow.ellipsis,
                                            style: const TextStyle(fontSize: 13, color: Colors.black54),
                                          ),
                                        ],
                                        const SizedBox(height: 12),
                                        Text(
                                          'Bs. ${p['precio_base']}',
                                          style: const TextStyle(
                                            fontSize: 18,
                                            fontWeight: FontWeight.w800,
                                            color: Colors.indigo,
                                          ),
                                        ),
                                        const SizedBox(height: 10),
                                        Row(
                                          mainAxisAlignment: MainAxisAlignment.end,
                                          children: [
                                            OutlinedButton.icon(
                                              onPressed: () => context.push('/vestidor-ar', extra: p),
                                              icon: const Icon(Icons.view_in_ar, size: 16),
                                              label: const Text('Probar con RA'),
                                            ),
                                            const SizedBox(width: 8),
                                            ElevatedButton.icon(
                                              onPressed: () {
                                                if (_apiService.isLoggedIn) {
                                                  context.push('/reservar', extra: p);
                                                } else {
                                                  context.push('/login');
                                                }
                                              },
                                              icon: const Icon(Icons.event_available, size: 16),
                                              label: const Text('Reservar'),
                                              style: ElevatedButton.styleFrom(
                                                backgroundColor: Colors.indigo,
                                                foregroundColor: Colors.white,
                                              ),
                                            ),
                                          ],
                                        ),
                                      ],
                                    ),
                                  ),
                                ],
                              ),
                            );
                          },
                        ),
            ),
          ],
        ),
      ),
    );
  }
}
