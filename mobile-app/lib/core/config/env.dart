class Env {
  // En el emulador de Android, "localhost" de la maquina host se accede
  // como 10.0.2.2. En iOS simulator y web, "localhost" funciona directo.
  static const String apiUrl = String.fromEnvironment(
    'API_URL',
    defaultValue: 'http://10.0.2.2:8000',
  );
}
