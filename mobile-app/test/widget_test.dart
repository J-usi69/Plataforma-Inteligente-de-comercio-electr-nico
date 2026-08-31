import 'package:flutter_test/flutter_test.dart';

import 'package:fashionstore/main.dart';

void main() {
  testWidgets('App arranca y muestra la pantalla de catalogo', (WidgetTester tester) async {
    await tester.pumpWidget(const FashionStoreApp());
    await tester.pumpAndSettle();

    expect(find.text('Catalogo'), findsWidgets);
  });
}
