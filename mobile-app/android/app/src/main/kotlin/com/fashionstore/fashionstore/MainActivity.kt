package com.fashionstore.fashionstore

import io.flutter.embedding.android.FlutterFragmentActivity

// flutter_stripe requiere FlutterFragmentActivity (usa Fragments internamente
// para sus componentes nativos de pago) en vez de la FlutterActivity por defecto.
class MainActivity : FlutterFragmentActivity()
