import 'package:flutter/material.dart';

import '../../domain/music_recommendation.dart';

class MusicCard extends StatelessWidget {
  const MusicCard({
    required this.recommendation,
    required this.isTopCard,
    required this.onDismissed,
    super.key,
  });

  final MusicRecommendation recommendation;
  final bool isTopCard;
  final ValueChanged<RecommendationReaction> onDismissed;

  @override
  Widget build(BuildContext context) {
    final card = ClipRRect(
      borderRadius: BorderRadius.circular(30),
      child: Stack(
        fit: StackFit.expand,
        children: [
          Image.network(
            recommendation.albumArtUrl,
            fit: BoxFit.cover,
            errorBuilder: (context, error, stackTrace) {
              return ColoredBox(
                color: Theme.of(context).colorScheme.surfaceContainerHighest,
                child: const Icon(Icons.album, size: 72),
              );
            },
          ),
          const DecoratedBox(
            decoration: BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topCenter,
                end: Alignment.bottomCenter,
                colors: [
                  Color(0x111B120C),
                  Color(0xAA2F2018),
                ],
              ),
            ),
          ),
          Positioned(
            left: 18,
            right: 18,
            bottom: 18,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  recommendation.contextLabel,
                  style: Theme.of(context).textTheme.labelLarge?.copyWith(
                        color: const Color(0xFFFFEFD7),
                        fontWeight: FontWeight.w700,
                      ),
                ),
                const SizedBox(height: 8),
                Text(
                  recommendation.title,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                        color: Colors.white,
                        fontWeight: FontWeight.w800,
                      ),
                ),
                const SizedBox(height: 4),
                Text(
                  recommendation.artist,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        color: Colors.white70,
                      ),
                ),
                const SizedBox(height: 14),
                _PreviewControl(label: recommendation.previewDescription),
              ],
            ),
          ),
          Positioned(
            top: 12,
            right: 12,
            child: IconButton.filledTonal(
              tooltip: '원곡 열기',
              onPressed: () {},
              icon: const Icon(Icons.open_in_new),
            ),
          ),
        ],
      ),
    );

    if (!isTopCard) {
      return IgnorePointer(child: card);
    }

    return Dismissible(
      key: ValueKey(recommendation.id),
      direction: DismissDirection.horizontal,
      onDismissed: (direction) {
        final reaction = direction == DismissDirection.endToStart
            ? RecommendationReaction.unsure
            : RecommendationReaction.like;
        onDismissed(reaction);
      },
      child: card,
    );
  }
}

class _PreviewControl extends StatefulWidget {
  const _PreviewControl({required this.label});

  final String label;

  @override
  State<_PreviewControl> createState() => _PreviewControlState();
}

class _PreviewControlState extends State<_PreviewControl> {
  bool isPlaying = true;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 48,
      padding: const EdgeInsets.symmetric(horizontal: 12),
      decoration: BoxDecoration(
        color: const Color(0xFFFFFBF4).withValues(alpha: 0.18),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: Colors.white.withValues(alpha: 0.18)),
      ),
      child: Row(
        children: [
          IconButton(
            tooltip: isPlaying ? '미리듣기 일시정지' : '미리듣기 재생',
            onPressed: () => setState(() => isPlaying = !isPlaying),
            icon: Icon(isPlaying ? Icons.pause : Icons.play_arrow),
            color: const Color(0xFFFFF7EA),
          ),
          Expanded(
            child: Text(
              widget.label,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(
                color: Color(0xFFFFF7EA),
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
