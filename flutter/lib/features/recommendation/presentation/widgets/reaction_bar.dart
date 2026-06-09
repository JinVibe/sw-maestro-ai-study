import 'package:flutter/material.dart';
import 'dart:async';

import '../../domain/music_recommendation.dart';

class ReactionBar extends StatelessWidget {
  const ReactionBar({required this.onReact, super.key});

  final Future<void> Function(RecommendationReaction reaction) onReact;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(6),
      decoration: BoxDecoration(
        color: const Color(0xFFFFFBF4).withValues(alpha: 0.82),
        borderRadius: BorderRadius.circular(24),
        border: Border.all(color: const Color(0xFFE8CFB5)),
        boxShadow: [
          BoxShadow(
            color: const Color(0xFF8A5D3B).withValues(alpha: 0.10),
            blurRadius: 22,
            offset: const Offset(0, 10),
          ),
        ],
      ),
      child: Row(
        children: [
          Expanded(
            child: OutlinedButton.icon(
              onPressed: () =>
                  unawaited(onReact(RecommendationReaction.unsure)),
              icon: const Icon(Icons.help_outline),
              label: const Text('글쎄요'),
            ),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: FilledButton.icon(
              onPressed: () => unawaited(onReact(RecommendationReaction.like)),
              icon: const Icon(Icons.favorite_outline),
              label: const Text('좋아요'),
            ),
          ),
        ],
      ),
    );
  }
}
