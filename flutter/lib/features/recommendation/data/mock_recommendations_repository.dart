import '../domain/music_recommendation.dart';

class MockRecommendationsRepository {
  const MockRecommendationsRepository();

  List<MusicRecommendation> fetchInitial() {
    return [
      MusicRecommendation(
        id: 'rec-001',
        title: '밤의 드라이브',
        artist: '아리 베일',
        albumArtUrl:
            'https://images.unsplash.com/photo-1493225457124-a3eb161ffa5f'
            '?auto=format&fit=crop&w=1200&q=80',
        contextLabel: '늦은 밤에 어울리는 신스 무드',
        previewDescription: '30초 미리듣기 준비됨',
        externalUrl: Uri.parse('https://music.youtube.com/'),
      ),
      MusicRecommendation(
        id: 'rec-002',
        title: '창가 자리',
        artist: '더 노스라인',
        albumArtUrl:
            'https://images.unsplash.com/photo-1516280440614-37939bbacd81'
            '?auto=format&fit=crop&w=1200&q=80',
        contextLabel: '조용한 이동 시간에 듣기 좋은 인디팝',
        previewDescription: '탭해서 미리듣기 일시정지',
        externalUrl: Uri.parse('https://music.youtube.com/'),
      ),
      MusicRecommendation(
        id: 'rec-003',
        title: '작은 날씨',
        artist: '미나 코스트',
        albumArtUrl:
            'https://images.unsplash.com/photo-1500530855697-b586d89ba3ee'
            '?auto=format&fit=crop&w=1200&q=80',
        contextLabel: '부드럽게 리셋하는 어쿠스틱',
        previewDescription: '백엔드에서 생성한 미리듣기',
        externalUrl: Uri.parse('https://music.youtube.com/'),
      ),
    ];
  }
}
