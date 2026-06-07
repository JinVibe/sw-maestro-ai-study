import 'dart:convert';

import 'package:http/http.dart' as http;

import '../../../core/api/api_config.dart';
import '../domain/music_recommendation.dart';

/// 추천 번들(백엔드 /recommendations 응답).
class RecommendationBundle {
  const RecommendationBundle({
    required this.bundleId,
    required this.emotionTitle,
    required this.songs,
    required this.nextAction,
  });

  final String bundleId;
  final String emotionTitle;
  final List<MusicRecommendation> songs;
  final String nextAction;
}

/// FastAPI 백엔드를 호출하는 추천 리포지토리.
///
/// 엔드포인트: POST /sessions, POST /recommendations, POST /feedbacks
class ApiRecommendationsRepository {
  ApiRecommendationsRepository({http.Client? client, String? baseUrl})
      : _client = client ?? http.Client(),
        _baseUrl = baseUrl ?? ApiConfig.baseUrl;

  final http.Client _client;
  final String _baseUrl;

  static const _jsonHeaders = {'Content-Type': 'application/json'};

  /// 온보딩 → 세션 생성. session_id 반환.
  Future<String> createSession({
    required int age,
    required List<String> genres,
    required List<String> artists,
  }) async {
    final res = await _client.post(
      Uri.parse('$_baseUrl/sessions'),
      headers: _jsonHeaders,
      body: jsonEncode({
        'age': age,
        'preferred_genres': genres,
        'preferred_artists': artists,
      }),
    );
    final json = _decode(res);
    return json['session_id'] as String;
  }

  /// 추천 요청 → 5곡 번들.
  Future<RecommendationBundle> recommend({
    required String sessionId,
    required String freeText,
    String followUpText = '',
  }) async {
    final res = await _client.post(
      Uri.parse('$_baseUrl/recommendations'),
      headers: _jsonHeaders,
      body: jsonEncode({
        'session_id': sessionId,
        'free_text': freeText,
        'follow_up_text': followUpText,
      }),
    );
    final json = _decode(res);
    final emotionTitle = json['emotion_title'] as String? ?? '';
    final songs = (json['songs'] as List<dynamic>? ?? <dynamic>[])
        .map((e) => _songFromJson(e as Map<String, dynamic>, emotionTitle))
        .toList();
    return RecommendationBundle(
      bundleId: json['bundle_id'] as String? ?? '',
      emotionTitle: emotionTitle,
      songs: songs,
      nextAction: json['next_action'] as String? ?? '',
    );
  }

  /// 곡별 피드백 전송 → next_action 반환.
  Future<String> sendFeedback({
    required String sessionId,
    required String bundleId,
    required List<Map<String, dynamic>> feedbacks,
  }) async {
    final res = await _client.post(
      Uri.parse('$_baseUrl/feedbacks'),
      headers: _jsonHeaders,
      body: jsonEncode({
        'session_id': sessionId,
        'bundle_id': bundleId,
        'feedbacks': feedbacks,
      }),
    );
    final json = _decode(res);
    return json['next_action'] as String? ?? '';
  }

  MusicRecommendation _songFromJson(
    Map<String, dynamic> json,
    String emotionTitle,
  ) {
    final artists = (json['artists'] as List<dynamic>? ?? <dynamic>[])
        .map((e) => e.toString())
        .where((e) => e.isNotEmpty)
        .toList();
    final title = json['title'] as String? ?? '';
    final reason = json['reason'] as String? ?? '';
    final previewUrl = json['preview_url'] as String? ?? '';
    final externalUrl = previewUrl.isNotEmpty
        ? Uri.parse(previewUrl)
        : Uri.parse(
            'https://music.youtube.com/search?q='
            '${Uri.encodeComponent('$title ${artists.join(' ')}')}',
          );

    return MusicRecommendation(
      id: json['song_id'] as String? ?? '',
      title: title,
      artist: artists.join(', '),
      // 빈 값이면 카드 위젯의 errorBuilder가 앨범 아이콘으로 대체한다.
      albumArtUrl: json['album_art_url'] as String? ?? '',
      contextLabel: reason.isNotEmpty ? reason : emotionTitle,
      previewDescription:
          previewUrl.isNotEmpty ? '30초 미리듣기 준비됨' : '미리듣기 준비 중',
      externalUrl: externalUrl,
    );
  }

  Map<String, dynamic> _decode(http.Response res) {
    if (res.statusCode < 200 || res.statusCode >= 300) {
      throw Exception('API ${res.statusCode}: ${utf8.decode(res.bodyBytes)}');
    }
    return jsonDecode(utf8.decode(res.bodyBytes)) as Map<String, dynamic>;
  }
}
