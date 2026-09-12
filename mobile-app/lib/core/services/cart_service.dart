import 'package:flutter/foundation.dart';

class CartItem {
  final int varianteId;
  final int prendaId;
  final String nombre;
  final String talla;
  final String color;
  final double precio;
  int cantidad;
  final String? imagenUrl;

  CartItem({
    required this.varianteId,
    required this.prendaId,
    required this.nombre,
    required this.talla,
    required this.color,
    required this.precio,
    this.cantidad = 1,
    this.imagenUrl,
  });
}

class CartService extends ChangeNotifier {
  static final CartService _instance = CartService._internal();
  factory CartService() => _instance;
  CartService._internal();

  final List<CartItem> _items = [];
  int sucursalId = 1;

  List<CartItem> get items => List.unmodifiable(_items);

  double get totalAmount =>
      _items.fold(0.0, (sum, item) => sum + (item.precio * item.cantidad));

  int get totalCount =>
      _items.fold(0, (sum, item) => sum + item.cantidad);

  void setSucursal(int id) {
    sucursalId = id;
    notifyListeners();
  }

  void addItem(CartItem item) {
    final index = _items.indexWhere((i) => i.varianteId == item.varianteId);
    if (index >= 0) {
      _items[index].cantidad += item.cantidad;
    } else {
      _items.add(item);
    }
    notifyListeners();
  }

  void updateQuantity(int varianteId, int cantidad) {
    if (cantidad <= 0) {
      removeItem(varianteId);
      return;
    }
    final index = _items.indexWhere((i) => i.varianteId == varianteId);
    if (index >= 0) {
      _items[index].cantidad = cantidad;
      notifyListeners();
    }
  }

  void removeItem(int varianteId) {
    _items.removeWhere((i) => i.varianteId == varianteId);
    notifyListeners();
  }

  void clear() {
    _items.clear();
    notifyListeners();
  }
}
