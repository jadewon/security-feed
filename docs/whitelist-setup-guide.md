# Whitelist 설정 가이드

기술 스택을 확인하여 whitelist를 구성하는 방법입니다.

## 확인 소스

| 소스 | 확인 대상 |
|------|----------|
| 코드 저장소 | 의존성, 프레임워크 |
| kubectl | 클러스터 내 워크로드 |
| AWS/GCP CLI | 클라우드 서비스 |
| 보안장비 API | 방화벽, EDR 등 |

## Claude Code 활용

Claude Code로 codebase와 인프라를 분석하여 기술 스택을 추출할 수 있습니다.

### 예시 프롬프트

#### 1. 코드 저장소 분석

```
우리 회사 코드 저장소들을 분석해서 사용 중인 기술 스택을 정리해줘.

확인할 것:
- package.json (Node.js 의존성)
- build.gradle, pom.xml (Java/Kotlin 의존성)
- requirements.txt (Python 의존성)
- go.mod (Go 의존성)

출력 형식:
- 카테고리별로 분류 (backend, frontend, database, infra 등)
- 제품명은 공식 명칭 사용
```

#### 2. Kubernetes 클러스터 분석

```
kubectl로 현재 클러스터의 워크로드를 분석해서 사용 중인 기술 스택을 정리해줘.

확인할 것:
- 모든 namespace의 deployment, statefulset
- 사용 중인 이미지 목록
- helm release 목록

명령어 예시:
kubectl get deploy,sts -A -o jsonpath='{range .items[*]}{.spec.template.spec.containers[*].image}{"\n"}{end}'
helm list -A
```

#### 3. AWS 인프라 분석

```
AWS CLI로 사용 중인 서비스를 확인해서 정리해줘.

확인할 것:
- RDS (MySQL, PostgreSQL 등)
- ElastiCache (Redis, Memcached)
- MSK (Kafka)
- EKS
- Lambda 런타임
- etc.

명령어 예시:
aws rds describe-db-instances --query 'DBInstances[*].[DBInstanceIdentifier,Engine]'
aws elasticache describe-cache-clusters --query 'CacheClusters[*].[CacheClusterId,Engine]'
aws eks list-clusters
```

#### 4. GCP 인프라 분석

```
gcloud로 사용 중인 서비스를 확인해서 정리해줘.

확인할 것:
- Cloud SQL
- Memorystore
- GKE
- Cloud Run
- etc.

명령어 예시:
gcloud sql instances list
gcloud redis instances list --region=asia-northeast3
gcloud container clusters list
```

#### 5. 보안장비 분석

```
보안장비에서 관리 중인 정책을 분석해서 사용 중인 제품을 파악해줘.

FortiGate:
- SSH로 접속하여 설정 확인
- REST API로 정책 조회

ESET:
- 관리 콘솔 API로 설치된 제품 확인

Wazuh:
- 에이전트 목록 및 룰셋 확인
```

### 통합 분석 프롬프트

```
우리 인프라 전체를 분석해서 보안 모니터링이 필요한 기술 스택을 정리해줘.

분석 대상:
1. 코드 저장소 (~/Workspaces/** 내 모든 프로젝트)
2. Kubernetes 클러스터 (kubectl 사용)
3. AWS 서비스 (aws cli 사용)
4. 자체 호스팅 앱 (n8n, Grafana 등)
5. 보안 솔루션 (FortiGate, ESET 등)

출력:
- config.yaml의 whitelist 형식으로 출력
- 카테고리별 분류
- 중복 제거
```

## 출력 예시

```yaml
whitelist:
  backend:
    - nestjs
    - spring boot
    - express

  database:
    - mysql
    - redis
    - elasticsearch

  infra:
    - kubernetes
    - docker
    - nginx

  cloud:
    - aws eks
    - amazon rds
    - amazon msk

  security:
    - fortigate
    - wazuh
    - eset

  monitoring:
    - prometheus
    - grafana

  apps:
    - n8n
    - metabase
```

## 주의사항

- 제품명은 **소문자**로, **공식 명칭** 사용
- 버전 정보는 제외 (예: `nestjs` O, `nestjs@10.0.0` X)
- 변형 표기도 추가 (예: `spring boot`, `spring-boot`, `springboot`)
