import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/preferences/app_settings.dart';

class OnboardingPage extends ConsumerStatefulWidget {
  const OnboardingPage({super.key});

  @override
  ConsumerState<OnboardingPage> createState() => _OnboardingPageState();
}

class _OnboardingPageState extends ConsumerState<OnboardingPage> {
  final _artistController = TextEditingController();
  String _ageGroup = '20대';
  final Set<String> _genres = {'인디'};

  static const _ageGroups = ['10대', '20대', '30대', '40대', '50대 이상'];
  static const _genreOptions = [
    '인디',
    '발라드',
    '알앤비',
    '힙합',
    '재즈',
    '시티팝',
    '락',
    '전자음악',
  ];

  @override
  void dispose() {
    _artistController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final canStart = _genres.isNotEmpty;

    return Scaffold(
      body: DecoratedBox(
        decoration: const BoxDecoration(
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
        child: SafeArea(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(22, 20, 22, 22),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text(
                  '취향을\n먼저 알려주세요',
                  style: Theme.of(context).textTheme.headlineLarge,
                ),
                const SizedBox(height: 10),
                Text(
                  '나이대, 좋아하는 장르와 가수를 바탕으로 첫 추천을 준비할게요.',
                  style: Theme.of(context).textTheme.bodyMedium,
                ),
                const SizedBox(height: 26),
                Expanded(
                  child: ListView(
                    children: [
                      const _SectionTitle('나이대'),
                      const SizedBox(height: 10),
                      Wrap(
                        spacing: 8,
                        runSpacing: 8,
                        children: [
                          for (final age in _ageGroups)
                            ChoiceChip(
                              label: Text(age),
                              selected: _ageGroup == age,
                              onSelected: (_) => setState(() {
                                _ageGroup = age;
                              }),
                            ),
                        ],
                      ),
                      const SizedBox(height: 26),
                      const _SectionTitle('좋아하는 장르'),
                      const SizedBox(height: 10),
                      Wrap(
                        spacing: 8,
                        runSpacing: 8,
                        children: [
                          for (final genre in _genreOptions)
                            FilterChip(
                              label: Text(genre),
                              selected: _genres.contains(genre),
                              onSelected: (selected) => setState(() {
                                if (selected) {
                                  _genres.add(genre);
                                } else {
                                  _genres.remove(genre);
                                }
                              }),
                            ),
                        ],
                      ),
                      const SizedBox(height: 26),
                      const _SectionTitle('좋아하는 가수'),
                      const SizedBox(height: 10),
                      TextField(
                        controller: _artistController,
                        decoration: InputDecoration(
                          hintText: '예: 아이유, 검정치마, NewJeans',
                          filled: true,
                          fillColor:
                              const Color(0xFFFFFBF4).withValues(alpha: 0.84),
                          border: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(20),
                            borderSide: BorderSide.none,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
                FilledButton(
                  onPressed: canStart ? _completeOnboarding : null,
                  child: const Text('추천 시작하기'),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Future<void> _completeOnboarding() async {
    await ref.read(appSettingsControllerProvider.notifier).completeOnboarding(
          ageGroup: _ageGroup,
          genres: _genres.toList(),
          favoriteArtists: _artistController.text.trim(),
        );
  }
}

class _SectionTitle extends StatelessWidget {
  const _SectionTitle(this.text);

  final String text;

  @override
  Widget build(BuildContext context) {
    return Text(
      text,
      style: const TextStyle(
        color: Color(0xFF6E594A),
        fontSize: 15,
        fontWeight: FontWeight.w800,
      ),
    );
  }
}
