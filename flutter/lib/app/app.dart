import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/preferences/app_settings.dart';
import '../core/theme/app_theme.dart';
import '../features/onboarding/presentation/onboarding_page.dart';
import '../features/recommendation/presentation/recommendation_page.dart';

class MaestroMusicApp extends ConsumerWidget {
  const MaestroMusicApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final settings = ref.watch(appSettingsControllerProvider);

    return MaterialApp(
      title: '오늘의 음악 추천',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light,
      home: !settings.isLoaded
          ? const _LoadingPage()
          : settings.onboardingComplete
              ? const RecommendationPage()
              : const OnboardingPage(),
    );
  }
}

class _LoadingPage extends StatelessWidget {
  const _LoadingPage();

  @override
  Widget build(BuildContext context) {
    return const Scaffold(
      body: DecoratedBox(
        decoration: BoxDecoration(
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
        child: Center(child: CircularProgressIndicator()),
      ),
    );
  }
}
