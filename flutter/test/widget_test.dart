import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:sw_maestro_ai_study_frontend/app/app.dart';
import 'package:sw_maestro_ai_study_frontend/features/recommendation/data/recommendation_api_client.dart';
import 'package:sw_maestro_ai_study_frontend/features/recommendation/domain/music_recommendation.dart';
import 'package:sw_maestro_ai_study_frontend/features/recommendation/presentation/recommendation_controller.dart';

void main() {
  testWidgets('renders recommendation home', (WidgetTester tester) async {
    SharedPreferences.setMockInitialValues({
      'onboarding_complete': true,
      'reminder_hour': 19,
      'reminder_minute': 0,
    });

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          recommendationApiClientProvider.overrideWithValue(_FakeApiClient()),
        ],
        child: const MaestroMusicApp(),
      ),
    );

    await tester.pumpAndSettle();

    expect(find.text('Oh my memory'), findsOneWidget);
    expect(find.text('오늘의\n플레이리스트'), findsOneWidget);
    expect(find.text('대표 추천'), findsOneWidget);
    expect(find.text('anchor'), findsNothing);
    expect(find.text('좋아요'), findsOneWidget);
    expect(find.text('보관'), findsNothing);
    expect(find.text('글쎄요'), findsOneWidget);
  });
}

class _FakeApiClient extends RecommendationApiClient {
  _FakeApiClient() : super(baseUrl: 'http://localhost');

  @override
  Future<SessionDto> createSession({
    required int age,
    required List<String> preferredGenres,
    required List<String> preferredArtists,
  }) async {
    return const SessionDto(sessionId: 'sess_test');
  }

  @override
  Future<BundleDto> recommend({
    required String sessionId,
    required String freeText,
  }) async {
    return BundleDto(
      bundleId: 'bundle_test',
      emotionTitle: '테스트 추천 묶음',
      songs: [
        MusicRecommendation.fromApiJson({
          'song_id': 'song_test',
          'title': '테스트 곡',
          'artists': ['테스트 아티스트'],
          'album_art_url': '',
          'preview_url': 'https://music.apple.com/',
          'slot_type': 'anchor',
          'reason': '테스트 추천 이유',
        }),
      ],
    );
  }

  @override
  Future<FeedbackDto> submitFeedback({
    required String sessionId,
    required String bundleId,
    required MusicRecommendation recommendation,
    required RecommendationReaction reaction,
  }) async {
    return const FeedbackDto(
      negativeCount: 0,
      nextAction: 'recommend_next_bundle',
    );
  }

  @override
  Future<FollowUpDto> submitFollowUp({
    required String sessionId,
    required String text,
  }) async {
    return const FollowUpDto(nextAction: 'recommend_next_bundle');
  }
}
