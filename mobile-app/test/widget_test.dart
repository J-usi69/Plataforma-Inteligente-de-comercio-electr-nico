import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'package:fashionstore/main.dart';

void main() {
  testWidgets('App arranca y muestra la pantalla de catalogo', (WidgetTester tester) async {
    await http.runWithClient(() async {
      await tester.pumpWidget(const FashionStoreApp());
      await tester.pumpAndSettle();
    }, () => MockClient((req) async {
      final cuerpo = req.url.path.endsWith('/recomendaciones') || req.url.path.endsWith('/tienda') ? {} : [];
      return http.Response(jsonEncode(cuerpo), 200, headers: {'content-type': 'application/json'});
    }));

    // El título lleva el nombre de la empresa: "Catálogo FashionStore"
    expect(find.textContaining('Catálogo'), findsWidgets);
  });
}
