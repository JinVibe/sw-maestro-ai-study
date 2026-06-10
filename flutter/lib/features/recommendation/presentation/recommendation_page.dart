import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/preferences/app_settings.dart';
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
    final settings = ref.watch(appSettingsControllerProvider);
    final settingsController = ref.read(appSettingsControllerProvider.notifier);

    ref.listen(recommendationControllerProvider, (previous, next) {
      if (next.shouldAskFollowUp && previous?.shouldAskFollowUp != true) {
        _showFollowUpSheet(context, controller);
      }
    });

    return Scaffold(
      extendBodyBehindAppBar: true,
      appBar: AppBar(
        title: const Text('Oh my memory'),
        actions: [
          Padding(
            padding: const EdgeInsets.only(right: 10),
            child: IconButton(
              tooltip: '보관함',
              onPressed: () async {
                await controller.refreshLibrary();
                if (!context.mounted) {
                  return;
                }
                final saved = ref
                    .read(recommendationControllerProvider)
                    .savedRecommendations;
                _showSavedSheet(context, saved);
              },
              icon: const Icon(Icons.bookmarks_outlined),
            ),
          ),
        ],
      ),
      body: DecoratedBox(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [
              Color(0xFFF1D5B8),
              Color(0xFFF7E8D3),
              Color(0xFFFFF8ED),
            ],
          ),
        ),
        child: SafeArea(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(18, 12, 18, 18),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                _WarmHeader(
                  reminderLabel: settings.reminderLabel,
                  onReminderTap: () => _pickReminderTime(
                    context,
                    settings.reminderHour,
                    settings.reminderMinute,
                    settingsController,
                  ),
                ),
                const SizedBox(height: 18),
                Text(
                  state.emotionTitle.isEmpty
                      ? '하루가 느슨해지는 시간에 맞춰, 오늘의 분위기와 어울리는 곡을 골랐어요.'
                      : state.emotionTitle,
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                        color: const Color(0xFF8B7666),
                      ),
                ),
                if (state.errorMessage.isNotEmpty) ...[
                  const SizedBox(height: 10),
                  _ErrorBanner(
                    message: state.errorMessage,
                    onRetry: () async {
                      if (state.sessionId.isEmpty) {
                        await controller.initialize();
                      } else {
                        await controller.loadRecommendations();
                      }
                    },
                  ),
                ],
                const SizedBox(height: 16),
                Expanded(
                  child: state.isLoading
                      ? const _MemorySearchLoading()
                      : _RecommendationStack(
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
      ),
    );
  }

  Future<void> _pickReminderTime(
    BuildContext context,
    int initialHour,
    int initialMinute,
    AppSettingsController controller,
  ) async {
    final picked = await showTimePicker(
      context: context,
      initialTime: TimeOfDay(hour: initialHour, minute: initialMinute),
      helpText: '알림 받을 시간',
      cancelText: '취소',
      confirmText: '저장',
    );

    if (picked == null) {
      return;
    }

    await controller.updateReminderTime(
      hour: picked.hour,
      minute: picked.minute,
    );
  }

  Future<void> _showSavedSheet(
    BuildContext context,
    List<MusicRecommendation> savedRecommendations,
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
                '저장한 노래',
                style: Theme.of(context).textTheme.titleLarge,
              ),
              const SizedBox(height: 12),
              if (savedRecommendations.isEmpty)
                const Padding(
                  padding: EdgeInsets.symmetric(vertical: 20),
                  child: Text('아직 저장한 노래가 없습니다. 좋아요를 누르면 여기에 모여요.'),
                )
              else
                Flexible(
                  child: ListView.separated(
                    shrinkWrap: true,
                    itemCount: savedRecommendations.length,
                    separatorBuilder: (context, index) =>
                        const Divider(height: 1),
                    itemBuilder: (context, index) {
                      final recommendation = savedRecommendations[index];
                      return ListTile(
                        contentPadding: EdgeInsets.zero,
                        leading: ClipRRect(
                          borderRadius: BorderRadius.circular(10),
                          child: Image.network(
                            recommendation.albumArtUrl,
                            width: 48,
                            height: 48,
                            fit: BoxFit.cover,
                          ),
                        ),
                        title: Text(recommendation.title),
                        subtitle: Text(recommendation.artist),
                      );
                    },
                  ),
                ),
            ],
          ),
        );
      },
    );
  }

  Future<void> _showFollowUpSheet(
    BuildContext context,
    RecommendationController controller,
  ) {
    final textController = TextEditingController();
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
                controller: textController,
                minLines: 2,
                maxLines: 4,
                decoration: InputDecoration(
                  hintText: '분위기, 장르, 템포, 좋아하는 아티스트 등',
                  filled: true,
                  fillColor: const Color(0xFFFFF8ED),
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(18),
                    borderSide: BorderSide.none,
                  ),
                ),
              ),
              const SizedBox(height: 16),
              FilledButton(
                onPressed: () async {
                  await controller.submitFollowUp(textController.text.trim());
                  if (!context.mounted) {
                    return;
                  }
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

class _ErrorBanner extends StatelessWidget {
  const _ErrorBanner({
    required this.message,
    required this.onRetry,
  });

  final String message;
  final Future<void> Function() onRetry;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: const Color(0xFFFFFBF4).withValues(alpha: 0.88),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: const Color(0xFFE8CFB5)),
      ),
      child: Row(
        children: [
          Expanded(
            child: Text(
              message,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(color: Color(0xFF8B4C3B)),
            ),
          ),
          TextButton(
            onPressed: () => onRetry(),
            child: const Text('재시도'),
          ),
        ],
      ),
    );
  }
}

class _MemorySearchLoading extends StatefulWidget {
  const _MemorySearchLoading();

  @override
  State<_MemorySearchLoading> createState() => _MemorySearchLoadingState();
}

class _MemorySearchLoadingState extends State<_MemorySearchLoading>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1800),
    )..repeat();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final textStyle = Theme.of(context).textTheme.titleMedium?.copyWith(
          color: const Color(0xFF6E594A),
          fontWeight: FontWeight.w800,
        );

    return Center(
      child: AnimatedBuilder(
        animation: _controller,
        builder: (context, child) {
          final dotCount = (_controller.value * 4).floor().clamp(0, 3).toInt();
          final animatedDots = List.filled(dotCount, '.').join();
          return Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Transform.rotate(
                angle: _controller.value * 6.283185307179586,
                child: Container(
                  width: 82,
                  height: 82,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: const Color(0xFFB78962),
                    boxShadow: [
                      BoxShadow(
                        color: const Color(0xFF8A5D3B).withValues(alpha: 0.18),
                        blurRadius: 22,
                        offset: const Offset(0, 12),
                      ),
                    ],
                  ),
                  child: Stack(
                    alignment: Alignment.center,
                    children: [
                      Container(
                        width: 52,
                        height: 52,
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          border: Border.all(
                            color:
                                const Color(0xFFFFF3DF).withValues(alpha: 0.52),
                            width: 2,
                          ),
                        ),
                      ),
                      Container(
                        width: 18,
                        height: 18,
                        decoration: const BoxDecoration(
                          shape: BoxShape.circle,
                          color: Color(0xFFFFF8ED),
                        ),
                      ),
                      Align(
                        alignment: const Alignment(0.55, -0.55),
                        child: Container(
                          width: 8,
                          height: 8,
                          decoration: const BoxDecoration(
                            shape: BoxShape.circle,
                            color: Color(0xFFFFF8ED),
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 22),
              Text(
                '당신의 추억을 DJ가 열심히 찾고 있는 중$animatedDots',
                textAlign: TextAlign.center,
                style: textStyle,
              ),
            ],
          );
        },
      ),
    );
  }
}

class _WarmHeader extends StatelessWidget {
  const _WarmHeader({
    required this.reminderLabel,
    required this.onReminderTap,
  });

  final String reminderLabel;
  final VoidCallback onReminderTap;

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.end,
      children: [
        Expanded(
          child: Text(
            '오늘의\n플레이리스트',
            style: Theme.of(context).textTheme.headlineLarge,
          ),
        ),
        InkWell(
          borderRadius: BorderRadius.circular(18),
          onTap: onReminderTap,
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
            decoration: BoxDecoration(
              color: const Color(0xFFFFFBF4).withValues(alpha: 0.74),
              borderRadius: BorderRadius.circular(18),
              border: Border.all(color: const Color(0xFFE8CFB5)),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Icon(Icons.notifications_none, size: 18),
                const SizedBox(width: 6),
                Text(
                  reminderLabel,
                  style: const TextStyle(
                    color: Color(0xFF6E594A),
                    fontSize: 13,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}

class _RecommendationStack extends StatelessWidget {
  const _RecommendationStack({
    required this.recommendations,
    required this.onSwiped,
  });

  final List<MusicRecommendation> recommendations;
  final Future<void> Function(RecommendationReaction reaction) onSwiped;

  @override
  Widget build(BuildContext context) {
    if (recommendations.isEmpty) {
      return const Center(
        child: Text('내일 다시 만나요!'),
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
