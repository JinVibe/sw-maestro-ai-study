import 'package:flutter/material.dart';

import '../core/theme/app_theme.dart';
import '../features/recommendation/presentation/recommendation_page.dart';

class MaestroMusicApp extends StatelessWidget {
  const MaestroMusicApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: '오늘의 음악 추천',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light,
      home: const RecommendationPage(),
    );
  }
}
