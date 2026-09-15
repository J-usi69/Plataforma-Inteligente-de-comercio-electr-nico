import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../core/router.dart';
import '../../core/services/api_service.dart';
import '../../core/services/cart_service.dart';

class CatalogoScreen extends StatefulWidget {
  const CatalogoScreen({super.key});

  @override
  State<CatalogoScreen> createState() => _CatalogoScreenState();
}

class _CatalogoScreenState extends State<CatalogoScreen> with RouteAware {
  final _apiService = ApiService();
  final _cartService = CartService();
  bool _isLoading = true;
  List<dynamic> _prendas = [];
  List<dynamic> _categorias = [];
  int? _selectedCategoriaId;
  List<dynamic> _recomendaciones = [];

  @override
  void initState() {
    super.initState();
    _cartService.addListener(_onCartChanged);
    _cargarDatos();
    _cargarRecomendaciones();
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    routeObserver.subscribe(this, ModalRoute.of(context) as PageRoute);
  }

  @override
  void dispose() {
    routeObserver.unsubscribe(this);
    _cartService.removeListener(_onCartChanged);
    super.dispose();
  }

  // Se llama cuando una ruta apilada encima de esta (ej. /login) se cierra y
  // este catálogo vuelve a quedar visible: refresca lo que depende de sesión
  // sin que el usuario tenga que hacer pull-to-refresh a mano.
  @override
  void didPopNext() {
    setState(() {});
    _cargarRecomendaciones();
  }

  void _onCartChanged() {
    if (mounted) setState(() {});
  }

  Future<void> _cargarDatos() async {
    setState(() => _isLoading = true);
    try {
      final cats = await _apiService.getCategorias();
      final prendas = await _apiService.getPrendas(
        categoriaId: _selectedCategoriaId,
      );
      setState(() {
        _categorias = cats;
        _prendas = prendas;
      });
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Error al cargar catálogo: $e'),
          backgroundColor: Colors.red,
        ),
      );
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  // CU-28: recomendaciones de IA; se ignora en silencio si falla o no hay sesión,
  // igual que en la versión web, para no interrumpir la navegación del catálogo.
  Future<void> _cargarRecomendaciones() async {
    if (!_apiService.isLoggedIn) return;
    try {
      final res = await _apiService.getRecomendaciones();
      final prendas = res['prendas'];
      if (mounted && prendas is List) {
        setState(() => _recomendaciones = prendas);
      }
    } catch (_) {}
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Catálogo FashionStore'),
        centerTitle: false,
        actions: [
          Stack(
            alignment: Alignment.center,
            children: [
              IconButton(
                icon: const Icon(Icons.shopping_bag_outlined),
                tooltip: 'Bolsa de compras',
                onPressed: () => context.push('/carrito'),
              ),
              if (_cartService.totalCount > 0)
                Positioned(
                  right: 8,
                  top: 8,
                  child: Container(
                    padding: const EdgeInsets.all(4),
                    decoration: const BoxDecoration(
                      color: Color(0xFF4F46E5),
                      shape: BoxShape.circle,
                    ),
                    constraints: const BoxConstraints(minWidth: 18, minHeight: 18),
                    child: Text(
                      '${_cartService.totalCount}',
                      style: const TextStyle(color: Colors.white, fontSize: 10, fontWeight: FontWeight.bold),
                      textAlign: TextAlign.center,
                    ),
                  ),
                ),
            ],
          ),
          PopupMenuButton<String>(
            icon: const Icon(Icons.menu),
            tooltip: 'Menú',
            onSelected: (value) {
              switch (value) {
                case 'sucursales':
                  context.push('/sucursales');
                case 'compras':
                  context.push('/mis-compras');
                case 'reservas':
                  context.push('/reservas');
                case 'perfil':
                  context.push('/perfil');
                case 'login':
                  // El login se apila arriba del catálogo (no lo reemplaza), así que
                  // al volver hay que refrescar a mano: nadie avisa que ya hay sesión.
                  context.push('/login').then((_) {
                    if (!mounted) return;
                    setState(() {});
                    _cargarRecomendaciones();
                  });
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
                  value: 'compras',
                  child: ListTile(
                    leading: Icon(Icons.receipt_long_outlined),
                    title: Text('Mis Compras'),
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
      // CU-29: el chat funciona también sin sesión iniciada.
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => context.push('/asistente'),
        backgroundColor: const Color(0xFF4F46E5),
        icon: const Icon(Icons.chat_bubble_outline, color: Colors.white),
        label: const Text('Asistente', style: TextStyle(color: Colors.white)),
      ),
      body: RefreshIndicator(
        onRefresh: () async {
          await _cargarDatos();
          await _cargarRecomendaciones();
        },
        child: Column(
          children: [
            // CU-28: Recomendaciones de IA
            if (_recomendaciones.isNotEmpty) ...[
              const Padding(
                padding: EdgeInsets.fromLTRB(16, 12, 16, 0),
                child: Align(
                  alignment: Alignment.centerLeft,
                  child: Text(
                    '✨ Recomendado para ti',
                    style: TextStyle(fontSize: 15, fontWeight: FontWeight.bold, color: Color(0xFF334155)),
                  ),
                ),
              ),
              SizedBox(
                height: 172,
                child: ListView.builder(
                  scrollDirection: Axis.horizontal,
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                  itemCount: _recomendaciones.length,
                  itemBuilder: (context, index) {
                    final p = _recomendaciones[index];
                    return GestureDetector(
                      onTap: () => _mostrarModalAgregarBolsa(Map<String, dynamic>.from(p)),
                      child: Container(
                        width: 130,
                        margin: const EdgeInsets.only(right: 10),
                        padding: const EdgeInsets.all(10),
                        decoration: BoxDecoration(
                          color: const Color(0xFFEEF2FF),
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            ClipRRect(
                              borderRadius: BorderRadius.circular(8),
                              child: SizedBox(
                                height: 55,
                                width: double.infinity,
                                child: (p['imagen_url'] as String?)?.isNotEmpty == true
                                    ? Image.network(
                                        p['imagen_url'],
                                        fit: BoxFit.cover,
                                        errorBuilder: (_, __, ___) => const Icon(Icons.checkroom, color: Color(0xFF4F46E5), size: 26),
                                      )
                                    : const Icon(Icons.checkroom, color: Color(0xFF4F46E5), size: 26),
                              ),
                            ),
                            const SizedBox(height: 6),
                            Text(
                              p['nombre'] ?? '',
                              maxLines: 2,
                              overflow: TextOverflow.ellipsis,
                              style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 12.5),
                            ),
                            const Spacer(),
                            Text(
                              'Bs. ${p['precio_base']}',
                              style: const TextStyle(fontWeight: FontWeight.bold, color: Color(0xFF4F46E5), fontSize: 12.5),
                            ),
                          ],
                        ),
                      ),
                    );
                  },
                ),
              ),
              const Divider(height: 1),
            ],
            // Categorías Chips
            if (_categorias.isNotEmpty)
              SingleChildScrollView(
                scrollDirection: Axis.horizontal,
                padding: const EdgeInsets.symmetric(
                  horizontal: 16,
                  vertical: 8,
                ),
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
                              _selectedCategoriaId = selected
                                  ? cat['id']
                                  : null;
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
                  ? const Center(
                      child: Text(
                        'No hay prendas registradas en este momento.',
                      ),
                    )
                  : ListView.builder(
                      padding: const EdgeInsets.all(16),
                      itemCount: _prendas.length,
                      itemBuilder: (context, index) {
                        final p = _prendas[index];
                        final has3D =
                            p['modelo_3d_url'] != null &&
                            p['modelo_3d_url'].toString().isNotEmpty;
                        final imagenUrl = p['imagen_url'] as String?;
                        final tieneImagen =
                            imagenUrl != null && imagenUrl.isNotEmpty;

                        return GestureDetector(
                          onTap: () => _mostrarModalAgregarBolsa(p),
                          child: Card(
                          margin: const EdgeInsets.only(bottom: 16),
                          elevation: 2,
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(12),
                          ),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              // Imagen de la prenda
                              ClipRRect(
                                borderRadius: const BorderRadius.vertical(
                                  top: Radius.circular(12),
                                ),
                                child: Container(
                                  height: 150,
                                  width: double.infinity,
                                  color: Colors.indigo.shade50,
                                  child: Stack(
                                    children: [
                                      if (tieneImagen)
                                        Positioned.fill(
                                          child: Image.network(
                                            imagenUrl,
                                            fit: BoxFit.cover,
                                            errorBuilder:
                                                (context, error, stackTrace) =>
                                                    const Center(
                                                      child: Icon(
                                                        Icons.checkroom,
                                                        size: 64,
                                                        color: Colors.indigo,
                                                      ),
                                                    ),
                                            loadingBuilder:
                                                (context, child, progress) {
                                                  if (progress == null)
                                                    return child;
                                                  return const Center(
                                                    child:
                                                        CircularProgressIndicator(
                                                          strokeWidth: 2,
                                                        ),
                                                  );
                                                },
                                          ),
                                        )
                                      else
                                        const Center(
                                          child: Icon(
                                            Icons.checkroom,
                                            size: 64,
                                            color: Colors.indigo,
                                          ),
                                        ),
                                      if (has3D)
                                        Positioned(
                                          top: 10,
                                          right: 10,
                                          child: Container(
                                            padding: const EdgeInsets.symmetric(
                                              horizontal: 8,
                                              vertical: 4,
                                            ),
                                            decoration: BoxDecoration(
                                              color: Colors.green.shade700,
                                              borderRadius:
                                                  BorderRadius.circular(8),
                                            ),
                                            child: const Row(
                                              mainAxisSize: MainAxisSize.min,
                                              children: [
                                                Icon(
                                                  Icons.view_in_ar,
                                                  size: 14,
                                                  color: Colors.white,
                                                ),
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
                                        style: const TextStyle(
                                          fontSize: 13,
                                          color: Colors.black54,
                                        ),
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
                                    Wrap(
                                      alignment: WrapAlignment.end,
                                      spacing: 8,
                                      runSpacing: 8,
                                      children: [
                                        OutlinedButton.icon(
                                          onPressed: () => context.push(
                                            '/vestidor-ar',
                                            extra: p,
                                          ),
                                          icon: const Icon(
                                            Icons.view_in_ar,
                                            size: 16,
                                          ),
                                          label: const Text('3D RA'),
                                        ),
                                        OutlinedButton.icon(
                                          onPressed: () {
                                            if (_apiService.isLoggedIn) {
                                              context.push(
                                                '/reservar',
                                                extra: p,
                                              );
                                            } else {
                                              // Igual que en el menú: el login se apila
                                              // arriba, así que al volver refrescamos a mano.
                                              context.push('/login').then((_) {
                                                if (!mounted) return;
                                                setState(() {});
                                                _cargarRecomendaciones();
                                              });
                                            }
                                          },
                                          icon: const Icon(
                                            Icons.event_available,
                                            size: 16,
                                          ),
                                          label: const Text('Reservar'),
                                        ),
                                        ElevatedButton.icon(
                                          onPressed: () => _mostrarModalAgregarBolsa(p),
                                          icon: const Icon(
                                            Icons.shopping_bag_outlined,
                                            size: 16,
                                          ),
                                          label: const Text('Comprar'),
                                          style: ElevatedButton.styleFrom(
                                            backgroundColor: const Color(0xFF4F46E5),
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

  void _mostrarModalAgregarBolsa(Map<String, dynamic> prenda) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (ctx) => _ModalSeleccionarVariante(
        prenda: prenda,
        // El login se apila arriba, así que al volver de ahí refrescamos a mano.
        onRegresoLogin: () {
          if (!mounted) return;
          setState(() {});
          _cargarRecomendaciones();
        },
      ),
    );
  }
}

class _ModalSeleccionarVariante extends StatefulWidget {
  final Map<String, dynamic> prenda;
  final VoidCallback? onRegresoLogin;
  const _ModalSeleccionarVariante({required this.prenda, this.onRegresoLogin});

  @override
  State<_ModalSeleccionarVariante> createState() => _ModalSeleccionarVarianteState();
}

class _ModalSeleccionarVarianteState extends State<_ModalSeleccionarVariante> {
  final _apiService = ApiService();
  final _cartService = CartService();
  bool _isLoading = true;
  List<dynamic> _variantes = [];
  Map<String, dynamic>? _selectedVariant;
  int _cantidad = 1;

  @override
  void initState() {
    super.initState();
    _cargarVariantes();
  }

  Future<void> _cargarVariantes() async {
    setState(() => _isLoading = true);
    try {
      final vars = await _apiService.getVariantes(widget.prenda['id']);
      final activas = vars.where((v) => v['estado'] == true).toList();
      if (mounted) {
        setState(() {
          _variantes = activas;
          if (activas.isNotEmpty) {
            _selectedVariant = activas.first;
          }
        });
      }
    } catch (_) {
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  void _agregarABolsa() {
    if (_selectedVariant == null) return;

    final precio = (widget.prenda['precio_base'] as num).toDouble();
    _cartService.addItem(CartItem(
      varianteId: _selectedVariant!['id'] as int,
      prendaId: widget.prenda['id'] as int,
      nombre: widget.prenda['nombre'] as String,
      talla: (_selectedVariant!['talla_nombre'] ?? 'Única').toString(),
      color: (_selectedVariant!['color_nombre'] ?? 'Estándar').toString(),
      precio: precio,
      cantidad: _cantidad,
      imagenUrl: widget.prenda['imagen_url'] as String?,
    ));

    // El contexto de este modal queda invalido despues de cerrarlo (pop), asi
    // que el router y el ScaffoldMessenger de la pantalla que lo abrio se
    // capturan ANTES de cerrar, para poder mostrar el snackbar y navegar
    // correctamente desde su accion "Ver Bolsa".
    final router = GoRouter.of(context);
    final messenger = ScaffoldMessenger.of(context);
    final nombrePrenda = widget.prenda['nombre'];

    Navigator.of(context).pop();

    messenger.showSnackBar(
      SnackBar(
        content: Text('✓ Se añadió "$nombrePrenda" a tu bolsa.'),
        backgroundColor: const Color(0xFF059669),
        action: SnackBarAction(
          label: 'Ver Bolsa',
          textColor: Colors.white,
          onPressed: () => router.push('/carrito'),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final precio = (widget.prenda['precio_base'] as num).toDouble();
    final subtotal = precio * _cantidad;

    return Container(
      decoration: const BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      padding: EdgeInsets.only(
        top: 20,
        left: 20,
        right: 20,
        bottom: MediaQuery.of(context).viewInsets.bottom + 24,
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Center(
            child: Container(
              width: 40,
              height: 4,
              decoration: BoxDecoration(
                color: Colors.grey.shade300,
                borderRadius: BorderRadius.circular(2),
              ),
            ),
          ),
          const SizedBox(height: 16),
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              ClipRRect(
                borderRadius: BorderRadius.circular(10),
                child: Container(
                  width: 90,
                  height: 90,
                  color: const Color(0xFFEEF2FF),
                  child: widget.prenda['imagen_url'] != null
                      ? Image.network(
                          widget.prenda['imagen_url'],
                          fit: BoxFit.cover,
                          errorBuilder: (_, __, ___) => const Icon(Icons.checkroom, color: Color(0xFF4F46E5)),
                        )
                      : const Icon(Icons.checkroom, color: Color(0xFF4F46E5)),
                ),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    if (widget.prenda['categoria_nombre'] != null)
                      Text(
                        widget.prenda['categoria_nombre'],
                        style: TextStyle(fontSize: 11.5, fontWeight: FontWeight.bold, color: Colors.indigo.shade600),
                      ),
                    const SizedBox(height: 2),
                    Text(
                      widget.prenda['nombre'],
                      style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      'Precio: Bs. ${precio.toStringAsFixed(2)}',
                      style: const TextStyle(color: Color(0xFF4F46E5), fontWeight: FontWeight.bold),
                    ),
                  ],
                ),
              ),
            ],
          ),
          if ((widget.prenda['descripcion'] as String?)?.isNotEmpty == true) ...[
            const SizedBox(height: 12),
            Text(
              widget.prenda['descripcion'],
              style: const TextStyle(fontSize: 13, color: Colors.black87, height: 1.4),
            ),
          ],
          const SizedBox(height: 14),
          Row(
            children: [
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: () {
                    final router = GoRouter.of(context);
                    Navigator.of(context).pop();
                    router.push('/vestidor-ar', extra: widget.prenda);
                  },
                  icon: const Icon(Icons.view_in_ar, size: 16),
                  label: const Text('3D RA'),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: () {
                    final router = GoRouter.of(context);
                    final logueado = _apiService.isLoggedIn;
                    final onRegresoLogin = widget.onRegresoLogin;
                    Navigator.of(context).pop();
                    final future = router.push(
                      logueado ? '/reservar' : '/login',
                      extra: logueado ? widget.prenda : null,
                    );
                    if (!logueado) future.then((_) => onRegresoLogin?.call());
                  },
                  icon: const Icon(Icons.event_available, size: 16),
                  label: const Text('Reservar'),
                ),
              ),
            ],
          ),
          const SizedBox(height: 20),

          // Selección de variante
          const Text(
            'Selecciona Talla y Color:',
            style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13, color: Color(0xFF334155)),
          ),
          const SizedBox(height: 8),
          if (_isLoading)
            const Center(child: Padding(padding: EdgeInsets.all(12), child: CircularProgressIndicator()))
          else if (_variantes.isEmpty)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 8),
              child: Text('No hay variantes disponibles actualmente para esta prenda.'),
            )
          else
            DropdownButtonFormField<int>(
              value: _selectedVariant?['id'] as int?,
              decoration: InputDecoration(
                contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
              ),
              items: _variantes.map<DropdownMenuItem<int>>((v) {
                return DropdownMenuItem<int>(
                  value: v['id'] as int,
                  child: Text('Talla: ${v['talla_nombre']}  ·  Color: ${v['color_nombre']}'),
                );
              }).toList(),
              onChanged: (val) {
                if (val != null) {
                  setState(() {
                    _selectedVariant = _variantes.firstWhere((v) => v['id'] == val);
                  });
                }
              },
            ),

          const SizedBox(height: 16),

          // Cantidad
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text(
                'Cantidad:',
                style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13, color: Color(0xFF334155)),
              ),
              Row(
                children: [
                  IconButton(
                    icon: const Icon(Icons.remove_circle_outline),
                    onPressed: _cantidad > 1 ? () => setState(() => _cantidad--) : null,
                  ),
                  Text(
                    '$_cantidad',
                    style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                  ),
                  IconButton(
                    icon: const Icon(Icons.add_circle_outline),
                    onPressed: _cantidad < 10 ? () => setState(() => _cantidad++) : null,
                  ),
                ],
              ),
            ],
          ),

          const Divider(height: 24),

          // Botón de agregar
          SizedBox(
            width: double.infinity,
            child: ElevatedButton.icon(
              onPressed: _selectedVariant == null ? null : _agregarABolsa,
              icon: const Icon(Icons.shopping_bag_outlined),
              label: Text('AÑADIR A LA BOLSA (Bs. ${subtotal.toStringAsFixed(2)})'),
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFF4F46E5),
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(vertical: 14),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
