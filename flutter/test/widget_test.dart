import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:sw_maestro_ai_study_frontend/app/app.dart';

void main() {
  testWidgets('renders recommendation home', (WidgetTester tester) async {
    SharedPreferences.setMockInitialValues({
      'onboarding_complete': true,
      'reminder_hour': 19,
      'reminder_minute': 0,
    });

    await tester.pumpWidget(
      const ProviderScope(child: MaestroMusicApp()),
    );

    await tester.pumpAndSettle();

    expect(find.text('Oh my memory'), findsOneWidget);
    expect(find.text('저녁의\n플레이리스트'), findsOneWidget);
    expect(find.text('좋아요'), findsOneWidget);
    expect(find.text('보관'), findsNothing);
    expect(find.text('글쎄요'), findsOneWidget);
  });
}
