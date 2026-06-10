# 빌드 컨텍스트는 repo 루트여야 한다(ai/ 와 backend/ 둘 다 필요).
#   docker build -f backend/Dockerfile -t soma-backend .
# 또는 backend/docker-compose.yml 사용(context: ..).
FROM python:3.11-slim

WORKDIR /srv

# 1) 의존성 먼저 설치(레이어 캐시)
COPY backend/requirements.txt /srv/backend/requirements.txt
RUN pip install --no-cache-dir -r /srv/backend/requirements.txt

# 2) 추천 AI 모듈 + 백엔드 소스 복사
COPY ai /srv/ai
COPY backend /srv/backend

# app(=/srv/backend) 와 ai(=/srv) 둘 다 import 가능하게
ENV PYTHONPATH=/srv/backend:/srv
ENV CATALOG_PATH=ai/data/raw/melon_kpop_2000_2025.jsonl
ENV PORT=8000

EXPOSE 8000

# 헬스체크
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python3 -c "import urllib.request,os; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"8000\")}/health')" || exit 1

CMD ["sh", "-c", "uvicorn app.main:app --app-dir /srv/backend --host 0.0.0.0 --port ${PORT}"]
