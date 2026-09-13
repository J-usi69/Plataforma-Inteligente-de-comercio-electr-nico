class Env {
  // En el emulador de Android, "localhost" de la maquina host se accede
  // como 10.0.2.2. En iOS simulator y web, "localhost" funciona directo.
  static const String apiUrl = String.fromEnvironment(
    'API_URL',
    defaultValue: 'http://10.0.2.2:8000',
  );

  // Clave publicable de Stripe (modo test) — no es sensible, puede vivir en el binario.
  static const String stripePublishableKey = String.fromEnvironment(
    'STRIPE_PUBLISHABLE_KEY',
    defaultValue:
        'pk_test_51UF3C82Ldeg7gvA62ZFDHp5d6zlVBaDhtnIOxmomKawM4D35Yi6Ev4Bd9zH5G66c4iMO8yvJbcU5nl5e5DjbFRqi00htVInn0I',
  );
}
