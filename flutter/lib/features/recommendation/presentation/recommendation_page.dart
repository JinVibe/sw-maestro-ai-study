import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../domain/music_recommendation.dart';
import 'recommendation_controller.dart';
import 'widgets/music_card.dart';
import 'widgets/reaction_bar.dart';

class RecommendationPage extends ConsumerWidget {
  const RecommendationPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(recommendationControllerProvider);
    final controller = ref.read(recommendationControllerProvider.notifier);

    ref.listen(recommendationControllerProvider, (previous, next) {
      if (next.shouldAskFollowUp && previous?.shouldAskFollowUp != true) {
        _showFollowUpSheet(context, controller);
      }
    });

    return Scaffold(
      appBar: AppBar(
        title: const Text('오늘의 추천'),
        actions: [
          IconButton(
            tooltip: '보관함',
            onPressed: () {},
            icon: const Icon(Icons.bookmarks_outlined),
          ),
        ],
      ),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(
                '최근 취향과 분위기에 맞춰 고른 음악입니다.',
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                      color: const Color(0xFF6E6E73),
                    ),
              ),
              const SizedBox(height: 16),
              Expanded(
                child: _RecommendationStack(
                  recommendations: state.queue,
                  onSwiped: controller.react,
                ),
              ),
              const SizedBox(height: 16),
              ReactionBar(onReact: controller.react),
            ],
          ),
        ),
      ),
    );
  }

  Future<void> _showFollowUpSheet(
    BuildContext context,
    RecommendationController controller,
  ) {
    return showModalBottomSheet<void>(
      context: context,
      showDragHandle: true,
      builder: (context) {
        return Padding(
          padding: const EdgeInsets.fromLTRB(20, 8, 20, 24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(
                '다음 추천 조정하기',
                style: Theme.of(context).textTheme.titleLarge,
              ),
              const SizedBox(height: 8),
              const Text('이번 추천에서 어떤 점이 아쉬웠나요?'),
              const SizedBox(height: 16),
              TextField(
                minLines: 2,
                maxLines: 4,
                decoration: InputDecoration(
                  hintText: '분위기, 장르, 템포, 좋아하는 아티스트 등',
                  filled: true,
                  fillColor: const Color(0xFFF5F5F7),
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(14),
                    borderSide: BorderSide.none,
                  ),
                ),
              ),
              const SizedBox(height: 16),
              FilledButton(
                onPressed: () {
                  controller.dismissFollowUp();
                  Navigator.of(context).pop();
                },
                child: const Text('반영하기'),
              ),
            ],
          ),
        );
      },
    );
  }
}

class _RecommendationStack extends StatelessWidget {
  const _RecommendationStack({
    required this.recommendations,
    required this.onSwiped,
  });

  final List<MusicRecommendation> recommendations;
  final ValueChanged<RecommendationReaction> onSwiped;

  @override
  Widget build(BuildContext context) {
    if (recommendations.isEmpty) {
      return const Center(
        child: Text('추천이 모두 끝났습니다. 잠시 후 다시 확인해 주세요.'),
      );
    }

    final visible = recommendations.take(3).toList().reversed.toList();

    return Stack(
      alignment: Alignment.center,
      children: [
        for (var index = 0; index < visible.length; index++)
          Positioned.fill(
            top: 16.0 * index,
            child: Transform.scale(
              scale: 1 - (visible.length - index - 1) * 0.04,
              child: MusicCard(
                recommendation: visible[index],
                isTopCard: index == visible.length - 1,
                onDismissed: onSwiped,
              ),
            ),
          ),
      ],
    );
  }
}
