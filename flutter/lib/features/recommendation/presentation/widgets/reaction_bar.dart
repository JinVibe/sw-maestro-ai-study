import 'package:flutter/material.dart';

import '../../domain/music_recommendation.dart';

class ReactionBar extends StatelessWidget {
  const ReactionBar({required this.onReact, super.key});

  final ValueChanged<RecommendationReaction> onReact;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(6),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.82),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: const Color(0xFFE5E5EA)),
      ),
      child: Row(
        children: [
          Expanded(
            child: OutlinedButton.icon(
              onPressed: () => onReact(RecommendationReaction.unsure),
              icon: const Icon(Icons.help_outline),
              label: const Text('잘 모르겠어요'),
            ),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: OutlinedButton.icon(
              onPressed: () => onReact(RecommendationReaction.save),
              icon: const Icon(Icons.bookmark_add_outlined),
              label: const Text('보관'),
            ),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: FilledButton.icon(
              onPressed: () => onReact(RecommendationReaction.like),
              icon: const Icon(Icons.favorite_outline),
              label: const Text('좋아요'),
            ),
          ),
        ],
      ),
    );
  }
}
