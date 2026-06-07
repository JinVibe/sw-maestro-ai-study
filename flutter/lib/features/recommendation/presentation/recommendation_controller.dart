import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/preferences/app_settings.dart';
import '../data/api_recommendations_repository.dart';
import '../domain/music_recommendation.dart';

final recommendationsRepositoryProvider =
    Provider<ApiRecommendationsRepository>(
  (ref) => ApiRecommendationsRepository(),
);

final recommendationControllerProvider =
    StateNotifierProvider<RecommendationController, RecommendationState>(
  (ref) {
    final repository = ref.watch(recommendationsRepositoryProvider);
    // RecommendationPage는 온보딩 완료 후에만 보이므로 read로 한 번만 읽는다.
    final settings = ref.read(appSettingsControllerProvider);
    return RecommendationController(repository: repository, settings: settings);
  },
);

class RecommendationState {
  const RecommendationState({
    this.queue = const [],
    this.allRecommendations = const [],
    this.unsureStreak = 0,
    this.savedIds = const {},
    this.lastReaction,
    this.isLoading = false,
    this.error,
    this.bundleId = '',
  });

  final List<MusicRecommendation> queue;
  final List<MusicRecommendation> allRecommendations;
  final int unsureStreak;
  final Set<String> savedIds;
  final RecommendationReaction? lastReaction;
  final bool isLoading;
  final String? error;
  final String bundleId;

  MusicRecommendation? get current => queue.isEmpty ? null : queue.first;
  List<MusicRecommendation> get savedRecommendations => allRecommendations
      .where((recommendation) => savedIds.contains(recommendation.id))
      .toList();
  bool get shouldAskFollowUp => unsureStreak >= 3;

  RecommendationState copyWith({
    List<MusicRecommendation>? queue,
    List<MusicRecommendation>? allRecommendations,
    int? unsureStreak,
    Set<String>? savedIds,
    RecommendationReaction? lastReaction,
    bool? isLoading,
    String? error,
    bool clearError = false,
    String? bundleId,
  }) {
    return RecommendationState(
      queue: queue ?? this.queue,
      allRecommendations: allRecommendations ?? this.allRecommendations,
      unsureStreak: unsureStreak ?? this.unsureStreak,
      savedIds: savedIds ?? this.savedIds,
      lastReaction: lastReaction ?? this.lastReaction,
      isLoading: isLoading ?? this.isLoading,
      error: clearError ? null : (error ?? this.error),
      bundleId: bundleId ?? this.bundleId,
    );
  }
}

class RecommendationController extends StateNotifier<RecommendationState> {
  RecommendationController({
    required this.repository,
    required this.settings,
  }) : super(const RecommendationState()) {
    if (settings.onboardingComplete && settings.genres.isNotEmpty) {
      _start();
    }
  }

  final ApiRecommendationsRepository repository;
  final AppSettingsState settings;
  String _sessionId = '';

  int get _age => switch (settings.ageGroup) {
        '10대' => 15,
        '20대' => 25,
        '30대' => 35,
        '40대' => 45,
        '50대 이상' => 55,
        _ => 25,
      };

  List<String> get _artists => settings.favoriteArtists
      .split(RegExp(r'[,\s]+'))
      .map((value) => value.trim())
      .where((value) => value.isNotEmpty)
      .toList();

  // 온보딩에 별도 테마 입력이 없으므로 장르로 free_text를 구성한다.
  // TODO: 추천 시작 전 "지금 듣고 싶은 느낌" 입력 화면을 붙이면 여기로 연결.
  String get _freeText => settings.genres.isNotEmpty
      ? '${settings.genres.join(', ')} 분위기의 노래'
      : '요즘 듣고 싶은 노래';

  Future<void> _start() async {
    state = state.copyWith(isLoading: true, clearError: true);
    try {
      _sessionId = await repository.createSession(
        age: _age,
        genres: settings.genres,
        artists: _artists,
      );
      await _loadBundle(freeText: _freeText);
    } catch (error) {
      state = state.copyWith(isLoading: false, error: error.toString());
    }
  }

  Future<void> _loadBundle({
    required String freeText,
    String followUpText = '',
  }) async {
    if (_sessionId.isEmpty) {
      return;
    }
    state = state.copyWith(isLoading: true, clearError: true);
    try {
      final bundle = await repository.recommend(
        sessionId: _sessionId,
        freeText: freeText,
        followUpText: followUpText,
      );
      state = state.copyWith(
        queue: bundle.songs,
        allRecommendations: [...state.allRecommendations, ...bundle.songs],
        bundleId: bundle.bundleId,
        unsureStreak: 0,
        isLoading: false,
      );
    } catch (error) {
      state = state.copyWith(isLoading: false, error: error.toString());
    }
  }

  void react(RecommendationReaction reaction) {
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

    // 백엔드에 피드백 전송(다음 추천 제외/보관함 반영). 실패해도 UX는 진행.
    unawaited(_sendFeedback(current, reaction));

    // 큐를 다 보면 다음 번들을 불러온다(꼬리 질문이 떠야 하면 대기).
    if (nextQueue.isEmpty && !state.shouldAskFollowUp) {
      unawaited(_loadBundle(freeText: _freeText));
    }
  }

  Future<void> _sendFeedback(
    MusicRecommendation song,
    RecommendationReaction reaction,
  ) async {
    if (_sessionId.isEmpty) {
      return;
    }
    try {
      await repository.sendFeedback(
        sessionId: _sessionId,
        bundleId: state.bundleId,
        feedbacks: [
          {
            'song_id': song.id,
            'title': song.title,
            'reaction':
                reaction == RecommendationReaction.like ? '좋아요' : '싫어요',
            'saved': reaction == RecommendationReaction.like,
          },
        ],
      );
    } catch (_) {
      // 피드백 전송 실패는 조용히 무시(다음 추천에 반영 안 될 수 있음).
    }
  }

  /// 꼬리 질문 답변을 반영해 다음 번들을 불러온다.
  Future<void> submitFollowUp(String text) async {
    await _loadBundle(freeText: _freeText, followUpText: text.trim());
  }

  void dismissFollowUp() {
    state = state.copyWith(unsureStreak: 0);
    if (state.queue.isEmpty) {
      unawaited(_loadBundle(freeText: _freeText));
    }
  }

  /// 에러 후 재시도.
  Future<void> retry() => _start();
}
