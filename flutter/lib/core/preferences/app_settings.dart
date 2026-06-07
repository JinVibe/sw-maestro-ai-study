import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../notifications/notification_service.dart';

final appSettingsControllerProvider =
    StateNotifierProvider<AppSettingsController, AppSettingsState>(
  (ref) => AppSettingsController(),
);

class AppSettingsState {
  const AppSettingsState({
    this.isLoaded = false,
    this.onboardingComplete = false,
    this.ageGroup = '',
    this.genres = const [],
    this.favoriteArtists = '',
    this.reminderHour = 19,
    this.reminderMinute = 0,
  });

  final bool isLoaded;
  final bool onboardingComplete;
  final String ageGroup;
  final List<String> genres;
  final String favoriteArtists;
  final int reminderHour;
  final int reminderMinute;

  int get age {
    final match = RegExp(r'\d+').firstMatch(ageGroup);
    final decade = int.tryParse(match?.group(0) ?? '') ?? 20;
    return decade >= 50 ? 55 : decade + 5;
  }

  List<String> get favoriteArtistList {
    return favoriteArtists
        .split(RegExp(r'[,，/]'))
        .map((artist) => artist.trim())
        .where((artist) => artist.isNotEmpty)
        .toList();
  }

  String get reminderLabel {
    final period = reminderHour < 12 ? '오전' : '오후';
    final hour = reminderHour % 12 == 0 ? 12 : reminderHour % 12;
    final minute = reminderMinute.toString().padLeft(2, '0');
    return '$period $hour:$minute';
  }

  AppSettingsState copyWith({
    bool? isLoaded,
    bool? onboardingComplete,
    String? ageGroup,
    List<String>? genres,
    String? favoriteArtists,
    int? reminderHour,
    int? reminderMinute,
  }) {
    return AppSettingsState(
      isLoaded: isLoaded ?? this.isLoaded,
      onboardingComplete: onboardingComplete ?? this.onboardingComplete,
      ageGroup: ageGroup ?? this.ageGroup,
      genres: genres ?? this.genres,
      favoriteArtists: favoriteArtists ?? this.favoriteArtists,
      reminderHour: reminderHour ?? this.reminderHour,
      reminderMinute: reminderMinute ?? this.reminderMinute,
    );
  }
}

class AppSettingsController extends StateNotifier<AppSettingsState> {
  AppSettingsController() : super(const AppSettingsState()) {
    _load();
  }

  static const _onboardingCompleteKey = 'onboarding_complete';
  static const _ageGroupKey = 'age_group';
  static const _genresKey = 'genres';
  static const _favoriteArtistsKey = 'favorite_artists';
  static const _reminderHourKey = 'reminder_hour';
  static const _reminderMinuteKey = 'reminder_minute';

  Future<void> _load() async {
    final prefs = await SharedPreferences.getInstance();
    final next = AppSettingsState(
      isLoaded: true,
      onboardingComplete: prefs.getBool(_onboardingCompleteKey) ?? false,
      ageGroup: prefs.getString(_ageGroupKey) ?? '',
      genres: prefs.getStringList(_genresKey) ?? const [],
      favoriteArtists: prefs.getString(_favoriteArtistsKey) ?? '',
      reminderHour: prefs.getInt(_reminderHourKey) ?? 19,
      reminderMinute: prefs.getInt(_reminderMinuteKey) ?? 0,
    );

    state = next;
    await NotificationService.instance.scheduleDailyRecommendationReminder(
      hour: next.reminderHour,
      minute: next.reminderMinute,
    );
  }

  Future<void> completeOnboarding({
    required String ageGroup,
    required List<String> genres,
    required String favoriteArtists,
  }) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_onboardingCompleteKey, true);
    await prefs.setString(_ageGroupKey, ageGroup);
    await prefs.setStringList(_genresKey, genres);
    await prefs.setString(_favoriteArtistsKey, favoriteArtists);

    state = state.copyWith(
      onboardingComplete: true,
      ageGroup: ageGroup,
      genres: genres,
      favoriteArtists: favoriteArtists,
    );
  }

  Future<void> updateReminderTime({
    required int hour,
    required int minute,
  }) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setInt(_reminderHourKey, hour);
    await prefs.setInt(_reminderMinuteKey, minute);
    await NotificationService.instance.scheduleDailyRecommendationReminder(
      hour: hour,
      minute: minute,
    );

    state = state.copyWith(reminderHour: hour, reminderMinute: minute);
  }
}
