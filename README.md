# 윤슬 (Elena) — AI 컴패니언 백엔드

> 27살 디자이너 출신 윤슬과 1:1로 대화하는 AI 컴패니언 서비스

---

## 핵심 기능

### 💬 자연스러운 대화
부산 광안리에서 번아웃 회복 중인 윤슬과 친구처럼 대화합니다.
반말, 이모지, 솔직한 감정 표현이 특징입니다.

### 🧠 장기 기억
이전 대화에서 나눴던 취향, 감정, 중요한 사실을 기억하고 자연스럽게 대화에 녹여냅니다.
"지난번에 말했잖아"가 아니라, 그냥 알고 있는 친구처럼 반응합니다.

### 📸 능동적 셀카
윤슬이 예쁜 노을을 봤을 때, 카페에 왔을 때 먼저 사진을 보내옵니다.
사진을 요청해도 되고, 자연스럽게 받을 수도 있습니다.

### 😊 감정 인식
대화 맥락에 따라 윤슬의 감정 상태가 변하고 (happy / calm / anxious / nostalgic / excited / sad),
응답 톤과 이미지 스타일에 반영됩니다.

---

## 기술 스택

| 영역 | 사용 기술 |
|------|-----------|
| API 서버 | FastAPI + uvicorn |
| 대화 파이프라인 | LangGraph |
| LLM | OpenAI GPT-4o-mini (테스트단계) |
| 임베딩 | OpenAI text-embedding-3-small (테스트단계) |
| 데이터베이스 | PostgreSQL + pgvector |
| 이미지 생성 | fal.ai (flux/schnell) (테스트단계) |
| 컨테이너 | Docker / Docker Compose |

---

## 빠른 시작

### 1. 환경 변수 설정

```bash
cp .env.example .env
```

`.env` 파일에 아래 값을 채워주세요.

```env
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
DATABASE_URL=postgresql://elena:elena@postgres:5432/elena
FAL_KEY=...
```

### 2. 실행

```bash
docker compose up -d
```

PostgreSQL 초기화 + 앱 빌드가 자동으로 진행됩니다.

### 3. 확인

```bash
curl http://localhost:8000/health
# {"status":"healthy","persona":"윤슬"}
```

---

## API

API 문서는 서버 실행 후 아래에서 확인할 수 있습니다.

```
http://localhost:8000/docs
```

### 주요 엔드포인트

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `POST` | `/api/v1/chat` | 윤슬에게 메시지 전송 |
| `GET` | `/api/v1/chat/{session_id}/history` | 대화 히스토리 조회 |
| `DELETE` | `/api/v1/chat/{session_id}` | 세션 종료 |

### 예시

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user-001",
    "message": "안녕! 오늘 뭐 했어?"
  }'
```

```json
{
  "message": "오늘 바다 보면서 멍 때렸어 🌊 파도 소리 들으니까 진짜 힐링되더라",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "image_url": null,
  "emotion": "calm"
}
```

---

## 프로젝트 구조

```
app/
├── api/routes/     # API 엔드포인트
├── core/           # LangGraph 파이프라인 & 페르소나
├── db/             # PostgreSQL Repository
├── schemas/        # Pydantic 모델
└── services/       # 비즈니스 로직 (대화, 기억, 이미지)
```

---

## 응답 시간 목표

| 상황 | 목표 |
|------|------|
| 텍스트 응답 | < 5초 |
| 셀카 포함 응답 | < 10초 |
