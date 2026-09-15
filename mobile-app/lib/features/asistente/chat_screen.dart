import 'package:flutter/material.dart';
import '../../core/services/api_service.dart';

class _MensajeChat {
  final String texto;
  final bool esUsuario;
  _MensajeChat(this.texto, this.esUsuario);
}

// CU-29: Asistente conversacional para el Cliente.
class ChatScreen extends StatefulWidget {
  const ChatScreen({super.key});

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  final _apiService = ApiService();
  final _controller = TextEditingController();
  final _scrollController = ScrollController();
  final List<_MensajeChat> _mensajes = [
    _MensajeChat(
      '¡Hola! Soy el asistente virtual de FashionStore. Preguntame sobre prendas, tallas, disponibilidad o reservas.',
      false,
    ),
  ];
  bool _enviando = false;

  @override
  void dispose() {
    _controller.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  Future<void> _enviar() async {
    final texto = _controller.text.trim();
    if (texto.isEmpty || _enviando) return;

    // Se arma antes de agregar el mensaje nuevo: son los turnos previos de la conversación.
    final historial = _mensajes
        .map((m) => {'rol': m.esUsuario ? 'user' : 'asistente', 'contenido': m.texto})
        .toList();

    setState(() {
      _mensajes.add(_MensajeChat(texto, true));
      _enviando = true;
      _controller.clear();
    });
    _scrollAlFinal();

    try {
      final respuesta = await _apiService.enviarMensajeChat(texto, historial: historial);
      setState(() => _mensajes.add(_MensajeChat(respuesta, false)));
    } catch (e) {
      setState(() => _mensajes.add(_MensajeChat(
        'No se pudo contactar al asistente en este momento. Intentalo de nuevo más tarde.',
        false,
      )));
    } finally {
      if (mounted) setState(() => _enviando = false);
      _scrollAlFinal();
    }
  }

  void _scrollAlFinal() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!_scrollController.hasClients) return;
      _scrollController.animateTo(
        _scrollController.position.maxScrollExtent,
        duration: const Duration(milliseconds: 250),
        curve: Curves.easeOut,
      );
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Asistente FashionStore'),
      ),
      body: Column(
        children: [
          Expanded(
            child: ListView.builder(
              controller: _scrollController,
              padding: const EdgeInsets.all(16),
              itemCount: _mensajes.length,
              itemBuilder: (context, index) {
                final m = _mensajes[index];
                return Align(
                  alignment: m.esUsuario ? Alignment.centerRight : Alignment.centerLeft,
                  child: Container(
                    constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.75),
                    margin: const EdgeInsets.only(bottom: 10),
                    padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                    decoration: BoxDecoration(
                      color: m.esUsuario ? const Color(0xFF4F46E5) : const Color(0xFFF1F5F9),
                      borderRadius: BorderRadius.circular(14),
                    ),
                    child: Text(
                      m.texto,
                      style: TextStyle(
                        color: m.esUsuario ? Colors.white : const Color(0xFF0F172A),
                      ),
                    ),
                  ),
                );
              },
            ),
          ),
          if (_enviando)
            const Padding(
              padding: EdgeInsets.only(bottom: 8),
              child: SizedBox(
                width: 16,
                height: 16,
                child: CircularProgressIndicator(strokeWidth: 2),
              ),
            ),
          SafeArea(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
              child: Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _controller,
                      decoration: InputDecoration(
                        hintText: 'Escribí tu consulta...',
                        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                        border: OutlineInputBorder(borderRadius: BorderRadius.circular(24)),
                      ),
                      textInputAction: TextInputAction.send,
                      onSubmitted: (_) => _enviar(),
                    ),
                  ),
                  const SizedBox(width: 8),
                  IconButton.filled(
                    onPressed: _enviando ? null : _enviar,
                    icon: const Icon(Icons.send),
                    style: IconButton.styleFrom(backgroundColor: const Color(0xFF4F46E5)),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
