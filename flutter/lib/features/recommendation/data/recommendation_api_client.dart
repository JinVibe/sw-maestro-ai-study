import 'dart:convert';

import 'package:http/http.dart' as http;

import '../../../core/api/api_config.dart';
import '../../../core/api/api_exception.dart';
import '../domain/music_recommendation.dart';

class RecommendationApiClient {
  RecommendationApiClient({
    http.Client? httpClient,
    String baseUrl = ApiConfig.baseUrl,
  })  : _httpClient = httpClient ?? http.Client(),
        _baseUrl = Uri.parse(baseUrl);

  final http.Client _httpClient;
  final Uri _baseUrl;

  Future<SessionDto> createSession({
    required int age,
    required List<String> preferredGenres,
    required List<String> preferredArtists,
  }) async {
    final json = await _postJson('/sessions', {
      'age': age,
      'preferred_genres': preferredGenres,
      'preferred_artists': preferredArtists,
      'user_id': '',
    });

    return SessionDto.fromJson(json);
  }

  Future<BundleDto> recommend({
    required String sessionId,
    required String freeText,
  }) async {
    final json = await _postJson('/recommendations', {
      'session_id': sessionId,
      'free_text': freeText,
    });

    return BundleDto.fromJson(json);
  }

  Future<FeedbackDto> submitFeedback({
    required String sessionId,
    required String bundleId,
    required MusicRecommendation recommendation,
    required RecommendationReaction reaction,
  }) async {
    final json = await _postJson('/feedbacks', {
      'session_id': sessionId,
      'bundle_id': bundleId,
      'feedbacks': [
        {
          'song_id': recommendation.id,
          'title': recommendation.title,
          'artists': [recommendation.artist],
          'reaction': reaction == RecommendationReaction.like ? '좋아요' : '싫어요',
          'saved': reaction == RecommendationReaction.like,
        },
      ],
    });

    return FeedbackDto.fromJson(json);
  }

  Future<FollowUpDto> submitFollowUp({
    required String sessionId,
    required String text,
  }) async {
    final json = await _postJson('/sessions/$sessionId/follow-up', {
      'text': text,
    });

    return FollowUpDto.fromJson(json);
  }

  Future<List<MusicRecommendation>> fetchLibrary({
    required String sessionId,
  }) async {
    final uri =
        _baseUrl.replace(path: '${_baseUrl.path}/sessions/$sessionId/library');
    final response = await _httpClient.get(uri);
    final json = _decodeResponse(response);
    final songs = json['songs'] as List<dynamic>? ?? const [];
    return songs
        .whereType<Map<String, dynamic>>()
        .map(MusicRecommendation.fromApiJson)
        .toList();
  }

  Future<Map<String, dynamic>> _postJson(
    String path,
    Map<String, dynamic> body,
  ) async {
    final uri = _baseUrl.replace(path: '${_baseUrl.path}$path');
    final response = await _httpClient.post(
      uri,
      headers: const {'Content-Type': 'application/json; charset=utf-8'},
      body: jsonEncode(body),
    );

    return _decodeResponse(response);
  }

  Map<String, dynamic> _decodeResponse(http.Response response) {
    final decoded = jsonDecode(utf8.decode(response.bodyBytes));
    if (response.statusCode < 200 || response.statusCode >= 300) {
      final detail = decoded is Map<String, dynamic> ? decoded['detail'] : null;
      throw ApiException(
        detail?.toString() ?? 'API 요청에 실패했습니다.',
        statusCode: response.statusCode,
      );
    }
    if (decoded is! Map<String, dynamic>) {
      throw const ApiException('API 응답 형식이 올바르지 않습니다.');
    }
    return decoded;
  }
}

class SessionDto {
  const SessionDto({required this.sessionId});

  final String sessionId;

  factory SessionDto.fromJson(Map<String, dynamic> json) {
    return SessionDto(sessionId: json['session_id']?.toString() ?? '');
  }
}

class BundleDto {
  const BundleDto({
    required this.bundleId,
    required this.emotionTitle,
    required this.songs,
  });

  final String bundleId;
  final String emotionTitle;
  final List<MusicRecommendation> songs;

  factory BundleDto.fromJson(Map<String, dynamic> json) {
    final songs = json['songs'] as List<dynamic>? ?? const [];
    return BundleDto(
      bundleId: json['bundle_id']?.toString() ?? '',
      emotionTitle: json['emotion_title']?.toString() ?? '',
      songs: songs
          .whereType<Map<String, dynamic>>()
          .map(MusicRecommendation.fromApiJson)
          .toList(),
    );
  }
}

class FeedbackDto {
  const FeedbackDto({
    required this.negativeCount,
    required this.nextAction,
  });

  final int negativeCount;
  final String nextAction;

  factory FeedbackDto.fromJson(Map<String, dynamic> json) {
    return FeedbackDto(
      negativeCount:
          int.tryParse(json['negative_count']?.toString() ?? '') ?? 0,
      nextAction: json['next_action']?.toString() ?? '',
    );
  }
}

class FollowUpDto {
  const FollowUpDto({required this.nextAction});

  final String nextAction;

  factory FollowUpDto.fromJson(Map<String, dynamic> json) {
    return FollowUpDto(nextAction: json['next_action']?.toString() ?? '');
  }
}
