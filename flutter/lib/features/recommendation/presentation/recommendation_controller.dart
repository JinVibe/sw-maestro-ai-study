import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../data/mock_recommendations_repository.dart';
import '../domain/music_recommendation.dart';

final recommendationsRepositoryProvider =
    Provider<MockRecommendationsRepository>(
  (ref) => const MockRecommendationsRepository(),
);

final recommendationControllerProvider =
    StateNotifierProvider<RecommendationController, RecommendationState>(
  (ref) {
    final repository = ref.watch(recommendationsRepositoryProvider);
    return RecommendationController(repository.fetchInitial());
  },
);

class RecommendationState {
  const RecommendationState({
    required this.queue,
    this.unsureStreak = 0,
    this.savedIds = const {},
    this.lastReaction,
  });

  final List<MusicRecommendation> queue;
  final int unsureStreak;
  final Set<String> savedIds;
  final RecommendationReaction? lastReaction;

  MusicRecommendation? get current => queue.isEmpty ? null : queue.first;
  bool get shouldAskFollowUp => unsureStreak >= 3;

  RecommendationState copyWith({
    List<MusicRecommendation>? queue,
    int? unsureStreak,
    Set<String>? savedIds,
    RecommendationReaction? lastReaction,
  }) {
    return RecommendationState(
      queue: queue ?? this.queue,
      unsureStreak: unsureStreak ?? this.unsureStreak,
      savedIds: savedIds ?? this.savedIds,
      lastReaction: lastReaction ?? this.lastReaction,
    );
  }
}

class RecommendationController extends StateNotifier<RecommendationState> {
  RecommendationController(List<MusicRecommendation> initialQueue)
      : super(RecommendationState(queue: initialQueue));

  void react(RecommendationReaction reaction) {
    final current = state.current;
    if (current == null) {
      return;
    }

    final nextQueue = state.queue.skip(1).toList();
    final nextSavedIds = {...state.savedIds};
    if (reaction == RecommendationReaction.save) {
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
  }

  void dismissFollowUp() {
    state = state.copyWith(unsureStreak: 0);
  }
}
