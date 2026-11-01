// Diseño de la app: la marca de FashionStore y, cuando se trabaja con otra empresa del SaaS, sus
// colores (los mismos que usa la web en /t/<slug>), con la fuente Plus Jakarta Sans de la web.
import 'package:flutter/material.dart';

const indigoMarca = Color(0xFF4F46E5);
const rosaMarca = Color(0xFFEC4899);
const fuenteMarca = 'PlusJakartaSans';

const _fondo = Color(0xFFF6F6FB);
const _tinta = Color(0xFF111827);
const _radio = 16.0;

/// "#0F766E" → Color. Null si no viene o no es un color válido.
Color? colorDeHex(Object? hex) {
  if (hex is! String) return null;
  final limpio = hex.replaceFirst('#', '');
  if (limpio.length != 6) return null;
  final valor = int.tryParse(limpio, radix: 16);
  return valor == null ? null : Color(0xFF000000 | valor);
}

/// Texto legible sobre un color: oscuro sobre colores claros (p. ej. un amarillo de marca).
Color textoSobre(Color fondo) => fondo.computeLuminance() > 0.45 ? _tinta : Colors.white;

/// Tema con los colores de la empresa (marca = GET /api/v1/tienda). Sin marca, el de FashionStore.
ThemeData temaDeEmpresa(Map<String, dynamic>? marca) {
  final primario = colorDeHex(marca?['color_primario']) ?? indigoMarca;
  final acento = colorDeHex(marca?['color_acento']) ?? rosaMarca;
  final clave = (primario, acento);
  if (clave != _ultimaClave) {
    _ultimaClave = clave;
    _ultimoTema = _tema(primario, acento);
  }
  return _ultimoTema!;
}

// El tema se recalcula solo si cambian los colores (la marca se vuelve a pedir seguido)
(Color, Color)? _ultimaClave;
ThemeData? _ultimoTema;

ThemeData _tema(Color primario, Color acento) {
  final esquema = ColorScheme.fromSeed(seedColor: primario).copyWith(
    primary: primario,
    onPrimary: textoSobre(primario),
    // Tinte suave de la marca (chips elegidos, fondos destacados): igual de sobrio con cualquier color
    primaryContainer: Color.alphaBlend(primario.withValues(alpha: 0.12), Colors.white),
    onPrimaryContainer: Color.lerp(primario, Colors.black, 0.35),
    tertiary: acento,
    onTertiary: textoSobre(acento),
    surface: Colors.white,
    onSurface: _tinta,
  );
  final bordeSuave = BorderSide(color: esquema.outlineVariant.withValues(alpha: 0.7));
  final redondeado = RoundedRectangleBorder(borderRadius: BorderRadius.circular(_radio));
  const textoBoton = TextStyle(fontFamily: fuenteMarca, fontWeight: FontWeight.w700, fontSize: 15);
  // 48dp como mínimo para todo lo que se toca
  const tamanoBoton = Size(64, 50);

  final base = ThemeData(useMaterial3: true, colorScheme: esquema, fontFamily: fuenteMarca);
  final texto = base.textTheme.apply(bodyColor: _tinta, displayColor: _tinta);

  return base.copyWith(
    scaffoldBackgroundColor: _fondo,
    textTheme: texto.copyWith(
      headlineSmall: texto.headlineSmall?.copyWith(fontWeight: FontWeight.w800, letterSpacing: -0.3),
      titleLarge: texto.titleLarge?.copyWith(fontWeight: FontWeight.w700, letterSpacing: -0.2),
      titleMedium: texto.titleMedium?.copyWith(fontWeight: FontWeight.w700),
      titleSmall: texto.titleSmall?.copyWith(fontWeight: FontWeight.w700),
    ),
    appBarTheme: const AppBarTheme(
      backgroundColor: _fondo,
      foregroundColor: _tinta,
      surfaceTintColor: Colors.transparent,
      elevation: 0,
      scrolledUnderElevation: 0.5,
      centerTitle: false,
      titleTextStyle: TextStyle(fontFamily: fuenteMarca, fontSize: 20, fontWeight: FontWeight.w800, color: _tinta),
    ),
    cardTheme: CardThemeData(
      color: Colors.white,
      surfaceTintColor: Colors.transparent,
      elevation: 0,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(_radio + 4), side: bordeSuave),
    ),
    elevatedButtonTheme: ElevatedButtonThemeData(
      style: ElevatedButton.styleFrom(
        backgroundColor: primario,
        foregroundColor: esquema.onPrimary,
        elevation: 0,
        minimumSize: tamanoBoton,
        shape: redondeado,
        textStyle: textoBoton,
      ),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(minimumSize: tamanoBoton, shape: redondeado, textStyle: textoBoton),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        minimumSize: const Size(48, 48),
        shape: redondeado,
        side: BorderSide(color: esquema.outline.withValues(alpha: 0.5)),
        textStyle: textoBoton.copyWith(fontSize: 14),
      ),
    ),
    textButtonTheme: TextButtonThemeData(
      style: TextButton.styleFrom(minimumSize: const Size(48, 48), textStyle: textoBoton.copyWith(fontSize: 14)),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: Colors.white,
      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
      border: OutlineInputBorder(borderRadius: BorderRadius.circular(_radio), borderSide: bordeSuave),
      enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(_radio), borderSide: bordeSuave),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(_radio),
        borderSide: BorderSide(color: primario, width: 2),
      ),
      errorBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(_radio),
        borderSide: BorderSide(color: esquema.error),
      ),
    ),
    chipTheme: ChipThemeData(
      backgroundColor: Colors.white,
      selectedColor: esquema.primaryContainer,
      side: bordeSuave,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      labelStyle: const TextStyle(fontFamily: fuenteMarca, fontWeight: FontWeight.w600, color: _tinta),
    ),
    floatingActionButtonTheme: FloatingActionButtonThemeData(
      backgroundColor: primario,
      foregroundColor: esquema.onPrimary,
      elevation: 2,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(_radio + 2)),
      extendedTextStyle: textoBoton,
    ),
    snackBarTheme: SnackBarThemeData(
      behavior: SnackBarBehavior.floating,
      backgroundColor: const Color(0xFF1F2937),
      actionTextColor: esquema.inversePrimary,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
      contentTextStyle: const TextStyle(fontFamily: fuenteMarca, color: Colors.white, fontSize: 14),
    ),
    dialogTheme: DialogThemeData(
      backgroundColor: Colors.white,
      surfaceTintColor: Colors.transparent,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24)),
    ),
    bottomSheetTheme: const BottomSheetThemeData(
      backgroundColor: Colors.white,
      surfaceTintColor: Colors.transparent,
      showDragHandle: true,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(28))),
    ),
    popupMenuTheme: PopupMenuThemeData(
      color: Colors.white,
      surfaceTintColor: Colors.transparent,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(_radio)),
    ),
    dividerTheme: DividerThemeData(color: esquema.outlineVariant.withValues(alpha: 0.6), space: 1),
    listTileTheme: const ListTileThemeData(minVerticalPadding: 12),
  );
}

/// Colores de la marca a mano en las pantallas (cambian con la empresa).
extension ColoresDeMarca on BuildContext {
  /// Color principal de la empresa con la que trabaja la app.
  Color get marca => Theme.of(this).colorScheme.primary;

  /// Texto e íconos sobre el color principal.
  Color get sobreMarca => Theme.of(this).colorScheme.onPrimary;

  /// Fondo suave del color principal (chips, avatares, destacados).
  Color get marcaSuave => Theme.of(this).colorScheme.primaryContainer;

  /// Color de acento de la empresa.
  Color get acento => Theme.of(this).colorScheme.tertiary;
}
