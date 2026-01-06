# Security Feed

보안 취약점 피드를 수집하고 LLM으로 분석하여 관련 알림을 Slack으로 발송하는 자동화 도구입니다.

## 기능

- **피드 수집**: NVD CVE, The Hacker News, GitHub Security Advisory
- **스마트 필터링**: 설정한 기술 스택(whitelist) 기반으로 관련 항목만 선별
- **LLM 분석**: Google Gemma 모델로 영향받는 제품 추출 및 심각도 판단
- **Slack 알림**: Critical/High 심각도 항목을 한 번에 모아서 발송
- **중복 제거**: 이미 처리한 항목은 재알림하지 않음

## 설치

```bash
# 저장소 클론
git clone https://github.com/your-org/security-feed.git
cd security-feed

# 가상환경 생성 및 활성화
python3 -m venv .venv
source .venv/bin/activate

# 의존성 설치
pip install -r requirements.txt
```

## 설정

### 1. 환경변수 설정

```bash
cp .env.example .env
```

`.env` 파일을 편집하여 필요한 값을 입력합니다:

| 환경변수 | 필수 | 설명 |
|----------|------|------|
| `GOOGLE_API_KEY` | O | Google AI Studio API 키 ([발급](https://aistudio.google.com/app/apikey)) |
| `GITHUB_TOKEN` | O | GitHub Personal Access Token ([발급](https://github.com/settings/tokens)) |
| `SLACK_WEBHOOK_URL` | O | Slack Incoming Webhook URL ([생성](https://api.slack.com/messaging/webhooks)) |
| `SLACK_MENTION_USERS` | X | 알림 시 멘션할 사용자 (콤마 구분) |

### 2. 설정 파일 생성

```bash
cp config.yaml.example config.yaml
```

### 3. 기술 스택 설정 (Whitelist)

`config.yaml`의 `whitelist` 섹션에 모니터링할 기술 스택을 설정합니다.
**whitelist에 있는 제품과 관련된 보안 이슈만 알림**을 받게 됩니다.

#### 기술 스택 확인 방법

Claude Code 등 AI 도구로 인프라 전체를 분석하여 whitelist를 구성할 수 있습니다:

| 소스 | 확인 대상 |
|------|----------|
| 코드 저장소 | package.json, build.gradle, requirements.txt 등 |
| kubectl | 클러스터 내 워크로드, 이미지 |
| AWS/GCP CLI | RDS, ElastiCache, MSK, EKS 등 |
| 보안장비 API | FortiGate, ESET, Wazuh 등 |
| 자체 호스팅 앱 | n8n, Grafana, Metabase 등 |

**상세 가이드 및 예시 프롬프트:** [docs/whitelist-setup-guide.md](docs/whitelist-setup-guide.md)

#### Whitelist 예시

```yaml
whitelist:
  # 프레임워크
  backend:
    - nestjs
    - spring boot
    - express
    - fastapi

  # 데이터베이스/캐시
  database:
    - mysql
    - postgresql
    - redis
    - elasticsearch
    - mongodb

  # 인프라
  infra:
    - kubernetes
    - docker
    - nginx
    - aws eks

  # 모니터링
  monitoring:
    - prometheus
    - grafana
```

> **Tip**: 제품명은 소문자로, 공식 명칭을 사용하세요. (예: `next.js`, `spring boot`)

### 4. LLM 모델 변경 (선택사항)

`config.yaml`의 `llm.model`을 수정하여 다른 모델을 사용할 수 있습니다:

```yaml
llm:
  model: "gemma-3-12b-it"  # 기본값
```

**사용 가능한 모델:**

| 모델 | 크기 | 특징 |
|------|------|------|
| `gemma-3-4b-it` | 4B | 가볍고 빠름 |
| `gemma-3-12b-it` | 12B | 균형 잡힌 성능 (권장) |
| `gemma-3-27b-it` | 27B | 높은 정확도, 느림 |
| `gemini-2.0-flash` | - | 빠른 응답, 무료 |

## 사용법

### 기본 실행

```bash
source .venv/bin/activate
source .env  # 또는 export로 환경변수 설정
python main.py
```

### 옵션

```bash
# 테스트 실행 (Slack 발송 없이)
python main.py --dry-run

# 상세 출력
python main.py --verbose

# 오래된 데이터 정리
python main.py --cleanup
```

### Cron 설정 (매시간 실행)

```bash
# run.sh 생성
cat > run.sh << 'EOF'
#!/bin/bash
cd /path/to/security-feed
source .venv/bin/activate
source .env
python main.py >> data/run.log 2>&1
EOF
chmod +x run.sh

# crontab 등록
crontab -e
# 추가: 0 * * * * /path/to/security-feed/run.sh
```

## 동작 방식

```
[1] 피드 수집 (NVD, THN, GitHub)
        ↓
[2] 중복 제거 (processed.json 기반)
        ↓
[3] 1차 필터링 (whitelist 키워드 + 보안 키워드 점수)
        ↓
[4] LLM 분석 (Gemma로 제품명 추출 → whitelist 매칭)
        ↓
[5] Slack 알림 (Critical/High만)
```

## 출력 예시

```
==================================================
[1/5] 피드 수집 중...
      수집 완료: 542개
[2/5] 중복 제거 중...
      신규 항목: 15개 (기존 527개 스킵)
[3/5] 필터링 중...
      LLM 분석 대상: 5개
[4/5] LLM 분석 중...
      관련 항목: 2개
[5/5] 알림 발송 중...
      알림 발송: 2건
==================================================
[완료] 파이프라인 실행 완료
       수집: 542 → 신규: 15 → 필터: 5 → LLM: 2 → 알림: 2
```

## 요구사항

- Python 3.9+
- Google AI API 키 (무료)
- GitHub Token
- Slack Webhook URL

## 라이선스

MIT License
