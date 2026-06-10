import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/preferences/app_settings.dart';
import '../data/recommendation_api_client.dart';
import '../domain/music_recommendation.dart';

final recommendationApiClientProvider = Provider<RecommendationApiClient>(
  (ref) => RecommendationApiClient(),
);

final recommendationControllerProvider =
    StateNotifierProvider<RecommendationController, RecommendationState>(
  (ref) {
    final settings = ref.watch(appSettingsControllerProvider);
    final apiClient = ref.watch(recommendationApiClientProvider);
    return RecommendationController(apiClient: apiClient, settings: settings);
  },
);

class RecommendationState {
  const RecommendationState({
    this.queue = const [],
    this.allRecommendations = const [],
    this.savedRecommendations = const [],
    this.isLoading = false,
    this.errorMessage = '',
    this.sessionId = '',
    this.bundleId = '',
    this.emotionTitle = '',
    this.unsureStreak = 0,
    this.savedIds = const {},
    this.lastReaction,
  });

  final List<MusicRecommendation> queue;
  final List<MusicRecommendation> allRecommendations;
  final List<MusicRecommendation> savedRecommendations;
  final bool isLoading;
  final String errorMessage;
  final String sessionId;
  final String bundleId;
  final String emotionTitle;
  final int unsureStreak;
  final Set<String> savedIds;
  final RecommendationReaction? lastReaction;

  MusicRecommendation? get current => queue.isEmpty ? null : queue.first;
  bool get shouldAskFollowUp => unsureStreak >= 3;

  RecommendationState copyWith({
    List<MusicRecommendation>? queue,
    List<MusicRecommendation>? allRecommendations,
    List<MusicRecommendation>? savedRecommendations,
    bool? isLoading,
    String? errorMessage,
    String? sessionId,
    String? bundleId,
    String? emotionTitle,
    int? unsureStreak,
    Set<String>? savedIds,
    RecommendationReaction? lastReaction,
  }) {
    return RecommendationState(
      queue: queue ?? this.queue,
      allRecommendations: allRecommendations ?? this.allRecommendations,
      savedRecommendations: savedRecommendations ?? this.savedRecommendations,
      isLoading: isLoading ?? this.isLoading,
      errorMessage: errorMessage ?? this.errorMessage,
      sessionId: sessionId ?? this.sessionId,
      bundleId: bundleId ?? this.bundleId,
      emotionTitle: emotionTitle ?? this.emotionTitle,
      unsureStreak: unsureStreak ?? this.unsureStreak,
      savedIds: savedIds ?? this.savedIds,
      lastReaction: lastReaction ?? this.lastReaction,
    );
  }
}

class RecommendationController extends StateNotifier<RecommendationState> {
  RecommendationController({
    required RecommendationApiClient apiClient,
    required AppSettingsState settings,
  })  : _apiClient = apiClient,
        _settings = settings,
        super(const RecommendationState()) {
    if (settings.isLoaded && settings.onboardingComplete) {
      initialize();
    }
  }

  final RecommendationApiClient _apiClient;
  final AppSettingsState _settings;

  Future<void> initialize() async {
    if (state.isLoading || state.sessionId.isNotEmpty) {
      return;
    }

    state = state.copyWith(isLoading: true, errorMessage: '');
    try {
      final session = await _apiClient.createSession(
        age: _settings.age,
        preferredGenres: _settings.genres,
        preferredArtists: _settings.favoriteArtistList,
      );
      state = state.copyWith(sessionId: session.sessionId);
      await loadRecommendations();
    } catch (error) {
      state = state.copyWith(
        isLoading: false,
        errorMessage: error.toString(),
      );
    }
  }

  Future<void> loadRecommendations() async {
    if (state.sessionId.isEmpty) {
      return;
    }

    state = state.copyWith(isLoading: true, errorMessage: '');
    try {
      final bundle = await _apiClient.recommend(
        sessionId: state.sessionId,
        freeText: _recommendationPrompt,
      );
      state = state.copyWith(
        queue: bundle.songs,
        allRecommendations: [...state.allRecommendations, ...bundle.songs],
        bundleId: bundle.bundleId,
        emotionTitle: bundle.emotionTitle,
        isLoading: false,
      );
    } catch (error) {
      state = state.copyWith(
        isLoading: false,
        errorMessage: error.toString(),
      );
    }
  }

  Future<void> react(RecommendationReaction reaction) async {
    final current = state.current;
    if (current == null) {
      return;
    }

    final nextQueue = state.queue.skip(1).toList();
    final nextSavedIds = {...state.savedIds};
    if (reaction == RecommendationReaction.like) {
      nextSavedIds.add(current.id);
    }

    state = state.copyWith(
      queue: nextQueue,
      savedIds: nextSavedIds,
      unsureStreak: reaction == RecommendationReaction.unsure
          ? state.unsureStreak + 1
          : 0,
      lastReaction: reaction,
    );

    if (state.sessionId.isEmpty) {
      return;
    }

    try {
      final feedback = await _apiClient.submitFeedback(
        sessionId: state.sessionId,
        bundleId: state.bundleId,
        recommendation: current,
        reaction: reaction,
      );
      if (feedback.nextAction == 'request_follow_up_text') {
        state = state.copyWith(unsureStreak: 3);
      }
      if (reaction == RecommendationReaction.like) {
        await refreshLibrary();
      }
    } catch (error) {
      state = state.copyWith(errorMessage: error.toString());
    }
  }

  void dismissFollowUp() {
    state = state.copyWith(unsureStreak: 0);
  }

  Future<void> submitFollowUp(String followUpText) async {
    if (state.sessionId.isEmpty || followUpText.isEmpty) {
      state = state.copyWith(unsureStreak: 0);
      return;
    }

    state = state.copyWith(isLoading: true, errorMessage: '', unsureStreak: 0);
    try {
      await _apiClient.submitFollowUp(
        sessionId: state.sessionId,
        text: followUpText,
      );
      await loadRecommendations();
    } catch (error) {
      state = state.copyWith(
        isLoading: false,
        errorMessage: error.toString(),
      );
    }
  }

  Future<void> refreshLibrary() async {
    if (state.sessionId.isEmpty) {
      return;
    }

    try {
      final saved = await _apiClient.fetchLibrary(sessionId: state.sessionId);
      state = state.copyWith(savedRecommendations: saved);
    } catch (error) {
      state = state.copyWith(errorMessage: error.toString());
    }
  }

  String get _recommendationPrompt {
    final genres =
        _settings.genres.isEmpty ? '음악' : _settings.genres.join(', ');
    final artists = _settings.favoriteArtistList.isEmpty
        ? ''
        : ' 좋아하는 가수는 ${_settings.favoriteArtistList.join(', ')}입니다.';
    return '오늘 저녁에 듣기 좋은 $genres 추천을 받고 싶어요.$artists';
  }
}
