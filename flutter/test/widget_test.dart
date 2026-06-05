import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:sw_maestro_ai_study_frontend/app/app.dart';

void main() {
  testWidgets('renders recommendation home', (WidgetTester tester) async {
    await tester.pumpWidget(
      const ProviderScope(child: MaestroMusicApp()),
    );

    await tester.pump();

    expect(find.text('오늘의 추천'), findsOneWidget);
    expect(find.text('좋아요'), findsOneWidget);
    expect(find.text('보관'), findsOneWidget);
    expect(find.text('잘 모르겠어요'), findsOneWidget);
  });
}
