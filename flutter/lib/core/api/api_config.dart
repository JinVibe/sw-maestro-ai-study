/// 백엔드 API 베이스 URL.
///
/// 실행 시 덮어쓰기:
///   flutter run --dart-define=API_BASE_URL=http://192.168.0.10:8000
///
/// 기본값 메모:
///   - Android 에뮬레이터: http://10.0.2.2:8000 (호스트의 localhost)
///   - iOS 시뮬레이터/웹/데스크톱: http://127.0.0.1:8000
class ApiConfig {
  const ApiConfig._();

  static const String baseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://10.0.2.2:8000',
  );
}
