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

  factory MusicRecommendation.fromApiJson(Map<String, dynamic> json) {
    final artists = json['artists'] as List<dynamic>? ?? const [];
    final previewUrl = json['preview_url']?.toString() ?? '';
    final reason = json['reason']?.toString() ?? '';

    return MusicRecommendation(
      id: json['song_id']?.toString() ?? '',
      title: json['title']?.toString() ?? '제목 없음',
      artist: artists.map((artist) => artist.toString()).join(', '),
      albumArtUrl: json['album_art_url']?.toString() ?? '',
      contextLabel: json['slot_type']?.toString().isEmpty ?? true
          ? 'AI 추천'
          : json['slot_type'].toString(),
      previewDescription: reason.isEmpty ? '추천 이유 준비 중' : reason,
      externalUrl:
          Uri.tryParse(previewUrl) ?? Uri.parse('https://music.apple.com/'),
    );
  }
}

enum RecommendationReaction {
  like,
  unsure,
}
