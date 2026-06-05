class MusicRecommendation {
  const MusicRecommendation({
    required this.id,
    required this.title,
    required this.artist,
    required this.albumArtUrl,
    required this.contextLabel,
    required this.previewDescription,
    required this.externalUrl,
  });

  final String id;
  final String title;
  final String artist;
  final String albumArtUrl;
  final String contextLabel;
  final String previewDescription;
  final Uri externalUrl;
}

enum RecommendationReaction {
  like,
  save,
  unsure,
}
