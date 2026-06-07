import 'package:flutter/material.dart';

class AppTheme {
  const AppTheme._();

  static ThemeData get light {
    const seed = Color(0xFFC98255);
    const ink = Color(0xFF3D3128);
    const muted = Color(0xFF8B7666);
    const surface = Color(0xFFFFF7EA);

    return ThemeData(
      useMaterial3: true,
      colorScheme: ColorScheme.fromSeed(
        seedColor: seed,
        brightness: Brightness.light,
        surface: surface,
      ),
      scaffoldBackgroundColor: const Color(0xFFF4E4CF),
      appBarTheme: const AppBarTheme(
        centerTitle: false,
        elevation: 0,
        titleTextStyle: TextStyle(
          color: ink,
          fontSize: 17,
          fontWeight: FontWeight.w700,
          fontFamilyFallback: ['Apple SD Gothic Neo', 'Noto Sans CJK KR'],
        ),
        backgroundColor: Colors.transparent,
        foregroundColor: ink,
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          minimumSize: const Size(56, 48),
          backgroundColor: const Color(0xFF3F6B5F),
          foregroundColor: const Color(0xFFFFFBF4),
          textStyle: const TextStyle(fontWeight: FontWeight.w700),
          shape:
              RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          minimumSize: const Size(56, 48),
          foregroundColor: ink,
          backgroundColor: const Color(0xFFFFFBF4),
          side: const BorderSide(color: Color(0xFFE8CFB5)),
          textStyle: const TextStyle(fontWeight: FontWeight.w700),
          shape:
              RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
        ),
      ),
      iconButtonTheme: IconButtonThemeData(
        style: IconButton.styleFrom(
          foregroundColor: ink,
          backgroundColor: const Color(0xFFFFFBF4).withValues(alpha: 0.72),
        ),
      ),
      textTheme: Typography.blackCupertino.apply(
        bodyColor: ink,
        displayColor: ink,
        fontFamilyFallback: const [
          'Apple SD Gothic Neo',
          'Noto Sans CJK KR',
          'Noto Sans KR',
          'Malgun Gothic',
        ],
      ).copyWith(
        headlineLarge: const TextStyle(
          fontSize: 34,
          height: 1.08,
          fontWeight: FontWeight.w800,
          letterSpacing: 0,
        ),
        headlineMedium: const TextStyle(
          fontSize: 30,
          height: 1.12,
          fontWeight: FontWeight.w800,
          letterSpacing: 0,
        ),
        titleLarge: const TextStyle(
          fontSize: 22,
          height: 1.2,
          fontWeight: FontWeight.w800,
          letterSpacing: 0,
        ),
        bodyMedium: const TextStyle(
          fontSize: 15,
          height: 1.45,
          color: muted,
          letterSpacing: 0,
        ),
      ),
    );
  }
}
